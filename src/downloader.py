"""Orchestrate bar data download: config → dates → per-day download loop."""
import argparse
import time
from datetime import date, timedelta
from pathlib import Path

from src.bar_downloader import download_day
from src.config_loader import load_config
from src.file_writer import file_exists, read_bars, write_bars
from src.gap_checker import check_gaps
from src.ibkr_client import connect_to_ibkr, disconnect
from src.types import AppConfig, DayDownloadResult

IBKR_MAX_LOOKBACK_DAYS = 180
DAY_SLEEP_SECONDS = 1

US_MARKET_HOLIDAYS = {
    # New Year's Day (observed)
    date(2024, 1, 1),
    # Martin Luther King Jr. Day
    date(2024, 1, 15),
    # Presidents' Day
    date(2024, 2, 19),
    # Good Friday
    date(2024, 3, 29),
    # Memorial Day
    date(2024, 5, 27),
    # Juneteenth
    date(2024, 6, 19),
    # Independence Day
    date(2024, 7, 4),
    # Labor Day
    date(2024, 9, 2),
    # Thanksgiving
    date(2024, 11, 28),
    # Christmas
    date(2024, 12, 25),
    # 2025 holidays
    date(2025, 1, 1),
    date(2025, 1, 20),
    date(2025, 2, 17),
    date(2025, 4, 18),
    date(2025, 5, 26),
    date(2025, 6, 19),
    date(2025, 7, 4),
    date(2025, 9, 1),
    date(2025, 11, 27),
    date(2025, 12, 25),
    # 2026 holidays
    date(2026, 1, 1),
    date(2026, 1, 19),
    date(2026, 2, 16),
    date(2026, 4, 3),
    date(2026, 5, 25),
    date(2026, 6, 19),
    date(2026, 7, 3),
    date(2026, 9, 7),
    date(2026, 11, 26),
    date(2026, 12, 25),
}


def is_market_holiday(target_date: date) -> bool:
    """Return True if target_date is a known US market holiday."""
    return target_date in US_MARKET_HOLIDAYS


def _trading_dates(today: date) -> list[date]:
    """Return all trading dates in the IBKR 5-second bar lookback window (up to yesterday)."""
    earliest = today - timedelta(days=IBKR_MAX_LOOKBACK_DAYS)
    yesterday = today - timedelta(days=1)

    trading_dates = []
    current = earliest
    while current <= yesterday:
        if current.weekday() < 5 and not is_market_holiday(current):  # Mon–Fri, not holiday
            trading_dates.append(current)
        current += timedelta(days=1)

    return trading_dates


def run_download(config: AppConfig) -> list[DayDownloadResult]:
    """
    Connect to IBKR, compute the date range, and download all missing bar files.

    Returns the full list of DayDownloadResult (one per symbol × date pair).
    Existing files are skipped. Failures are logged and do not abort the run.
    """
    results: list[DayDownloadResult] = []
    today = date.today()
    trading_dates = _trading_dates(today)

    print(
        f"Connecting to IBKR on {config.ibkr_host}:{config.ibkr_port}...",
        flush=True,
    )
    client = connect_to_ibkr(config.ibkr_host, config.ibkr_port)
    print("Connected successfully.", flush=True)
    print(
        f"Download range: {trading_dates[0]} → {trading_dates[-1]} ({len(trading_dates)} days)",
        flush=True,
    )

    try:
        for target_date in trading_dates:
            spy_bars = _load_spy_bars(config, target_date)

            for instrument in config.instruments:
                if file_exists(config.data_dir, instrument.symbol, target_date):
                    print(f"[{target_date}] {instrument.symbol}: already have file, skipping.")
                    results.append(DayDownloadResult(
                        symbol=instrument.symbol,
                        date=target_date,
                        success=True,
                        skipped=True,
                        bars_saved=0,
                        file_path=None,
                        error_message=None,
                    ))
                    continue

                print(f"[{target_date}] {instrument.symbol}: downloading...", flush=True)
                try:
                    daily_bars = download_day(client, instrument, target_date, spy_bars)

                    if daily_bars is None:
                        results.append(DayDownloadResult(
                            symbol=instrument.symbol,
                            date=target_date,
                            success=False,
                            skipped=False,
                            bars_saved=0,
                            file_path=None,
                            error_message="No bars returned by IBKR",
                        ))
                        continue

                    gap_report = check_gaps(daily_bars)
                    if gap_report.has_gaps:
                        print(
                            f"  → Gap check: {len(gap_report.gaps)} gap(s) detected, "
                            f"bar_count_delta={gap_report.bar_count_delta}"
                        )
                    else:
                        print("  → Gap check: OK")

                    file_path = write_bars(config.data_dir, daily_bars)
                    print(f"  → {daily_bars.bar_count} bars saved to {file_path}")

                    results.append(DayDownloadResult(
                        symbol=instrument.symbol,
                        date=target_date,
                        success=True,
                        skipped=False,
                        bars_saved=daily_bars.bar_count,
                        file_path=file_path,
                        error_message=None,
                    ))

                except FileExistsError as exc:
                    # Second safety net — should not normally happen
                    print(f"  → Skipped (file appeared mid-run): {exc}")
                    results.append(DayDownloadResult(
                        symbol=instrument.symbol,
                        date=target_date,
                        success=True,
                        skipped=True,
                        bars_saved=0,
                        file_path=None,
                        error_message=None,
                    ))
                except Exception as exc:  # noqa: BLE001
                    print(f"  → FAILED: {exc}")
                    results.append(DayDownloadResult(
                        symbol=instrument.symbol,
                        date=target_date,
                        success=False,
                        skipped=False,
                        bars_saved=0,
                        file_path=None,
                        error_message=str(exc),
                    ))

            time.sleep(DAY_SLEEP_SECONDS)
    finally:
        disconnect(client)

    _print_summary(results)
    return results


def _load_spy_bars(config: AppConfig, target_date: date):
    """Load SPY bars for target_date if available, for VIX/SPX RTH filtering."""
    try:
        return read_bars(config.data_dir, config.spy_symbol, target_date)
    except FileNotFoundError:
        return None


def _print_summary(results: list[DayDownloadResult]) -> None:
    downloaded = sum(1 for r in results if r.success and not r.skipped)
    skipped = sum(1 for r in results if r.skipped)
    failed = sum(1 for r in results if not r.success)
    print(f"\nSummary: {downloaded} downloaded, {skipped} skipped, {failed} failed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download IBKR historical bar data")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(__file__).parent / "config.yaml",
        help="Path to config.yaml",
    )
    args = parser.parse_args()

    cfg = load_config(args.config)
    run_download(cfg)
