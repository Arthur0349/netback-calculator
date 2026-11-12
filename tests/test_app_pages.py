"""The Streamlit pages run end to end, on the static reference data (no
network), and the Calculator restores a case from a shared link."""

import os
from pathlib import Path

import pytest

os.environ["NETBACK_LIVE"] = "0"

from streamlit.testing.v1 import AppTest  # noqa: E402

HOME = str(Path(__file__).resolve().parents[1] / "app" / "Home.py")
PAGES = ["pages/1_Calculator.py", "pages/2_Arbitrage.py", "pages/3_Freight.py",
         "pages/4_Methodology.py"]


def run_home() -> AppTest:
    at = AppTest.from_file(HOME, default_timeout=30).run()
    assert not at.exception, at.exception
    return at


def number(at: AppTest, label: str) -> float:
    return next(w.value for w in at.number_input if w.label == label)


def test_home_runs():
    at = run_home()
    assert at.title[0].value == "Netback Calculator"


@pytest.mark.parametrize("page", PAGES)
def test_page_runs(page):
    at = run_home().switch_page(page).run()
    assert not at.exception, at.exception
    assert not at.error and not at.warning
    assert at.title


def test_calculator_restores_a_shared_link():
    at = run_home().switch_page(PAGES[0])
    for key, value in {"c": "iron_ore", "r": "morebaya_rotterdam",
                       "m": "landed_cost", "term": "DPU", "p": "95",
                       "q": "150000", "f": "11.25", "x.Fe": "63",
                       "ins": "not-a-number", "bogus": "1"}.items():
        at.query_params[key] = value
    at.run()
    assert not at.exception, at.exception
    assert at.title[0].value == "Iron ore fines: Landed cost"
    assert number(at, "Freight (USD/wmt)") == 11.25
    assert number(at, "Quantity (dmt)") == 150000
    assert number(at, "FOB price (USD/dmt)") == 95
    assert number(at, "Fe (benchmark 65)") == 63
    assert number(at, "Insurance %") == 0.35          # broken value: default
    # the URL now carries the full case, cleaned of what did not parse
    assert at.query_params["f"] in ("11.25", ["11.25"])
    assert "bogus" not in at.query_params


def test_calculator_ignores_a_link_to_nowhere():
    at = run_home().switch_page(PAGES[0])
    at.query_params["c"] = "unobtainium"
    at.query_params["q"] = "-5"
    at.run()
    assert not at.exception, at.exception
    assert at.title[0].value.startswith("Copper concentrate")


def test_freight_page_reconciles_with_the_reference_rate():
    at = run_home().switch_page(PAGES[2]).run()
    assert not at.exception, at.exception
    # the hire field opens on the TCE implied by the reference freight rate
    assert number(at, "Hire (USD/day)") > 5000
    assert any("on the reference rate" in m.value for m in at.markdown)
