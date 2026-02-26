"""Build ibapi Contract objects. Resolves ES/VXM expiry months for futures (US2)."""
from datetime import date

from ibapi.contract import Contract

from src.types import InstrumentConfig

# VIX must always use IND/CBOE regardless of what the config says.
VIX_SYMBOL = "VIX"
VIX_SEC_TYPE = "IND"
VIX_EXCHANGE = "CBOE"


def resolve_contract(instrument: InstrumentConfig, target_date: date) -> Contract:
    """
    Build an ibapi Contract for the given instrument and target date.

    Special cases:
    - VIX: always resolved as IND/CBOE regardless of config sec_type.
    - CONTFUT (ES, VXM): raises NotImplementedError until US2 is implemented.
    """
    if instrument.symbol == VIX_SYMBOL:
        return _build_contract(
            symbol=VIX_SYMBOL,
            sec_type=VIX_SEC_TYPE,
            exchange=VIX_EXCHANGE,
            currency=instrument.currency,
        )

    if instrument.sec_type == "CONTFUT":
        raise NotImplementedError(
            f"Futures contract resolution not yet implemented for {instrument.symbol} — see US2"
        )

    return _build_contract(
        symbol=instrument.symbol,
        sec_type=instrument.sec_type,
        exchange=instrument.exchange,
        currency=instrument.currency,
    )


def get_active_es_contract_month(target_date: date) -> str:
    """Return the active ES quarterly contract month for the given date (YYYYMM format).

    ES expires on the 3rd Friday of Mar/Jun/Sep/Dec.
    Not implemented until US2.
    """
    raise NotImplementedError("ES contract resolution not yet implemented — see US2")


def get_active_vxm_contract_month(target_date: date) -> str:
    """Return the active VXM monthly contract month for the given date (YYYYMM format).

    VXM expires on the 3rd Wednesday of each month.
    Not implemented until US2.
    """
    raise NotImplementedError("VXM contract resolution not yet implemented — see US2")


def _build_contract(symbol: str, sec_type: str, exchange: str, currency: str) -> Contract:
    contract = Contract()
    contract.symbol = symbol
    contract.secType = sec_type
    contract.exchange = exchange
    contract.currency = currency
    return contract
