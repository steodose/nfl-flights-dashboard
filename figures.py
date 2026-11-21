"""Plotly figure builders. Every builder takes a `theme` ("light" | "dark")."""
from __future__ import annotations

import math
import re

import pandas as pd
import plotly.graph_objects as go

from data import great_circle

AFC = "#d50a0a"
NFC = "#013369"
NFC_DARK = "#4f7cc4"  # navy is too dark to read on a dark background
ROUTE = "#3ee0d0"
ROUTE_HI = "#ffd23f"
AIRPORT = "#ef4b55"
FONT = "Titillium Web, Segoe UI, Helvetica, Arial, sans-serif"

# Label anchor points (lat, lon) for country names drawn on the label-free basemap.
COUNTRY_LABELS = [
    ("United States", 39.5, -98.5), ("Canada", 58.0, -103.0), ("Mexico", 23.5, -102.5),
    ("Cuba", 21.7, -79.0), ("Guatemala", 15.6, -90.3), ("Honduras", 14.8, -86.8),
    ("Nicaragua", 12.9, -85.0), ("Panama", 8.5, -80.1), ("Venezuela", 7.1, -66.2),
    ("Colombia", 3.9, -73.1), ("Ecuador", -1.4, -78.4), ("Peru", -9.2, -75.0),
    ("Brazil", -10.8, -52.9), ("Bolivia", -16.7, -64.7), ("Paraguay", -23.4, -58.4),
    ("Chile", -30.0, -71.0), ("Argentina", -35.4, -65.2), ("Uruguay", -32.8, -56.0),
    ("Greenland", 72.0, -40.0), ("Iceland", 64.9, -18.6), ("Ireland", 53.2, -8.0),
    ("United Kingdom", 52.8, -1.6), ("Spain", 40.2, -3.6), ("Portugal", 39.6, -8.0),
    ("France", 46.6, 2.4), ("Germany", 51.1, 10.4), ("Italy", 42.8, 12.6),
    ("Norway", 61.5, 9.0), ("Sweden", 62.5, 15.5), ("Poland", 52.1, 19.4),
    ("Morocco", 31.8, -6.8), ("Algeria", 28.0, 2.6), ("Russia", 61.0, 96.0),
    ("Japan", 36.5, 138.5), ("China", 35.0, 103.0), ("Australia", -25.7, 134.5),
    ("New Zealand", -41.5, 172.5),
]

# City served by each airport code in the data. Unlisted codes fall back to the code itself.
AIRPORT_CITIES = {
    "AFW": "Fort Worth", "ATL": "Atlanta", "ATW": "Appleton", "BED": "Bedford", "BER": "Berlin",
    "BKL": "Cleveland", "BNA": "Nashville", "BOS": "Boston", "BUF": "Buffalo", "BWI": "Baltimore",
    "CDG": "Paris", "CLE": "Cleveland", "CLT": "Charlotte", "COS": "Colorado Springs",
    "CVG": "Cincinnati", "DAL": "Dallas", "DEN": "Denver", "DET": "Detroit", "DFW": "Dallas",
    "DTW": "Detroit", "DUB": "Dublin", "EFD": "Houston", "EWR": "Newark", "FLL": "Fort Lauderdale",
    "FRA": "Frankfurt", "GIG": "Rio de Janeiro", "GRB": "Green Bay", "GRU": "São Paulo", "GYY": "Gary",
    "HHN": "Hahn", "IAD": "Washington", "IAG": "Niagara Falls", "IAH": "Houston",
    "IND": "Indianapolis", "JAX": "Jacksonville", "LAS": "Las Vegas", "LAX": "Los Angeles",
    "LHR": "London", "LWB": "Lewisburg", "MAD": "Madrid", "MCI": "Kansas City", "MDW": "Chicago",
    "MEL": "Melbourne", "MIA": "Miami", "MSP": "Minneapolis", "MSY": "New Orleans", "MUC": "Munich",
    "OAK": "Oakland", "ORD": "Chicago", "PHL": "Philadelphia", "PHX": "Phoenix", "PIT": "Pittsburgh",
    "PVD": "Providence", "ROA": "Roanoke", "SEA": "Seattle", "SFO": "San Francisco", "SJC": "San Jose",
    "STN": "London", "TPA": "Tampa",
}

THEMES = {
    "light": dict(ink="#0b0b0b", ink2="#52514e", muted="#8a8984", grid="#e8e7e3", surface="#fcfcfb", accent=NFC),
    "dark": dict(ink="#f2f1ee", ink2="#c9c8c3", muted="#96958f", grid="#363532", surface="#1c1c1b", accent="#7aa2e3"),
}


