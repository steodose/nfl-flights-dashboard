"""NFL Charter Flights — Dash rebuild of the Tableau Public dashboard."""
from __future__ import annotations

import dash_ag_grid as dag
import pandas as pd
from dash import Dash, Input, Output, State, dcc, html, no_update

import figures
from data import load_flights, logo_url, teams

DEFAULT_TEAM = "SF"
BTP_URL = "https://betweenthepipes.substack.com"
SITE_URL = "https://stephanteodosescu.com"
SOCIALS = [
    ("Substack", BTP_URL),
    ("Website", SITE_URL),
    ("X / Twitter", "https://twitter.com/steodosescu"),
    ("GitHub", "https://github.com/steodose"),
    ("Source code", "https://github.com/steodose/nfl-flights-dashboard"),
]
FONTS = "https://fonts.googleapis.com/css2?family=Titillium+Web:wght@300;400;600;700&display=swap"

app = Dash(
    __name__,
    title="NFL Charter Flights",
    external_stylesheets=[FONTS],
    external_scripts=["https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"],
    meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}],
)
server = app.server  # for gunicorn / Plotly Cloud


# ---------------------------------------------------------------- helpers ---

def _filter(df: pd.DataFrame, season: int, direction: str, team: str | None = None) -> pd.DataFrame:
    out = df[df["season"] == season]
    if direction != "all":
        out = out[out["direction"] == direction]
    if team:
        out = out[out["away_team_abbr"] == team]
    return out


def _team_totals(df: pd.DataFrame, season: int, direction: str) -> pd.DataFrame:
    """Total miles for all 32 teams (zero if they have no recorded flights)."""
    legs = _filter(df, season, direction)
    miles = legs.groupby("away_team_abbr")["distance_mi"].sum()
    out = teams(df).copy()
    out["miles"] = out["away_team_abbr"].map(miles).fillna(0).astype(int)
    return out


def _kpi(label: str, value: str, sub: str = "") -> html.Div:
    return html.Div(className="kpi", children=[
        html.Div(label, className="kpi-label"),
        html.Div(value, className="kpi-value"),
        html.Div(sub, className="kpi-sub"),
    ])


def _export_buttons(target: str, name: str, csv_id: str | None = None) -> html.Div:
    """PNG button (client-side, assets/export.js) plus an optional server-side CSV button."""
    buttons = [html.Button("Download PNG", className="dl-btn", title="Download this card as a PNG",
                           **{"data-target": target, "data-name": name})]
    if csv_id:
        buttons.append(html.Button("Download CSV", id=f"{csv_id}-btn", className="csv-btn",
                                   title="Download this card's data as CSV", n_clicks=0))
        buttons.append(dcc.Download(id=f"{csv_id}-download"))
    return html.Div(buttons, className="dl-group", **{"data-html2canvas-ignore": "true"})


def _card_head(title, target: str, name: str, csv_id: str | None = None) -> html.Div:
    return html.Div(className="card-head", children=[title, _export_buttons(target, name, csv_id)])


# Bundled airline logos (assets/airlines). "Cardinals" is the Arizona Cardinals' own aircraft.
AIRLINE_LOGO_FILES = {
    "Delta Airlines": "airlines/delta.png",
    "United Airlines": "airlines/united.png",
    "Atlas Air": "airlines/atlas-air.png",
    "American Airlines": "airlines/american.png",
    "Virgin Atlantic Airlines": "airlines/virgin-atlantic.png",
    "Qantas": "airlines/qantas.png",
    "Aer Lingus": "airlines/aer-lingus.png",
    "Eastern Airlines": "airlines/eastern.png",
    "Omni Air International": "airlines/omni.png",
    "Unknown": "nfl-shield.png",
}


def _airline_logo(airline: str) -> str:
    if airline == "Cardinals":
        return logo_url("ARI")
    return app.get_asset_url(AIRLINE_LOGO_FILES.get(airline, "airlines/generic.svg"))


