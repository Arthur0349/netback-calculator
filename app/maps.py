"""Route map: the trade lanes on a dark world map.

Lanes are drawn along sea waypoints (``reference/sea_lanes.json``), not as
straight great circles across continents. Three visual ranks: the best
outlet of the cargo in focus (amber), its other outlets (blue), and lanes
out of focus (hairline grey).
"""

from dataclasses import dataclass

import plotly.graph_objects as go
import streamlit as st

import theme

LANE_BLUE = "#6F9BC9"
LANE_DIM = "#35405A"
LAND = "#151C2C"
COAST = "#2B3550"

# Where each port label sits relative to its marker, to keep neighbours
# apart (the three North China ports, the two Guinea ports, the Gulf).
_LABEL_POSITION = {
    "Yantai": "top right", "Qingdao": "middle left", "Ningbo": "middle right",
    "Fangchenggang": "middle left", "Kamsar": "top left",
    "Morebaya": "bottom left", "Rotterdam": "top center",
    "Huelva": "middle left", "Ras Tanura": "top left",
    "Khalifa Port": "bottom center", "Sikka": "middle right",
    "Lobito": "middle right", "Dar es Salaam": "bottom center",
}


@dataclass
class Lane:
    load_port: str
    discharge_port: str
    path: list[tuple[float, float]]         # (lat, lon), load port first
    hover: str = ""                         # HTML, shown on the lane
    rank: str = "dim"                       # "best" | "focus" | "dim"


_STYLE = {
    "best": dict(color=theme.AMBER, width=2.4),
    "focus": dict(color=LANE_BLUE, width=1.6),
    "dim": dict(color=LANE_DIM, width=1.0),
}
_ORDER = {"dim": 0, "focus": 1, "best": 2}


def _midpoint(path: list[tuple[float, float]]) -> tuple[float, float]:
    """Vertex nearest to half the path length (flat-earth lengths are good
    enough to place a hover target)."""
    lengths = [0.0]
    for (lat0, lon0), (lat1, lon1) in zip(path, path[1:]):
        lengths.append(lengths[-1] + ((lat1 - lat0) ** 2 + (lon1 - lon0) ** 2) ** 0.5)
    half = lengths[-1] / 2.0
    return path[min(range(len(path)), key=lambda i: abs(lengths[i] - half))]


def _padded(name: str) -> str:
    """Keep side labels clear of their marker."""
    position = _LABEL_POSITION.get(name, "top center")
    if position.endswith("right"):
        return f"\u00a0\u00a0{name}"
    if position.endswith("left"):
        return f"{name}\u00a0\u00a0"
    return name


def route_map_figure(lanes: list[Lane], height: int = 440,
                     labels: bool = True) -> go.Figure:
    lanes = sorted(lanes, key=lambda lane: _ORDER[lane.rank])
    fig = go.Figure()
    hover_label = dict(bgcolor=theme.SURFACE, bordercolor=theme.BORDER,
                       font=dict(family=theme.MONO, color=theme.TEXT, size=12))

    for lane in lanes:
        fig.add_trace(go.Scattergeo(
            lat=[p[0] for p in lane.path], lon=[p[1] for p in lane.path],
            mode="lines", line=_STYLE[lane.rank], hoverinfo="skip",
            opacity=1.0 if lane.rank != "dim" else 0.9))

    # one invisible hover target per lane in focus, at mid-voyage
    for lane in lanes:
        if lane.rank == "dim" or not lane.hover:
            continue
        lat, lon = _midpoint(lane.path)
        fig.add_trace(go.Scattergeo(
            lat=[lat], lon=[lon], mode="markers",
            marker=dict(size=16, color=_STYLE[lane.rank]["color"], opacity=0.0),
            hovertemplate=lane.hover + "<extra></extra>"))

    # ports: a port takes the colour of its best lane; only ports in focus
    # are labelled
    ports: dict[str, dict] = {}
    for lane in lanes:
        for name, point, is_load in ((lane.load_port, lane.path[0], True),
                                     (lane.discharge_port, lane.path[-1], False)):
            port = ports.setdefault(name, {"point": point, "rank": lane.rank,
                                           "load": is_load, "hover": []})
            if _ORDER[lane.rank] > _ORDER[port["rank"]]:
                port["rank"] = lane.rank
            port["load"] = port["load"] or is_load
    for name, port in sorted(ports.items(), key=lambda kv: _ORDER[kv[1]["rank"]]):
        focus = port["rank"] != "dim"
        color = _STYLE[port["rank"]]["color"]
        fig.add_trace(go.Scattergeo(
            lat=[port["point"][0]], lon=[port["point"][1]],
            mode="markers+text" if focus and labels else "markers",
            text=[_padded(name)],
            textposition=_LABEL_POSITION.get(name, "top center"),
            textfont=dict(family=theme.SANS, size=11,
                          color=theme.TEXT if focus else theme.MUTED),
            marker=dict(size=8 if focus else 5,
                        color=theme.BG if port["load"] else color,
                        line=dict(color=color, width=1.6)),
            hovertemplate=(f"<b>{name}</b><br>"
                           f"{'Load port' if port['load'] else 'Outlet'}"
                           "<extra></extra>")))

    fig.update_geos(
        projection_type="equirectangular",
        lonaxis_range=[-58, 158], lataxis_range=[-43, 60],
        showland=True, landcolor=LAND,
        showocean=False, showlakes=False, showrivers=False,
        showcountries=False, showcoastlines=True, coastlinecolor=COAST,
        coastlinewidth=0.6, showframe=False, bgcolor="rgba(0,0,0,0)",
        resolution=110,
    )
    fig.update_layout(
        height=height, margin=dict(t=0, b=0, l=0, r=0), showlegend=False,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=theme.SANS, color=theme.TEXT, size=12),
        hoverlabel=hover_label, dragmode=False,
    )
    return fig


def responsive_map(lanes: list[Lane], key: str, height: int = 440) -> None:
    """Labelled map on wide screens; on phones a shorter one without port
    labels (names stay in the hover). Both are rendered, the stylesheet
    shows one per viewport."""
    config = {"displayModeBar": False, "scrollZoom": False}
    with st.container(key=f"nb_wide_{key}"):
        st.plotly_chart(route_map_figure(lanes, height), width="stretch",
                        config=config)
    with st.container(key=f"nb_narrow_{key}"):
        st.plotly_chart(route_map_figure(lanes, 190, labels=False),
                        width="stretch", config=config)


def map_legend(best: str, focus: str, dim: str | None = None) -> str:
    """Small HTML legend under the map (trusted text)."""
    def swatch(color: str, text: str) -> str:
        return (f'<span class="nb-legend-item"><span class="nb-legend-line" '
                f'style="background:{color}"></span>{text}</span>')
    items = [swatch(theme.AMBER, best), swatch(LANE_BLUE, focus)]
    if dim:
        items.append(swatch(LANE_DIM, dim))
    return f'<div class="nb-legend">{"".join(items)}</div>'