def _blend(hex_color: str, bg_hex: str, alpha: float) -> str:
    """Solid color equal to `hex_color` at `alpha` opacity over `bg_hex`."""
    fg = [int(hex_color[i:i + 2], 16) for i in (1, 3, 5)]
    bg = [int(bg_hex[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(a * alpha + b * (1 - alpha)):02x}" for a, b in zip(fg, bg))


def conf_colors(theme: str) -> dict:
    return {"AFC": AFC if theme == "light" else "#ef4b55", "NFC": NFC if theme == "light" else NFC_DARK}


def _base_layout(theme: str, **kw) -> dict:
    t = THEMES[theme]
    layout = dict(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=FONT, color=t["ink2"], size=13),
        margin=dict(l=8, r=16, t=8, b=8),
        hoverlabel=dict(font=dict(family=FONT, size=13), bgcolor=t["surface"], bordercolor=t["grid"], font_color=t["ink"]),
        showlegend=False,
    )
    layout.update(kw)
    return layout


def _fit_view(lats: list[float], lons: list[float]) -> tuple[dict, float]:
    lat_min, lat_max = min(lats), max(lats)
    lon_min, lon_max = min(lons), max(lons)
    center = dict(lat=(lat_min + lat_max) / 2, lon=(lon_min + lon_max) / 2)
    span = max(lat_max - lat_min, (lon_max - lon_min) / 1.8, 1)
    # Rough span -> zoom mapping for a ~560px tall map.
    for z_span, z in ((4, 5.2), (10, 4.2), (20, 3.3), (35, 2.6), (60, 2.0), (90, 1.5), (140, 1.0)):
        if span <= z_span:
            zoom = z
            break
    else:
        zoom = 0.7
    return center, zoom


# Sides of an airport dot to try for its city label, in order of preference.
LABEL_POSITIONS = ("top center", "middle right", "middle left", "bottom center",
                   "top right", "top left", "bottom right", "bottom left")


def _map_px(lat: float, lon: float, zoom: float) -> tuple[float, float]:
    """Web-Mercator pixel position at `zoom` (MapLibre uses 512px tiles)."""
    world = 512 * 2 ** zoom
    y = math.log(math.tan(math.pi / 4 + math.radians(max(min(lat, 85), -85)) / 2))
    return (lon + 180) / 360 * world, (1 - y / math.pi) / 2 * world


def _label_box(x: float, y: float, text: str, position: str, size: int = 13) -> tuple:
    w, h, gap = len(text) * size * 0.5 + 2, size + 3, 7
    vert, horiz = position.split()
    x0 = {"center": x - w / 2, "right": x + gap, "left": x - gap - w}[horiz]
    y0 = {"middle": y - h / 2, "bottom": y + gap, "top": y - gap - h}[vert]
    return x0, y0, x0 + w, y0 + h


def _overlaps(a: tuple, b: tuple) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def _merge_close_labels(points: list[tuple], zoom: float) -> list[str]:
    """Share one label between dots that sit on top of each other, e.g. "Green Bay / Appleton"."""
    labels = [text for _, _, text in points]
    pixels = [_map_px(lat, lon, zoom) for lat, lon, _ in points]
    for i, text in enumerate(labels):
        if not text:
            continue
        for j in range(i):
            if labels[j] and math.hypot(pixels[i][0] - pixels[j][0], pixels[i][1] - pixels[j][1]) < 7:
                labels[j], labels[i] = f"{labels[j]} / {text}", ""
                break
    return labels


def _place_labels(points: list[tuple], zoom: float) -> tuple[list[str], list[tuple]]:
    """Pick a free side for each (lat, lon, text), because the map hides overlapping labels.

    Returns each point's position and the boxes taken, in pixels at `zoom`.
    """
    pixels = [_map_px(lat, lon, zoom) for lat, lon, _ in points]
    dots = [(x - 6, y - 6, x + 6, y + 6) for x, y in pixels]
    labelled = [i for i, point in enumerate(points) if point[2]]
    positions = [LABEL_POSITIONS[0]] * len(points)

    def box(i: int, position: str) -> tuple:
        return _label_box(*pixels[i], points[i][2], position)

    def cost(i: int, position: str) -> float:
        b = box(i, position)
        # 3px margin: the map drops labels that merely touch.
        padded = (b[0] - 3, b[1] - 3, b[2] + 3, b[3] + 3)
        labels_hit = sum(_overlaps(padded, box(j, positions[j])) for j in labelled if j != i)
        dots_hit = sum(_overlaps(padded, d) for j, d in enumerate(dots) if j != i)
        return 10 * labels_hit + 3 * dots_hit + LABEL_POSITIONS.index(position) * 0.01

    # Repeatedly move each label to its least-conflicting side until nothing changes.
    for _ in range(12):
        changed = False
        for i in labelled:
            best = min(LABEL_POSITIONS, key=lambda position: cost(i, position))
            if best != positions[i]:
                positions[i], changed = best, True
        if not changed:
            break
    taken = [box(i, positions[i]) for i in labelled]
    return positions, taken


def map_figure(legs: pd.DataFrame, theme: str = "light", highlight_ids: list | None = None) -> go.Figure:
    """Great-circle routes for the given legs on a dark basemap."""
    highlight_ids = set(highlight_ids or [])
    fig = go.Figure()

    route_lat, route_lon, hi_lat, hi_lon = [], [], [], []
    hover_lat, hover_lon, hover_text = [], [], []
    # Put every longitude in one frame (within 180 deg of the median airport) so
    # trans-Pacific routes and US routes share a continuous view.
    ref = float(pd.concat([legs["dep_lon"], legs["arr_lon"]]).median()) if len(legs) else -96.0

    def near_ref(lon: float) -> float:
        return lon - 360 * round((lon - ref) / 360)

    for row in legs.itertuples(index=False):
        lats, lons = great_circle(row.dep_lat, row.dep_lon, row.arr_lat, row.arr_lon)
        shift = near_ref(lons[0]) - lons[0]
        lons = [v + shift for v in lons]
        target_lat, target_lon = (hi_lat, hi_lon) if row.row_id in highlight_ids else (route_lat, route_lon)
        target_lat += lats + [None]
        target_lon += lons + [None]
        mid = len(lats) // 2
        hover_lat.append(lats[mid])
        hover_lon.append(lons[mid])
        d = row.flight_date
        date_str = f"{d:%a, %b} {d.day}, {d.year}" if pd.notna(d) else "Date n/a"
        hover_text.append(
            f"<b>Week {row.week}</b> · {row.direction.title()} · {date_str}<br>"
            f"{row.dep_airport} → {row.arr_airport} · {row.distance_mi:,} mi<br>"
            f"vs {row.home_team}<br>"
            f"{row.airline} {row.flight_number} · {row.aircraft_type}"
        )

    fig.add_trace(go.Scattermap(lat=route_lat, lon=route_lon, mode="lines",
                                line=dict(width=2.2, color=ROUTE), hoverinfo="skip", opacity=0.9))
    if hi_lat:
        fig.add_trace(go.Scattermap(lat=hi_lat, lon=hi_lon, mode="lines",
                                    line=dict(width=4.5, color=ROUTE_HI), hoverinfo="skip"))

    # Invisible-ish midpoint markers carry the route hover text.
    fig.add_trace(go.Scattermap(lat=hover_lat, lon=hover_lon, mode="markers",
                                marker=dict(size=14, color=ROUTE, opacity=0.01),
                                text=hover_text, hovertemplate="%{text}<extra></extra>"))

    airports = pd.concat([
        legs[["dep_airport", "dep_lat", "dep_lon"]].set_axis(["code", "lat", "lon"], axis=1),
        legs[["arr_airport", "arr_lat", "arr_lon"]].set_axis(["code", "lat", "lon"], axis=1),
    ]).drop_duplicates("code")
    airports["lon"] = airports["lon"].map(near_ref)
    cities = airports["code"].map(lambda code: AIRPORT_CITIES.get(code, code))

    if route_lat or hi_lat:
        all_lat = [v for v in route_lat + hi_lat if v is not None]
        all_lon = [v for v in route_lon + hi_lon if v is not None]
        center, zoom = _fit_view(all_lat, all_lon)
    else:
        center, zoom = dict(lat=39, lon=-96), 2.8

    # Label each city once, even when a team used two of its airports.
    labels = _merge_close_labels(
        list(zip(airports["lat"], airports["lon"], cities.where(~cities.duplicated(), ""))), zoom)
    positions, city_boxes = _place_labels(list(zip(airports["lat"], airports["lon"], labels)), zoom)
    airports = airports.assign(label=labels, position=positions, place=airports["code"] + " · " + cities)

    # Country names (the basemap's own labels only appear at zoom >= 2). City labels take priority.
    countries = []
    for name, lat, lon in COUNTRY_LABELS:
        lon = near_ref(lon)
        x, y = _map_px(lat, lon, zoom)
        country_box = (x - len(name) * 3.6, y - 9, x + len(name) * 3.6, y + 9)
        if not any(_overlaps(country_box, box) for box in city_boxes):
            countries.append((name, lat, lon))
    fig.add_trace(go.Scattermap(
        lat=[c[1] for c in countries], lon=[c[2] for c in countries],
        text=[c[0] for c in countries], mode="text", hoverinfo="skip",
        textfont=dict(size=12, color="#9aa4ab"),
    ))
    # textposition is per-trace on maps, so airports are grouped by label side.
    for position, group in airports.groupby("position", sort=False):
        fig.add_trace(go.Scattermap(
            lat=group["lat"], lon=group["lon"], mode="markers+text",
            marker=dict(size=10, color=AIRPORT),
            text=group["label"], textposition=position,
            textfont=dict(size=13, color="#ffffff"),
            customdata=group["place"],
            hovertemplate="<b>%{customdata}</b><extra></extra>",
        ))

    fig.update_layout(**_base_layout(theme, margin=dict(l=0, r=0, t=0, b=0)),
                      map=dict(style="carto-darkmatter-nolabels", center=center, zoom=zoom))
    return fig


LABEL_PAD = 4      # px between the figure's left edge and the logo column
LOGO_GAP = 8       # px between the logo column and the row labels
LABEL_GAP = 10     # px between the row labels and the bars


def _logo_label_column(fig: go.Figure, logos: list[str] | None, labels: list[str], color: str,
                       size: int, logo_px: int, sizey: float, est_plot_w: int,
                       logo_first: bool = True) -> int:
    """Left-hand row column, flush left, then the bars. Returns the left margin (px).

    logo_first=True:  [logo][label] [bar]   (logos pinned to the figure's left edge)
    logo_first=False: [label] [logo][bar]   (logos pinned against the axis)

    `logo_px` is the logo box width; `sizey` (in rows) caps the height, so square logos
    fill the height and wide wordmarks use the extra width.

    Labels are annotations positioned in pixels. Plotly can only place images in
    fractions of the plot width, so logos get an estimated position here and
    assets/logo-column.js re-pins them (using layout.meta) at the real width.
    """
    logo_w = logo_px + LOGO_GAP if logos else 0
    label_w = _label_width(labels, size)
    margin_l = LABEL_PAD + logo_w + label_w + LABEL_GAP
    label_shift = -margin_l + LABEL_PAD + (logo_w if logo_first else 0)
    for i, text in enumerate(labels):
        fig.add_annotation(
            xref="paper", yref="y", x=0, y=i, xshift=label_shift,
            xanchor="left", yanchor="middle", align="left", showarrow=False,
            text=text, font=dict(size=size, color=color),
        )
    if logos:
        if logo_first:
            meta = dict(logo_px=logo_px, logo_left_px=LABEL_PAD)
            x0, anchor = -(margin_l - LABEL_PAD) / est_plot_w, "left"
        else:
            meta = dict(logo_px=logo_px, logo_axis_gap_px=LABEL_GAP)
            x0, anchor = -LABEL_GAP / est_plot_w, "right"
        fig.update_layout(
            meta=meta,
            images=[
                dict(source=logo, xref="paper", yref="y", x=x0, y=i, sizex=logo_px / est_plot_w,
                     sizey=sizey, xanchor=anchor, yanchor="middle", sizing="contain", layer="above")
                for i, logo in enumerate(logos)
            ],
        )
    return margin_l


def _label_width(labels: list[str], size: int) -> int:
    """Rough rendered width of the longest label in Titillium Web (a fairly narrow face)."""
    longest = max((len(re.sub(r"<[^>]+>", "", l)) for l in labels), default=0)
    return int(longest * size * 0.42) + 10


def team_bar_figure(totals: pd.DataFrame, selected: str | None, theme: str = "light",
                    league_avg: float | None = None) -> go.Figure:
    """Horizontal bars of total miles per traveling team, colored by conference.

    Rows are labelled with the team abbreviation plus the primary team logo
    (nflverse `team_logo_espn`). `totals` columns: away_team, away_team_abbr,
    away_conf, logo_url, miles.
    """
    t = THEMES[theme]
    colors = conf_colors(theme)
    totals = totals.sort_values("miles", ascending=True).reset_index(drop=True)
    abbrs = totals["away_team_abbr"].tolist()
    is_sel = totals["away_team_abbr"] == selected
    row_px = 26

    fig = go.Figure(go.Bar(
        x=totals["miles"], y=list(range(len(totals))), orientation="h",
        customdata=totals["away_team_abbr"], hovertext=totals["away_team"],
        # Muted bars are solid blends (not translucent) so the average line stays hidden behind them.
        marker=dict(
            color=[colors[c] if s or selected is None else _blend(colors[c], t["surface"], 0.55)
                   for c, s in zip(totals["away_conf"], is_sel)],
            line=dict(width=[2 if s else 0 for s in is_sel], color=t["ink"]),
        ),
        # Labels sit inside the bar ends so the league-average line never crosses text.
        text=[f"{m:,}" for m in totals["miles"]], textposition="inside", insidetextanchor="end",
        textangle=0, constraintext="none",
        textfont=dict(size=12, color=["#ffffff" if s else t["ink"] for s in is_sel]),
        hovertemplate="<b>%{hovertext}</b><br>%{x:,} miles<extra>Click to select</extra>",
    ))

    # Row column: [logo][abbr] flush left, then the bar.
    margin_l = _logo_label_column(
        fig, totals["logo_url"].tolist(), [f"<b>{a}</b>" if a == selected else a for a in abbrs],
        t["ink2"], size=12, logo_px=24, sizey=0.86, est_plot_w=420,
    )

    if league_avg:
        fig.add_shape(type="line", xref="x", yref="paper", x0=league_avg, x1=league_avg, y0=0, y1=1,
                      line=dict(color=t["ink2"], width=1.5, dash="dash"), layer="below")
        fig.add_annotation(xref="x", yref="paper", x=league_avg, y=0, yanchor="top", showarrow=False,
                           text=f"League avg {league_avg:,.0f} mi", font=dict(size=11, color=t["ink2"]))

    fig.update_layout(**_base_layout(
        theme, bargap=0.28, height=max(320, row_px * len(totals) + 60),
        margin=dict(l=margin_l, r=56, t=4, b=26),
        xaxis=dict(showgrid=True, gridcolor=t["grid"], zeroline=False, tickformat="~s", side="top",
                   ticksuffix=" mi", tickfont=dict(color=t["muted"], size=11)),
        yaxis=dict(showgrid=False, showticklabels=False, range=[-0.6, len(totals) - 0.4]),
    ))
    return fig


def carrier_bar_figure(carriers: pd.DataFrame, metric: str = "miles", theme: str = "light") -> go.Figure:
    """Horizontal bars per airline, labelled by ICAO code + logo; the full name is in the tooltip.

    `carriers` columns: airline, miles, flights, [code], [logo].
    """
    t = THEMES[theme]
    carriers = carriers.sort_values(metric, ascending=True).reset_index(drop=True)
    other = "flights" if metric == "miles" else "miles"
    n = len(carriers)
    fig = go.Figure(go.Bar(
        x=carriers[metric], y=list(range(n)), orientation="h",
        customdata=carriers[other], hovertext=carriers["airline"],
        marker=dict(color=t["accent"]),
        text=[f"{v:,}" for v in carriers[metric]], textposition="outside", cliponaxis=False,
        textfont=dict(size=12, color=t["ink2"]),
        hovertemplate=(
            "<b>%{hovertext}</b><br>%{x:,} " + metric + "<br>%{customdata:,} " + other + "<extra></extra>"
        ),
    ))
    # Row column: [code] flush left, then [logo] against the bar.
    labels = (carriers["code"] if "code" in carriers else carriers["airline"]).tolist()
    margin_l = _logo_label_column(
        fig, carriers["logo"].tolist() if "logo" in carriers else None, labels,
        t["ink2"], size=12, logo_px=44, sizey=0.72, est_plot_w=380, logo_first=False,
    )
    fig.update_layout(**_base_layout(
        theme, bargap=0.3, height=max(260, 34 * n + 40),
        margin=dict(l=margin_l, r=56, t=4, b=8),
        xaxis=dict(showgrid=True, gridcolor=t["grid"], zeroline=False,
                   tickformat="~s", tickfont=dict(color=t["muted"], size=11)),
        yaxis=dict(showgrid=False, showticklabels=False, range=[-0.6, n - 0.4]),
    ))
    return fig
