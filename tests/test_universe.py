"""Tests for F&O universe module."""

from diamond_options.data.universe import (
    FNO_STOCKS,
    FNO_SYMBOLS,
    INDEX_CONTRACTS,
    get_fno_stock,
    get_lot_size,
    get_sector,
    is_fno_stock,
    get_index_lot_size,
    get_fno_by_sector,
    search_symbol,
)


def test_fno_stocks_not_empty():
    assert len(FNO_STOCKS) > 50


def test_all_stocks_have_lot_sizes():
    for stock in FNO_STOCKS:
        assert stock.lot_size > 0, f"{stock.symbol} has invalid lot size"


def test_all_stocks_have_sectors():
    for stock in FNO_STOCKS:
        assert stock.sector, f"{stock.symbol} missing sector"


def test_all_stocks_have_yf_tickers():
    for stock in FNO_STOCKS:
        assert stock.yf_ticker.endswith(".NS"), f"{stock.symbol} invalid YF ticker"


def test_get_fno_stock():
    stock = get_fno_stock("RELIANCE")
    assert stock is not None
    assert stock.lot_size == 250
    assert stock.yf_ticker == "RELIANCE.NS"


def test_get_fno_stock_case_insensitive():
    assert get_fno_stock("reliance") is not None
    assert get_fno_stock("Reliance") is not None


def test_get_fno_stock_not_found():
    assert get_fno_stock("NONEXISTENT") is None


def test_get_lot_size():
    assert get_lot_size("NIFTY") == 0  # NIFTY is index, not stock
    assert get_lot_size("RELIANCE") == 250
    assert get_lot_size("TCS") == 150


def test_get_lot_size_not_found():
    assert get_lot_size("FAKE") == 0


def test_is_fno_stock():
    assert is_fno_stock("RELIANCE") is True
    assert is_fno_stock("FAKE") is False


def test_index_contracts():
    assert "NIFTY" in INDEX_CONTRACTS
    assert "BANKNIFTY" in INDEX_CONTRACTS
    assert INDEX_CONTRACTS["NIFTY"]["lot_size"] == 65


def test_get_index_lot_size():
    assert get_index_lot_size("NIFTY") == 65
    assert get_index_lot_size("BANKNIFTY") == 15
    assert get_index_lot_size("FAKE") == 0


def test_get_sector():
    assert get_sector("RELIANCE") == "Energy"
    assert get_sector("TCS") == "Technology"
    assert get_sector("FAKE") == "Unknown"


def test_get_fno_by_sector():
    tech = get_fno_by_sector("Technology")
    assert len(tech) >= 3
    assert all(s.sector == "Technology" for s in tech)


def test_search_symbol():
    results = search_symbol("REL")
    assert any(s.symbol == "RELIANCE" for s in results)

    results = search_symbol("TAT")
    assert len(results) >= 2  # TATAMOTORS, TATASTEEL, etc.


def test_fno_symbols_list():
    assert "RELIANCE" in FNO_SYMBOLS
    assert len(FNO_SYMBOLS) == len(FNO_STOCKS)


def test_no_duplicate_symbols():
    assert len(FNO_SYMBOLS) == len(set(FNO_SYMBOLS))
