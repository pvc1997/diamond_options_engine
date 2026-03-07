"""Tests for options chain module."""

from datetime import date

from diamond_options.data.options_chain import (
    OptionQuote,
    OptionsChain,
    generate_strikes,
    build_synthetic_chain,
)


class TestOptionQuote:
    def test_bid_ask_spread(self):
        q = OptionQuote(strike=22500, option_type="CE", expiry=date(2026, 3, 12),
                        ltp=130, bid=128, ask=132)
        assert q.bid_ask_spread == 4.0
        assert abs(q.bid_ask_spread_pct - 4 / 130) < 0.001

    def test_mid_price(self):
        q = OptionQuote(strike=22500, option_type="CE", expiry=date(2026, 3, 12),
                        ltp=130, bid=128, ask=132)
        assert q.mid_price == 130.0

    def test_mid_price_fallback_to_ltp(self):
        q = OptionQuote(strike=22500, option_type="CE", expiry=date(2026, 3, 12),
                        ltp=130)
        assert q.mid_price == 130.0

    def test_is_liquid(self):
        liquid = OptionQuote(strike=22500, option_type="CE", expiry=date(2026, 3, 12),
                             ltp=130, open_interest=1000, volume=100)
        illiquid = OptionQuote(strike=22500, option_type="CE", expiry=date(2026, 3, 12),
                               ltp=130, open_interest=50, volume=5)
        assert liquid.is_liquid is True
        assert illiquid.is_liquid is False

    def test_to_dict(self):
        q = OptionQuote(strike=22500, option_type="CE", expiry=date(2026, 3, 12), ltp=130)
        d = q.to_dict()
        assert d["strike"] == 22500
        assert d["expiry"] == "2026-03-12"


class TestOptionsChain:
    def test_strikes(self, sample_chain):
        strikes = sample_chain.strikes
        assert len(strikes) == 7
        assert strikes == sorted(strikes)

    def test_atm_strike(self, sample_chain):
        assert sample_chain.atm_strike == 22500

    def test_get_call(self, sample_chain):
        call = sample_chain.get_call(22500)
        assert call is not None
        assert call.ltp == 130.0

    def test_get_put(self, sample_chain):
        put = sample_chain.get_put(22500)
        assert put is not None
        assert put.ltp == 100.0

    def test_get_quote(self, sample_chain):
        ce = sample_chain.get_quote(22500, "CE")
        pe = sample_chain.get_quote(22500, "PE")
        assert ce is not None
        assert pe is not None
        assert ce.option_type == "CE"
        assert pe.option_type == "PE"

    def test_itm_otm_calls(self, sample_chain):
        itm = sample_chain.itm_calls()
        otm = sample_chain.otm_calls()
        assert all(q.strike < 22500 for q in itm)
        assert all(q.strike > 22500 for q in otm)

    def test_itm_otm_puts(self, sample_chain):
        itm = sample_chain.itm_puts()
        otm = sample_chain.otm_puts()
        assert all(q.strike > 22500 for q in itm)
        assert all(q.strike < 22500 for q in otm)

    def test_straddle(self, sample_chain):
        call, put = sample_chain.straddle()
        assert call is not None and put is not None
        assert call.strike == put.strike == 22500

    def test_pcr_oi(self, sample_chain):
        pcr = sample_chain.pcr_oi()
        assert pcr is not None
        assert 0.5 < pcr < 2.0  # Reasonable range

    def test_pcr_volume(self, sample_chain):
        pcr = sample_chain.pcr_volume()
        assert pcr is not None
        assert pcr > 0

    def test_max_pain(self, sample_chain):
        mp = sample_chain.max_pain()
        assert mp is not None
        assert 22200 <= mp <= 22800

    def test_total_oi(self, sample_chain):
        oi = sample_chain.total_oi()
        assert oi["call_oi"] > 0
        assert oi["put_oi"] > 0
        assert oi["total_oi"] == oi["call_oi"] + oi["put_oi"]

    def test_liquid_strikes(self, sample_chain):
        liquid = sample_chain.liquid_strikes(min_oi=50000)
        assert len(liquid) > 0
        assert all(isinstance(s, (int, float)) for s in liquid)

    def test_summary(self, sample_chain):
        s = sample_chain.summary()
        assert s["symbol"] == "NIFTY"
        assert s["atm_strike"] == 22500
        assert s["num_strikes"] == 7

    def test_to_dict_roundtrip(self, sample_chain):
        d = sample_chain.to_dict()
        assert d["symbol"] == "NIFTY"
        assert len(d["calls"]) == 7
        assert len(d["puts"]) == 7


class TestGenerateStrikes:
    def test_nifty_strikes(self):
        strikes = generate_strikes(22500, step=50, num_otm=5)
        assert 22500 in strikes
        assert len(strikes) == 11  # 5 below + ATM + 5 above

    def test_banknifty_strikes(self):
        strikes = generate_strikes(48000, step=100, num_otm=10)
        assert len(strikes) == 21

    def test_centered_around_atm(self):
        strikes = generate_strikes(22530, step=50, num_otm=3)
        # ATM should round to 22550
        assert 22550 in strikes
        assert strikes[0] == 22550 - 3 * 50


class TestSyntheticChain:
    def test_build(self):
        chain = build_synthetic_chain(
            "NIFTY", 22500, date(2026, 3, 12),
            [22400, 22500, 22600],
        )
        assert chain.symbol == "NIFTY"
        assert len(chain.calls) == 3
        assert len(chain.puts) == 3
        assert chain.spot_price == 22500

    def test_synthetic_iv(self):
        chain = build_synthetic_chain(
            "NIFTY", 22500, date(2026, 3, 12),
            [22500], iv=0.25,
        )
        assert chain.calls[0].iv == 0.25
        assert chain.puts[0].iv == 0.25
