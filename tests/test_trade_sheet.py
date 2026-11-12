import pytest

from netback.core.netback import compute_result
from netback.core.sensitivity import tornado
from netback.data.providers import StaticDataProvider
from netback.reporting.trade_sheet import build_trade_sheet, waterfall_steps


@pytest.fixture
def provider():
    return StaticDataProvider()


def _args(provider, commodity, route_id):
    return (provider.get_default_cost_inputs(commodity, route_id),
            provider.get_route(route_id),
            provider.get_commodity_profile(commodity, route_id))


@pytest.mark.parametrize("commodity,route_id,mode", [
    ("iron_ore", "morebaya_qingdao", "netback"),
    ("crude_oil", "ras_tanura_ningbo", "landed_cost"),
    ("copper_concentrate", "dar_es_salaam_fangchenggang", "netback"),
])
def test_trade_sheet_is_a_one_page_pdf(provider, commodity, route_id, mode):
    inputs, route, profile = _args(provider, commodity, route_id)
    prices = provider.get_metal_prices(commodity)
    result = compute_result(inputs, route, profile, mode, prices)
    _, rows = tornado(inputs, route, profile, mode, prices)
    pdf = build_trade_sheet(result, inputs, route, profile, prices, rows,
                            as_of=provider.as_of)
    assert pdf.startswith(b"%PDF")
    assert pdf.count(b"/Type /Page\n") + pdf.count(b"/Type /Page ") == 1


def test_waterfall_steps_walk_to_the_result(provider):
    for commodity, route_id in [("iron_ore", "morebaya_qingdao"),
                                ("copper_concentrate", "lobito_qingdao")]:
        inputs, route, profile = _args(provider, commodity, route_id)
        result = compute_result(inputs, route, profile, "netback",
                                provider.get_metal_prices(commodity))
        steps = waterfall_steps(result)
        running = 0.0
        for _label, value, kind in steps:
            if kind == "total":
                assert running == 0.0 or value == pytest.approx(running)
                running = value
            else:
                running += value
        assert steps[-1][1] == pytest.approx(result.result_price)
