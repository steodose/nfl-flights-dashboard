# NFL Charter Flights

A [Between the Pipes](https://betweenthepipes.substack.com) project: an interactive Plotly Dash dashboard of NFL team charter flights. It's a rebuild of the original [Tableau Public dashboard](https://public.tableau.com/app/profile/stephan.teodosescu/viz/NFLCharterFlights-2/Dashboard) (screenshot: `Dashboard-2.png`).

**Data:** [`steodose/nfl-flights`](https://github.com/steodose/nfl-flights) (`inst/extdata/charter_flights.csv`), sourced from Doug Kroll / [Jet Tip](https://blog.jettip.net).

## Features

- Team, season and leg (outbound/return) filters
- KPI cards with league rank and comparison to the league average
- Great-circle route map on a dark basemap with country labels
- Flight table with opponent helmets; click a row to highlight that leg on the map
- "Who's flying most?" ranking with team logos and a league-average line (click a bar to select a team)
- Carrier ranking by miles or flights, for all teams or the selected team
- PNG export per card or for the whole dashboard, and CSV export per table/chart
- Light/dark theme

## Run locally

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python app.py      # http://127.0.0.1:8050
```

## Project layout

| Path | Purpose |
| --- | --- |
| `app.py` | Layout and callbacks; exposes `server` for gunicorn / Plotly Cloud |
| `data.py` | Fetches the CSV from GitHub (cached 6h) with a fallback to `data/charter_flights.csv`; logo URLs; great-circle helper |
| `figures.py` | Map, team bars and carrier bars (light/dark aware) |
| `assets/style.css` | Theme tokens and layout (Titillium Web) |
| `assets/export.js` | PNG export (html2canvas for the HTML; charts rasterised with inlined images and fonts; maps copied from their WebGL canvas) |
| `assets/logo-column.js` | Keeps bar-chart logo columns pinned at a fixed pixel offset |
| `assets/dashAgGridComponentFunctions.js` | Helmet + team-name cell renderer for the flight table |
| `assets/airlines/`, `assets/teams/`, `assets/helmets/` | Bundled airline logos, team logos and helmets (served same-origin so PNG export works in Safari) |

## Data refresh

The deployed app re-reads the source CSV from GitHub at most every 6 hours, so new weeks appear without a redeploy. `data/charter_flights.csv` is only a fallback snapshot; refresh it occasionally:

```bash
curl -sL https://raw.githubusercontent.com/steodose/nfl-flights/main/inst/extdata/charter_flights.csv -o data/charter_flights.csv
```

## Deploy

- **Plotly Cloud:** `app.py` is the entry point and `requirements.txt` lists the dependencies.
- **Other hosts:** `gunicorn app:server`.

## Credits

Viz: Stephan Teodosescu · Data: Doug Kroll (Jet Tip) · Team logos and helmets via nflverse/ESPN and [`steodose/NFL`](https://github.com/steodose/NFL)