def _carrier_codes(df: pd.DataFrame) -> dict:
    """Most common 3-letter ICAO code per airline across all data (e.g. Delta -> DAL)."""
    icao = df[df["carrier_code"].fillna("").str.fullmatch(r"[A-Z]{3}")]
    codes = icao.groupby("airline")["carrier_code"].agg(lambda s: s.value_counts().index[0]).to_dict()
    codes["Unknown"] = "UNK"
    return codes


def _carrier_totals(df: pd.DataFrame, season: int, direction: str, team: str | None) -> pd.DataFrame:
    legs = _filter(df, season, direction, team)
    out = (legs.groupby("airline")
           .agg(miles=("distance_mi", "sum"), flights=("distance_mi", "size"))
           .reset_index())
    codes = _carrier_codes(df)
    out.insert(1, "code", out["airline"].map(lambda a: codes.get(a, a[:3].upper())))
    return out


def _csv_name(*parts) -> str:
    return "-".join(str(p).lower().replace(" ", "-") for p in ("nfl-charter-flights",) + parts if p) + ".csv"


def _team_total_sub(legs: pd.DataFrame, rank: int, n_teams: int, league_avg: float) -> str:
    sub = f"{_ordinal(rank)} of {n_teams}"
    if league_avg:
        sub += f" · {legs['distance_mi'].sum() / league_avg:.1f}× league avg"
    return sub


def _ordinal(n: int) -> str:
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


GRID_COLUMNS = [
    {"field": "week", "headerName": "Week", "width": 82, "type": "numericColumn"},
    # ISO strings sort correctly; shown as e.g. "Sun, Sep 7".
    {"field": "flight_date", "headerName": "Date", "width": 115,
     "valueFormatter": {"function": "params.value ? d3.timeFormat('%a, %b %-d')(d3.timeParse('%Y-%m-%d')(params.value)) : ''"}},
    {"field": "direction", "headerName": "Leg", "width": 100},
    {"field": "home_team", "headerName": "Opponent (Home)", "minWidth": 210, "flex": 2,
     "cellRenderer": "TeamHelmet"},
    {"field": "home_division", "headerName": "Home Division", "width": 130},
    {"field": "dep_airport", "headerName": "Dep", "width": 80},
    {"field": "arr_airport", "headerName": "Arr", "width": 80},
    {"field": "airline", "headerName": "Airline", "minWidth": 150, "flex": 1.5},
    {"field": "flight_number", "headerName": "Flight #", "width": 105},
    {"field": "aircraft_type", "headerName": "Aircraft", "width": 100},
    {"field": "distance_mi", "headerName": "Distance (mi)", "width": 130, "type": "numericColumn",
     "valueFormatter": {"function": "d3.format(',')(params.value)"}},
]


# ----------------------------------------------------------------- layout ---

