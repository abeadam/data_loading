"""Tests for src/contract_resolver.py — pure logic, no IBKR connection."""
from datetime import date



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
    """These tests become invalid once US2 is implemented — replaced by TestFuturesContract."""

    def test_contfut_non_vix_no_longer_raises(self):
        """After US2 implementation, CONTFUT resolves correctly (no NotImplementedError)."""
        from src.contract_resolver import resolve_contract

        inst = make_instrument("ES", "CONTFUT", "CME")
        # Should no longer raise after US2 implementation
        contract = resolve_contract(inst, date(2024, 1, 2))
        assert contract.secType == "FUT"

    def test_vxm_contfut_resolves(self):
        """After US2 implementation, VXM CONTFUT resolves correctly."""
        from src.contract_resolver import resolve_contract

        inst = make_instrument("VXM", "CONTFUT", "CFE")
        contract = resolve_contract(inst, date(2024, 1, 2))
        assert contract.secType == "FUT"


class TestESContractMonth:
    """ES quarterly expiry — 3rd Friday of Mar/Jun/Sep/Dec."""

    def test_jan_15_uses_march_contract(self):
        from src.contract_resolver import get_active_es_contract_month

        # Jan 15 2024: well before March 3rd Friday (Mar 15, 2024)
        assert get_active_es_contract_month(date(2024, 1, 15)) == "202403"

    def test_march_14_before_expiry_uses_march(self):
        from src.contract_resolver import get_active_es_contract_month

        # Mar 14 2024: 3rd Friday of March 2024 is Mar 15 → still in March contract
        assert get_active_es_contract_month(date(2024, 3, 14)) == "202403"

    def test_march_15_on_expiry_uses_march(self):
        from src.contract_resolver import get_active_es_contract_month

        # Mar 15 2024 is the 3rd Friday — on expiry day still uses March contract
        assert get_active_es_contract_month(date(2024, 3, 15)) == "202403"

    def test_march_18_after_expiry_uses_june(self):
        from src.contract_resolver import get_active_es_contract_month

        # Mar 18 2024: day after 3rd Friday → rolls to June
        assert get_active_es_contract_month(date(2024, 3, 18)) == "202406"

    def test_july_uses_september(self):
        from src.contract_resolver import get_active_es_contract_month

        assert get_active_es_contract_month(date(2024, 7, 1)) == "202409"

    def test_october_uses_december(self):
        from src.contract_resolver import get_active_es_contract_month

        assert get_active_es_contract_month(date(2024, 10, 1)) == "202412"

    def test_december_after_expiry_rolls_to_next_march(self):
        from src.contract_resolver import get_active_es_contract_month

        # Dec 2024 3rd Friday is Dec 20 → Dec 21+ rolls to Mar 2025
        assert get_active_es_contract_month(date(2024, 12, 21)) == "202503"


class TestVXMContractMonth:
    """VXM monthly expiry — 3rd Wednesday of each month."""

    def test_mid_month_before_expiry_uses_current_month(self):
        from src.contract_resolver import get_active_vxm_contract_month

        # Jan 2024: 3rd Wednesday is Jan 17 → Jan 15 still in Jan contract
        assert get_active_vxm_contract_month(date(2024, 1, 15)) == "202401"

    def test_on_expiry_day_uses_current_month(self):
        from src.contract_resolver import get_active_vxm_contract_month

        # Jan 17 2024 is 3rd Wednesday → still Jan contract
        assert get_active_vxm_contract_month(date(2024, 1, 17)) == "202401"

    def test_after_expiry_rolls_to_next_month(self):
        from src.contract_resolver import get_active_vxm_contract_month

        # Jan 18 2024: day after 3rd Wednesday → Feb contract
        assert get_active_vxm_contract_month(date(2024, 1, 18)) == "202402"

    def test_december_after_expiry_rolls_to_january(self):
        from src.contract_resolver import get_active_vxm_contract_month

        # Dec 2024: 3rd Wednesday is Dec 18 → Dec 19+ rolls to Jan 2025
        assert get_active_vxm_contract_month(date(2024, 12, 19)) == "202501"


class TestFuturesContract:
    """resolve_contract for CONTFUT instruments — requires US2 implementation."""

    def test_es_contfut_returns_fut_contract(self):
        from src.contract_resolver import resolve_contract

        inst = make_instrument("ES", "CONTFUT", "CME")
        contract = resolve_contract(inst, date(2024, 1, 15))

        assert contract.secType == "FUT"
        assert contract.symbol == "ES"
        assert contract.exchange == "CME"
        assert contract.lastTradeDateOrContractMonth == "202403"
        assert contract.includeExpired == 1

    def test_vxm_contfut_returns_fut_contract(self):
        from src.contract_resolver import resolve_contract

        inst = make_instrument("VXM", "CONTFUT", "CFE")
        contract = resolve_contract(inst, date(2024, 1, 15))

        assert contract.secType == "FUT"
        assert contract.symbol == "VXM"
        assert contract.exchange == "CFE"
        assert contract.lastTradeDateOrContractMonth == "202401"
        assert contract.includeExpired == 1

    def test_es_after_march_expiry_uses_june(self):
        from src.contract_resolver import resolve_contract

        inst = make_instrument("ES", "CONTFUT", "CME")
        contract = resolve_contract(inst, date(2024, 3, 18))

        assert contract.lastTradeDateOrContractMonth == "202406"
