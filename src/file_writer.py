"""Read and write per-day bar CSV files. Never overwrites existing files."""
import csv
from datetime import date
from pathlib import Path

from src.types import Bar, DailyBars

CSV_HEADER = "timestamp,open,high,low,close,volume"


def day_file_path(data_dir: Path, symbol: str, target_date: date) -> Path:
    """Return the canonical path for a per-day bar CSV file."""
    return data_dir / "bars" / symbol / f"{target_date}_{symbol}.csv"


def file_exists(data_dir: Path, symbol: str, target_date: date) -> bool:
    """Return True if the bar file for this symbol and date already exists on disk."""
    return day_file_path(data_dir, symbol, target_date).exists()


def write_bars(data_dir: Path, bars: DailyBars) -> Path:
    """
    Write DailyBars to a CSV file. Creates parent directories as needed.

    Raises FileExistsError if the file already exists — existing data is never overwritten.
    """
    path = day_file_path(data_dir, bars.symbol, bars.date)
    if path.exists():
        raise FileExistsError(
            f"Bar file already exists and will not be overwritten: {path}"
        )

    path.parent.mkdir(parents=True, exist_ok=True)

    sorted_bars = sorted(bars.bars, key=lambda b: b.timestamp)
    with open(path, "w", newline="") as f:
        f.write(CSV_HEADER + "\n")
        writer = csv.writer(f)
        for bar in sorted_bars:
            writer.writerow([bar.timestamp, bar.open, bar.high, bar.low, bar.close, bar.volume])

    return path


def read_bars(data_dir: Path, symbol: str, target_date: date) -> DailyBars:
    """Read a per-day bar CSV file and return a DailyBars instance."""
    path = day_file_path(data_dir, symbol, target_date)
    if not path.exists():
        raise FileNotFoundError(f"Bar file not found: {path}")

    bars: list[Bar] = []
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            bars.append(Bar(
                timestamp=int(row["timestamp"]),
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=float(row["volume"]),
            ))

    return DailyBars(symbol=symbol, date=target_date, bars=bars)