def serve_layout():
    df = load_flights()
    team_df = teams(df)
    seasons = sorted(df["season"].unique(), reverse=True)
    refreshed = df["scraped_at"].max()
    refreshed_txt = refreshed.strftime("%-m/%-d/%Y") if pd.notna(refreshed) else "—"

    return html.Div(className="wrap", id="page", children=[
        dcc.Store(id="theme-store"),

        html.Div(className="topbar", **{"data-html2canvas-ignore": "true"}, children=[
            html.Div(className="opt", children=[
                html.B("Appearance"),
                dcc.RadioItems(
                    id="theme", value="light", inline=True, persistence=True, className="radio",
                    options=[{"label": "Light", "value": "light"}, {"label": "Dark", "value": "dark"}],
                ),
            ]),
        ]),

        html.Header(className="hdr", children=[
            html.Div(className="hdr-main", children=[
                html.Img(src=app.get_asset_url("nfl-shield.png"), className="nfl-shield", alt="NFL"),
                html.Div([
                    html.H1("NFL Charter Flights"),
                    html.Div("Between the Pipes · NFL Analytics Suite", className="eyebrow"),
                ]),
            ]),
            html.Div(className="badge-stack", children=[
                html.Button("Download dashboard", className="dl-btn dl-btn-strong", title="Download the full dashboard as PNG",
                            **{"data-target": "page", "data-name": "nfl-charter-flights-dashboard",
                               "data-html2canvas-ignore": "true"}),
                html.Span(f"Last refreshed {refreshed_txt}", className="pill"),
                html.Span("Regular season", className="pill pill-alt"),
            ]),
        ]),

        html.Div(className="controls", children=[
            html.Div(className="control control-team", children=[
                html.Label("Team", htmlFor="team"),
                html.Div(className="team-select", children=[
                    html.Img(id="team-logo", className="team-logo", alt=""),
                    dcc.Dropdown(
                        id="team", clearable=False, value=DEFAULT_TEAM, className="team-dropdown",
                        options=[{"label": r.away_team, "value": r.away_team_abbr} for r in team_df.itertuples()],
                    ),
                ]),
            ]),
            html.Div(className="control", children=[
                html.Label("Season", htmlFor="season"),
                dcc.Dropdown(id="season", clearable=False, value=int(seasons[0]),
                             options=[{"label": str(s), "value": int(s)} for s in seasons]),
            ]),
            html.Div(className="control", children=[
                html.Label("Legs"),
                dcc.RadioItems(
                    id="direction", value="all", inline=True, className="radio",
                    options=[{"label": "All", "value": "all"},
                             {"label": "Outbound", "value": "outbound"},
                             {"label": "Return", "value": "return"}],
                ),
            ]),
        ]),

        html.Div(id="kpis", className="kpis"),

        html.Div(className="card", id="card-map", children=[
            _card_head(html.H3(id="map-title"), "card-map", "nfl-charter-flights-map"),
            html.P("Great-circle routes. Hover a route for flight details; select a row in the table "
                   "below to highlight that leg.", className="hint"),
            dcc.Graph(id="map", style={"height": "560px"}, config={"displayModeBar": False, "scrollZoom": True}),
        ]),

        html.Div(className="card", id="card-table", children=[
            _card_head(html.H3(id="table-title"), "card-table", "nfl-charter-flights-table",
                       csv_id="csv-table"),
            dag.AgGrid(
                id="grid",
                columnDefs=GRID_COLUMNS,
                defaultColDef={"sortable": True, "resizable": True},
                dashGridOptions={
                    "rowSelection": {"mode": "singleRow", "checkboxes": False, "enableClickSelection": True},
                    "domLayout": "autoHeight",
                    "suppressCellFocus": True,
                    "rowHeight": 40,
                },
                getRowId="params.data.row_id",
                style={"width": "100%"},
            ),
        ]),

        html.Div(className="grid-2", children=[
            html.Div(className="card", id="card-teams", children=[
                _card_head(html.H3("Who’s flying most?"), "card-teams", "nfl-charter-flights-by-team",
                           csv_id="csv-teams"),
                html.P(className="hint", children=[
                    "Total miles by team. ",
                    html.Span("■ AFC", className="sw sw-afc"), " ",
                    html.Span("■ NFC", className="sw sw-nfc"),
                    " · Click a bar to select that team.",
                ]),
                html.P(id="league-note", className="league-note"),
                html.Div(className="scroll", children=dcc.Graph(id="team-bars", config={"displayModeBar": False})),
            ]),
            html.Div(className="card", id="card-carriers", children=[
                _card_head(html.H3("Most popular carriers"), "card-carriers", "nfl-charter-flights-carriers",
                           csv_id="csv-carriers"),
                html.Div(className="card-controls", children=[
                    dcc.RadioItems(id="carrier-metric", value="miles", inline=True, className="radio",
                                   options=[{"label": "Miles", "value": "miles"},
                                            {"label": "Flights", "value": "flights"}]),
                    dcc.RadioItems(id="carrier-scope", value="league", inline=True, className="radio",
                                   options=[{"label": "All teams", "value": "league"},
                                            {"label": "Selected team", "value": "team"}]),
                ]),
                dcc.Graph(id="carrier-bars", config={"displayModeBar": False}),
            ]),
        ]),

        html.Footer(className="ftr", children=[
            html.A(html.Img(src=app.get_asset_url("btp-logo.png"), alt="Between the Pipes"),
                   className="btp-badge", href=BTP_URL, target="_blank", rel="noopener",
                   title="A Between the Pipes project"),
            html.Div(className="footer-text", children=[
                html.Div([
                    "A ", html.A(html.Strong("Between the Pipes"), href=BTP_URL, target="_blank", rel="noopener"),
                    " project by ", html.A("Stephan Teodosescu", href=SITE_URL, target="_blank", rel="noopener"),
                    " · Data: Doug Kroll (", html.A("Jet Tip", href="https://blog.jettip.net", target="_blank",
                                                     rel="noopener"),
                    ") via ", html.A("nfl-flights", href="https://github.com/steodose/nfl-flights",
                                     target="_blank", rel="noopener"),
                    " · Built with Plotly Dash",
                ]),
                html.Div(className="socials", children=[
                    html.A(label, href=url, target="_blank", rel="noopener") for label, url in SOCIALS
                ]),
            ]),
        ]),
    ])


