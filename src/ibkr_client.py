"""IBKR connection lifecycle, pacing, and historical data/news requests."""
import threading
import time
from typing import Any

from ibapi.client import EClient
from ibapi.contract import Contract
from ibapi.wrapper import EWrapper

PACING_SLEEP_SECONDS = 2
DAY_SLEEP_SECONDS = 1
REQUEST_TIMEOUT_SECONDS = 60
SPX_REQUEST_TIMEOUT_SECONDS = 600
CLIENT_IDS_TO_TRY = [1, 2, 3, 4, 5]
NEWS_PACING_SLEEP_SECONDS = 0.5


class IBKRClient(EWrapper, EClient):
    """Minimal IBKR client: connects, fetches historical bars and news, disconnects."""

    def __init__(self) -> None:
        EWrapper.__init__(self)
        EClient.__init__(self, wrapper=self)

        self._next_req_id: int = 0
        self._bar_data: list[dict[str, Any]] = []
        self._bar_request_done = threading.Event()
        self._error_code: int | None = None
        self._error_msg: str | None = None

        self._news_items: list[dict[str, Any]] = []
        self._news_request_done = threading.Event()

        self._con_id: int | None = None
        self._contract_details_done = threading.Event()

    # ── EWrapper callbacks ───────────────────────────────────────────────────

    def nextValidId(self, order_id: int) -> None:
        self._next_req_id = order_id

    def historicalData(self, req_id: int, bar: Any) -> None:
        self._bar_data.append({
            "timestamp": int(bar.date),
            "open": bar.open,
            "high": bar.high,
            "low": bar.low,
            "close": bar.close,
            "volume": bar.volume,
        })

    def historicalDataEnd(self, req_id: int, start: str, end: str) -> None:
        self._bar_request_done.set()

    def historicalNews(self, req_id: int, time: str, provider_code: str, article_id: str, headline: str) -> None:
        self._news_items.append({
            "time": time,
            "provider_code": provider_code,
            "article_id": article_id,
            "headline": headline,
        })

    def historicalNewsEnd(self, req_id: int, has_more: bool) -> None:
        self._news_request_done.set()

    def contractDetails(self, req_id: int, contract_details: Any) -> None:
        self._con_id = contract_details.contract.conId

    def contractDetailsEnd(self, req_id: int) -> None:
        self._contract_details_done.set()

    def error(self, req_id: int, error_time: int, error_code: int, error_string: str, advanced_order_reject_json: str = "") -> None:
        # These codes are warnings/informational — data is still returned normally.
        # 2104/2106/2107/2108/2119/2158: market data farm connection status
        # 2176: fractional share size rules (warning only — data still returned)
        informational_codes = {2104, 2106, 2107, 2108, 2119, 2158, 2176}
        if error_code in informational_codes:
            return
        self._error_code = error_code
        self._error_msg = error_string
        # Unblock any waiting event if this is a terminal error
        if req_id != -1:
            self._bar_request_done.set()
            self._news_request_done.set()
            self._contract_details_done.set()


def connect_to_ibkr(host: str, port: int, client_ids: list[int] = CLIENT_IDS_TO_TRY) -> IBKRClient:
    """
    Connect to TWS/IB Gateway, trying each client ID in sequence.

    Raises ConnectionError if all client IDs fail.
    """
    for client_id in client_ids:
        client = IBKRClient()
        client.connect(host, port, clientId=client_id)
        thread = threading.Thread(target=client.run, daemon=True)
        thread.start()
        time.sleep(1)  # Allow time for nextValidId callback
        if client.isConnected():
            return client
        client.disconnect()

    raise ConnectionError(
        f"Could not connect to IBKR at {host}:{port} after trying client IDs {client_ids}"
    )


def disconnect(client: IBKRClient) -> None:
    """Disconnect from TWS/IB Gateway."""
    client.disconnect()


def fetch_historical_bars(
    client: IBKRClient,
    contract: Contract,
    end_datetime: str,
    duration_str: str,
    bar_size: str = "5 secs",
    what_to_show: str = "TRADES",
    use_rth: int = 0,
) -> list[dict[str, Any]]:
    """
    Request historical bars from IBKR and block until data arrives.

    Returns a list of bar dicts with keys: timestamp, open, high, low, close, volume.
    Applies a 2-second pacing sleep after each call.

    Raises TimeoutError if data does not arrive within the timeout window.
    Raises RuntimeError if IBKR returns an error for this request.
    """
    is_spx = contract.symbol == "SPX"
    timeout = SPX_REQUEST_TIMEOUT_SECONDS if is_spx else REQUEST_TIMEOUT_SECONDS

    client._bar_data = []
    client._bar_request_done.clear()
    client._error_code = None
    client._error_msg = None

    req_id = client._next_req_id
    client._next_req_id += 1

    client.reqHistoricalData(
        reqId=req_id,
        contract=contract,
        endDateTime=end_datetime,
        durationStr=duration_str,
        barSizeSetting=bar_size,
        whatToShow=what_to_show,
        useRTH=use_rth,
        formatDate=2,  # epoch timestamps
        keepUpToDate=False,
        chartOptions=[],
    )

    done = client._bar_request_done.wait(timeout=timeout)

    time.sleep(PACING_SLEEP_SECONDS)  # IBKR pacing requirement

    if not done:
        raise TimeoutError(
            f"Historical bar request for {contract.symbol} timed out after {timeout}s"
        )
    if client._error_code is not None:
        raise RuntimeError(
            f"IBKR error {client._error_code} for {contract.symbol}: {client._error_msg}"
        )

    return list(client._bar_data)


def resolve_con_id(client: IBKRClient, contract: Contract) -> int:
    """
    Resolve the conId for a contract via reqContractDetails.

    Returns the integer conId.
    Raises RuntimeError if no contract details are returned.
    """
    client._con_id = None
    client._contract_details_done.clear()

    req_id = client._next_req_id
    client._next_req_id += 1

    client.reqContractDetails(reqId=req_id, contract=contract)
    done = client._contract_details_done.wait(timeout=REQUEST_TIMEOUT_SECONDS)

    if not done or client._con_id is None:
        raise RuntimeError(
            f"Could not resolve conId for {contract.symbol}: timeout or no details returned"
        )

    return client._con_id


def fetch_historical_news(
    client: IBKRClient,
    con_id: int,
    provider_codes: str,
    start_datetime: str,
    end_datetime: str,
    total_results: int = 300,
) -> list[dict[str, Any]]:
    """
    Request historical news headlines from IBKR and block until data arrives.

    Returns a list of news dicts with keys: time, provider_code, article_id, headline.
    Raises PermissionError if error code 10276 is returned (no news subscription).
    """
    client._news_items = []
    client._news_request_done.clear()
    client._error_code = None
    client._error_msg = None

    req_id = client._next_req_id
    client._next_req_id += 1

    client.reqHistoricalNews(
        reqId=req_id,
        conId=con_id,
        providerCodes=provider_codes,
        startDateTime=start_datetime,
        endDateTime=end_datetime,
        totalResults=total_results,
        historicalNewsOptions=[],
    )

    done = client._news_request_done.wait(timeout=REQUEST_TIMEOUT_SECONDS)

    if not done:
        raise TimeoutError(f"Historical news request timed out after {REQUEST_TIMEOUT_SECONDS}s")

    if client._error_code == 10276:
        raise PermissionError(
            f"IBKR news subscription required (error 10276): {client._error_msg}"
        )
    if client._error_code is not None:
        raise RuntimeError(
            f"IBKR error {client._error_code} for news request: {client._error_msg}"
        )

    return list(client._news_items)
