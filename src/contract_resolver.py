"""Build ibapi Contract objects. Resolves ES/VXM expiry months for futures."""
from datetime import date, datetime

from ibapi.contract import Contract

from src.types import InstrumentConfig

# VIX must always use IND/CBOE regardless of what the config says.
VIX_SYMBOL = "VIX"
VIX_SEC_TYPE = "IND"
VIX_EXCHANGE = "CBOE"

# ES expiry: 3rd Friday of Mar/Jun/Sep/Dec
ES_QUARTERLY_MONTHS = [3, 6, 9, 12]

# VXM expiry: 3rd Wednesday of every month
WEDNESDAY_WEEKDAY = 2
FRIDAY_WEEKDAY = 4


def resolve_contract(instrument: InstrumentConfig, target_date: date) -> Contract:
    """
    Build an ibapi Contract for the given instrument and target date.

    Special cases:
    - VIX: always resolved as IND/CBOE regardless of config sec_type.
    - CONTFUT (ES, VXM): resolved to FUT with active expiry month and includeExpired=True.
    """
    if instrument.symbol == VIX_SYMBOL:
        return _build_contract(
            symbol=VIX_SYMBOL,
            sec_type=VIX_SEC_TYPE,
            exchange=VIX_EXCHANGE,
            currency=instrument.currency,
        )

    if instrument.sec_type == "CONTFUT":
        return _resolve_futures_contract(instrument, target_date)

    return _build_contract(
        symbol=instrument.symbol,
        sec_type=instrument.sec_type,
        exchange=instrument.exchange,
        currency=instrument.currency,
    )


def get_active_es_contract_month(target_date: date) -> str:
    """
    Return the active ES quarterly contract month for the given date (YYYYMM format).

    ES expires on the 3rd Friday of Mar/Jun/Sep/Dec.
    On or before the 3rd Friday → current quarter's contract.
    After the 3rd Friday → next quarter's contract.
    """
    year = target_date.year
    month = target_date.month
    day = target_date.day

    for quarterly_month in ES_QUARTERLY_MONTHS:
        if month < quarterly_month or (
            month == quarterly_month and day <= _get_third_friday(year, quarterly_month)
        ):
            return f"{year}{quarterly_month:02d}"

    # Past December expiry → next year's March contract
    return f"{year + 1}03"


def get_active_vxm_contract_month(target_date: date) -> str:
    """
    Return the active VXM monthly contract month for the given date (YYYYMM format).

    VXM expires on the 3rd Wednesday of each month.
    On or before the 3rd Wednesday → current month's contract.
    After the 3rd Wednesday → next month's contract.
    """
    year = target_date.year
    month = target_date.month
    day = target_date.day

    expiry_day = _get_third_wednesday(year, month)

    if day <= expiry_day:
        return f"{year}{month:02d}"

    # Roll to next month
    if month == 12:
        return f"{year + 1}01"
    return f"{year}{month + 1:02d}"


# ── Private helpers ──────────────────────────────────────────────────────────


def _resolve_futures_contract(instrument: InstrumentConfig, target_date: date) -> Contract:
    """Resolve a CONTFUT instrument to a concrete FUT contract with expiry month."""
    if instrument.symbol == "ES":
        contract_month = get_active_es_contract_month(target_date)
    elif instrument.symbol == "VXM":
        contract_month = get_active_vxm_contract_month(target_date)
    else:
        raise NotImplementedError(
            f"Futures contract resolution not yet implemented for {instrument.symbol}"
        )

    contract = _build_contract(
        symbol=instrument.symbol,
        sec_type="FUT",
        exchange=instrument.exchange,
        currency=instrument.currency,
    )
    contract.lastTradeDateOrContractMonth = contract_month
    contract.includeExpired = 1
    return contract


def _get_third_friday(year: int, month: int) -> int:
    """Return the day-of-month number of the 3rd Friday in the given month.

    Example: March 2024 → 15 (March 1 is a Friday, so 1st=Mar1, 2nd=Mar8, 3rd=Mar15).
    """
    first_day_weekday = datetime(year, month, 1).weekday()
    # Days from day 1 to the first occurrence of Friday (0 means day 1 is a Friday)
    days_until_friday = (FRIDAY_WEEKDAY - first_day_weekday) % 7
    first_friday = 1 + days_until_friday
    return first_friday + 14  # 3rd Friday = first + 2 weeks


def _get_third_wednesday(year: int, month: int) -> int:
    """Return the day-of-month number of the 3rd Wednesday in the given month."""
    first_day_weekday = datetime(year, month, 1).weekday()
    days_until_wednesday = (WEDNESDAY_WEEKDAY - first_day_weekday) % 7
    first_wednesday = 1 + days_until_wednesday
    return first_wednesday + 14  # 3rd Wednesday = first + 2 weeks


def _build_contract(symbol: str, sec_type: str, exchange: str, currency: str) -> Contract:
    contract = Contract()
    contract.symbol = symbol
    contract.secType = sec_type
    contract.exchange = exchange
    contract.currency = currency
    return contract