app.layout = serve_layout


# -------------------------------------------------------------- callbacks ---

app.clientside_callback(
    """
    function(theme) {
        document.documentElement.setAttribute('data-theme', theme || 'light');
        return theme || 'light';
    }
    """,
    Output("theme-store", "data"),
    Input("theme", "value"),
)


@app.callback(
    Output("team-logo", "src"),
    Output("kpis", "children"),
    Output("map-title", "children"),
    Output("table-title", "children"),
    Output("grid", "rowData"),
    Output("team-bars", "figure"),
    Output("league-note", "children"),
    Input("team", "value"),
    Input("season", "value"),
    Input("direction", "value"),
    Input("theme-store", "data"),
)
def update_team_view(team, season, direction, theme):
    theme = theme or "light"
    df = load_flights()
    team_row = teams(df).set_index("away_team_abbr").loc[team]
    name = team_row["away_team"]

    legs = _filter(df, season, direction, team)
    totals = _team_totals(df, season, direction)
    ranked = totals.sort_values("miles", ascending=False).reset_index(drop=True)
    rank = int(ranked.index[ranked["away_team_abbr"] == team][0]) + 1
    n_teams = len(ranked)

    # League context: total and per-team average for the same season / leg filter.
    league_total = int(totals["miles"].sum())
    league_avg = league_total / n_teams if n_teams else 0
    season_df = df[df["season"] == season]
    in_progress = season == int(df["season"].max()) and int(season_df["week"].max()) < 18
    through = f" (through Week {int(season_df['week'].max())})" if in_progress and len(season_df) else ""
    league_note = [
        "League total: ", html.B(f"{league_total:,} mi"),
        " · avg ", html.B(f"{league_avg:,.0f}"), f" per team{through}",
    ]

    if legs.empty:
        kpis = [_kpi("Total miles", "0"), _kpi("Flight legs", "0"),
                _kpi("Longest leg", "—"), _kpi("Airlines used", "0")]
    else:
        longest = legs.loc[legs["distance_mi"].idxmax()]
        airlines = legs["airline"].value_counts()
        kpis = [
            _kpi("Total miles", f"{int(legs['distance_mi'].sum()):,}", _team_total_sub(legs, rank, n_teams, league_avg)),
            _kpi("Flight legs", f"{len(legs)}", f"{legs['week'].nunique()} road trips"),
            _kpi("Longest leg", f"{int(longest['distance_mi']):,} mi",
                 f"{longest['dep_airport']} → {longest['arr_airport']} · Week {longest['week']}"),
            _kpi("Airlines used", f"{len(airlines)}", f"Mostly {airlines.index[0]}"),
        ]

    leg_label = "" if direction == "all" else f" · {direction.title()} legs"
    grid_rows = legs[[c["field"] for c in GRID_COLUMNS] + ["row_id", "home_helmet"]].assign(
        direction=lambda d: d["direction"].str.title(),
        flight_date=lambda d: d["flight_date"].dt.strftime("%Y-%m-%d"),
        row_id=lambda d: d["row_id"].astype(str),  # AG Grid row IDs must be strings
    ).to_dict("records")

    return (
        team_row["logo_url"],
        kpis,
        f"Where the {name} flew in {season}{leg_label}",
        f"Flight info ({name})",
        grid_rows,
        figures.team_bar_figure(totals, team, theme, league_avg),
        league_note,
    )


