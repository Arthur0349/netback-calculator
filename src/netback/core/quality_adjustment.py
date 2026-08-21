"""Quality/spec adjustment — the only commodity-specific part of the engine.

Each commodity's ``CommodityProfile.quality_adjustment_fn`` names a function in
the registry below. Every function shares the same signature:

    (actual: dict, benchmark: dict, params: dict) -> float

and returns a signed $/unit adjustment (premium > 0, penalty < 0). Adding a
commodity means registering one function here — no engine change.
"""

from collections.abc import Callable

AdjustmentFn = Callable[[dict, dict, dict], float]

_REGISTRY: dict[str, AdjustmentFn] = {}


def register(name: str) -> Callable[[AdjustmentFn], AdjustmentFn]:
    def decorator(fn: AdjustmentFn) -> AdjustmentFn:
        _REGISTRY[name] = fn
        return fn
    return decorator


def get_adjustment_fn(name: str) -> AdjustmentFn:
    try:
        return _REGISTRY[name]
    except KeyError:
        raise KeyError(
            f"Unknown quality adjustment function {name!r}. "
            f"Registered: {sorted(_REGISTRY)}"
        ) from None


def quality_adjustment(fn_name: str, actual: dict, benchmark: dict,
                       params: dict) -> float:
    """Signed $/unit adjustment for the given cargo vs its benchmark spec."""
    return get_adjustment_fn(fn_name)(actual, benchmark, params)


@register("bauxite_linear")
def bauxite_linear(actual: dict, benchmark: dict, params: dict) -> float:
    """Linear adjustment per unit of deviation (standard Platts/CRU pattern):
    alumina content pays both ways, silica only penalises above benchmark.

    adjustment = (actual Al2O3 - benchmark Al2O3) x price_per_unit_alumina
               - max(0, actual SiO2 - benchmark SiO2) x penalty_per_unit_silica
    """
    alumina = (actual["Al2O3"] - benchmark["Al2O3"]) * params["price_per_unit_alumina"]
    silica = max(0.0, actual["SiO2"] - benchmark["SiO2"]) * params["penalty_per_unit_silica"]
    return alumina - silica


@register("spodumene_linear")
def spodumene_linear(actual: dict, benchmark: dict, params: dict) -> float:
    """Linear Li2O content adjustment vs the SC6 benchmark grade.

    adjustment = (actual Li2O - benchmark Li2O) x price_per_unit_li2o
    """
    return (actual["Li2O"] - benchmark["Li2O"]) * params["price_per_unit_li2o"]


@register("iron_ore_linear")
def iron_ore_linear(actual: dict, benchmark: dict, params: dict) -> float:
    """IODEX-style linear adjustment: Fe content pays both ways per 1 % Fe,
    silica and moisture only penalise above the benchmark spec.

    adjustment = (actual Fe - benchmark Fe) x price_per_unit_fe
               - max(0, actual SiO2 - benchmark SiO2) x penalty_per_unit_silica
               - max(0, actual moisture - benchmark moisture) x penalty_per_unit_moisture
    """
    fe = (actual["Fe"] - benchmark["Fe"]) * params["price_per_unit_fe"]
    silica = max(0.0, actual["SiO2"] - benchmark["SiO2"]) * params["penalty_per_unit_silica"]
    moisture = max(0.0, actual["moisture"] - benchmark["moisture"]) * params["penalty_per_unit_moisture"]
    return fe - silica - moisture


@register("crude_api_sulfur")
def crude_api_sulfur(actual: dict, benchmark: dict, params: dict) -> float:
    """OSP-grid-style linear adjustment for crude: lighter (higher API) and
    sweeter (lower sulfur) cargoes earn a premium, both signed both ways.

    adjustment = (actual API - benchmark API) x premium_per_api_degree
               - (actual sulfur - benchmark sulfur) x penalty_per_pct_sulfur
    """
    api = (actual["API"] - benchmark["API"]) * params["premium_per_api_degree"]
    sulfur = (actual["sulfur_pct"] - benchmark["sulfur_pct"]) * params["penalty_per_pct_sulfur"]
    return api - sulfur
