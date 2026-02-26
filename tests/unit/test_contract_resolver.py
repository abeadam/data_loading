"""Tests for src/contract_resolver.py — pure logic, no IBKR connection."""
from datetime import date

import pytest


def make_instrument(symbol: str, sec_type: str, exchange: str = "SMART", currency: str = "USD"):
    from src.types import InstrumentConfig

    return InstrumentConfig(symbol=symbol, sec_type=sec_type, exchange=exchange, currency=currency)


class TestEquityContract:
    def test_stk_instrument_returns_stk_contract(self):
        from src.contract_resolver import resolve_contract

        inst = make_instrument("SPY", "STK", "SMART")
        contract = resolve_contract(inst, date(2024, 1, 2))

        assert contract.symbol == "SPY"
        assert contract.secType == "STK"
        assert contract.exchange == "SMART"
        assert contract.currency == "USD"

    def test_stk_contract_no_expiry(self):
        from src.contract_resolver import resolve_contract

        inst = make_instrument("SPY", "STK", "SMART")
        contract = resolve_contract(inst, date(2024, 1, 2))

        assert contract.lastTradeDateOrContractMonth == ""


class TestIndexContract:
    def test_ind_instrument_returns_ind_contract(self):
        from src.contract_resolver import resolve_contract

        inst = make_instrument("SPX", "IND", "CBOE")
        contract = resolve_contract(inst, date(2024, 1, 2))

        assert contract.symbol == "SPX"
        assert contract.secType == "IND"
        assert contract.exchange == "CBOE"

    def test_vix_config_sec_type_overridden_to_ind(self):
        from src.contract_resolver import resolve_contract

        # Even if config says CONTFUT, VIX must be resolved as IND/CBOE
        inst = make_instrument("VIX", "CONTFUT", "CFE")
        contract = resolve_contract(inst, date(2024, 1, 2))

        assert contract.secType == "IND"
        assert contract.exchange == "CBOE"

    def test_vix_ind_config_resolves_correctly(self):
        from src.contract_resolver import resolve_contract

        inst = make_instrument("VIX", "IND", "CBOE")
        contract = resolve_contract(inst, date(2024, 1, 2))

        assert contract.secType == "IND"
        assert contract.exchange == "CBOE"
        assert contract.symbol == "VIX"


class TestContfutStub:
    def test_contfut_non_vix_raises_not_implemented(self):
        from src.contract_resolver import resolve_contract

        inst = make_instrument("ES", "CONTFUT", "CME")
        with pytest.raises(NotImplementedError, match="[Ff]utures"):
            resolve_contract(inst, date(2024, 1, 2))

    def test_vxm_contfut_raises_not_implemented(self):
        from src.contract_resolver import resolve_contract

        inst = make_instrument("VXM", "CONTFUT", "CFE")
        with pytest.raises(NotImplementedError, match="[Ff]utures"):
            resolve_contract(inst, date(2024, 1, 2))