@app.callback(
    Output("map", "figure"),
    Input("team", "value"),
    Input("season", "value"),
    Input("direction", "value"),
    Input("grid", "selectedRows"),
    Input("theme-store", "data"),
)
def update_map(team, season, direction, selected_rows, theme):
    legs = _filter(load_flights(), season, direction, team)
    highlight = [int(r["row_id"]) for r in (selected_rows or [])]
    return figures.map_figure(legs, theme or "light", highlight)


@app.callback(
    Output("carrier-bars", "figure"),
    Input("season", "value"),
    Input("direction", "value"),
    Input("carrier-metric", "value"),
    Input("carrier-scope", "value"),
    Input("team", "value"),
    Input("theme-store", "data"),
)
def update_carriers(season, direction, metric, scope, team, theme):
    carriers = _carrier_totals(load_flights(), season, direction, team if scope == "team" else None)
    carriers["logo"] = carriers["airline"].map(_airline_logo)
    return figures.carrier_bar_figure(carriers, metric, theme or "light")


# ------------------------------------------------------------ CSV export ---

TABLE_CSV_COLUMNS = {
    "season": "season", "week": "week", "flight_date": "flight_date", "direction": "leg",
    "away_team": "team", "home_team": "opponent_home", "home_division": "home_division",
    "dep_airport": "dep_airport", "arr_airport": "arr_airport", "airline": "airline",
    "flight_number": "flight_number", "aircraft_type": "aircraft_type", "distance_mi": "distance_mi",
}


@app.callback(
    Output("csv-table-download", "data"),
    Input("csv-table-btn", "n_clicks"),
    State("team", "value"),
    State("season", "value"),
    State("direction", "value"),
    prevent_initial_call=True,
)
def download_table_csv(_, team, season, direction):
    legs = _filter(load_flights(), season, direction, team)
    out = legs[list(TABLE_CSV_COLUMNS)].rename(columns=TABLE_CSV_COLUMNS)
    out["flight_date"] = out["flight_date"].dt.strftime("%Y-%m-%d")
    name = _csv_name(team, season, None if direction == "all" else direction)
    return dcc.send_data_frame(out.to_csv, name, index=False)


@app.callback(
    Output("csv-teams-download", "data"),
    Input("csv-teams-btn", "n_clicks"),
    State("season", "value"),
    State("direction", "value"),
    prevent_initial_call=True,
)
def download_teams_csv(_, season, direction):
    totals = _team_totals(load_flights(), season, direction)
    avg = totals["miles"].mean()
    out = (totals.sort_values("miles", ascending=False)
           .assign(rank=lambda d: range(1, len(d) + 1),
                   vs_league_avg=lambda d: (d["miles"] / avg).round(2) if avg else None)
           [["rank", "away_team", "away_team_abbr", "away_conf", "miles", "vs_league_avg"]]
           .rename(columns={"away_team": "team", "away_team_abbr": "abbr", "away_conf": "conference"}))
    name = _csv_name("by-team", season, None if direction == "all" else direction)
    return dcc.send_data_frame(out.to_csv, name, index=False)


@app.callback(
    Output("csv-carriers-download", "data"),
    Input("csv-carriers-btn", "n_clicks"),
    State("season", "value"),
    State("direction", "value"),
    State("carrier-scope", "value"),
    State("team", "value"),
    prevent_initial_call=True,
)
def download_carriers_csv(_, season, direction, scope, team):
    scoped_team = team if scope == "team" else None
    out = (_carrier_totals(load_flights(), season, direction, scoped_team)
           .sort_values("miles", ascending=False))
    name = _csv_name("carriers", scoped_team, season, None if direction == "all" else direction)
    return dcc.send_data_frame(out.to_csv, name, index=False)


@app.callback(
    Output("team", "value"),
    Input("team-bars", "clickData"),
    State("team", "value"),
    prevent_initial_call=True,
)
def select_team_from_bar(click, current):
    if not click:
        return no_update
    abbr = click["points"][0].get("customdata")
    return abbr if abbr and abbr != current else no_update


if __name__ == "__main__":
    app.run(debug=True)
