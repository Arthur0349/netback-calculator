"""Arbitrage ranking: the same cargo netted back from several outlets.

Takes one ``NetbackResult`` per outlet and ranks them on the FOB netback,
the number a trader compares to pick where to sell. For each outlet it
reports:

- ``spread_vs_best``: netback gap to the best outlet ($/unit, <= 0);
- ``cushion``: for the best outlet, how far its netback can fall (freight
  up, price down...) before the runner-up wins; for the others, how much it
  must gain to become the best (negative);
- ``cargo_spread_vs_best``: the gap in USD over the whole cargo.

Pure function, no I/O.
"""

from pydantic import BaseModel

from netback.models.schemas import NetbackResult


class OutletRanking(BaseModel):
    outlet: str
    rank: int
    delivery_term: str
    delivered_price: float          # $/unit, before voyage costs
    freight: float
    other_costs: float              # insurance + financing + ports + commission
    quality_adjustment: float
    netback: float
    spread_vs_best: float
    cushion: float
    cargo_spread_vs_best: float


def rank_outlets(results: dict[str, NetbackResult],
                 quantity: float) -> list[OutletRanking]:
    """Rank outlets by FOB netback, best first. Requires netback-mode
    results (comparing landed costs is the buyer's question, not this one)."""
    if not results:
        return []
    for name, r in results.items():
        if r.mode != "netback":
            raise ValueError(f"{name!r} is a {r.mode} result; rank netbacks only")

    ordered = sorted(results.items(), key=lambda kv: kv[1].result_price,
                     reverse=True)
    best = ordered[0][1].result_price
    runner_up = ordered[1][1].result_price if len(ordered) > 1 else best

    rankings = []
    for i, (name, r) in enumerate(ordered, start=1):
        spread = r.result_price - best
        rankings.append(OutletRanking(
            outlet=name,
            rank=i,
            delivery_term=r.delivery_term,
            delivered_price=r.base_price,
            freight=r.freight_cost,
            other_costs=(r.insurance_cost + r.financing_cost
                         + r.port_fees_total + r.commission_cost),
            quality_adjustment=r.quality_adjustment,
            netback=r.result_price,
            spread_vs_best=spread,
            cushion=(best - runner_up) if i == 1 else spread,
            cargo_spread_vs_best=spread * quantity,
        ))
    return rankings
