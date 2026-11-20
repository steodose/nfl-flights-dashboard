"""Data loading, cleaning and geometry helpers for the NFL Charter Flights dashboard."""
from __future__ import annotations

import logging
import time
from io import StringIO
from pathlib import Path

import numpy as np
import pandas as pd
import requests

log = logging.getLogger(__name__)

DATA_URL = (
    "https://raw.githubusercontent.com/steodose/nfl-flights/main/"
    "inst/extdata/charter_flights.csv"
)
FALLBACK_PATH = Path(__file__).parent / "data" / "charter_flights.csv"
CACHE_TTL_SECONDS = 6 * 60 * 60

# Team logos (ESPN CDN) and helmets (steodose/NFL) are bundled in assets/ at reduced size.
# Serving them same-origin keeps PNG export working in Safari, which refuses to draw
# cross-origin images onto a canvas.
_ASSETS = Path(__file__).parent / "assets"

_cache = {"df": None, "loaded_at": 0.0, "source": None}


def logo_url(abbr: str) -> str:
    return f"/assets/teams/{abbr}.png"


def helmet_url(abbr: str) -> str:
    """Right-facing team helmet (nflverse abbreviations), bundled from the steodose/NFL repo."""
    return f"/assets/helmets/{abbr}.png" if (_ASSETS / "helmets" / f"{abbr}.png").exists() else ""


def _read_remote() -> pd.DataFrame:
    resp = requests.get(DATA_URL, timeout=10)
    resp.raise_for_status()
    return pd.read_csv(StringIO(resp.text))


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns={"Row ID": "row_id"}).copy()
    if "row_id" not in df.columns:
        df["row_id"] = range(1, len(df) + 1)
    df["flight_date"] = pd.to_datetime(df["flight_date"], errors="coerce")
    df["scraped_at"] = pd.to_datetime(df["scraped_at"], errors="coerce")
    df["airline"] = df["airline"].fillna("").str.strip().replace("", "Unknown")
    df["aircraft_type"] = df["aircraft_type"].fillna("")
    df["flight_number"] = df["flight_number"].fillna("")
    df["home_division"] = df["home_division"].fillna("")
    df["distance_mi"] = pd.to_numeric(df["distance_mi"], errors="coerce").fillna(0).astype(int)
    df["season"] = df["season"].astype(int)
    df["week"] = df["week"].astype(int)
    df["leg_seq"] = pd.to_numeric(df["leg_seq"], errors="coerce").fillna(1).astype(int)
    df["logo_url"] = df["away_team_abbr"].map(logo_url)
    df["home_helmet"] = df["home_team_abbr"].map(helmet_url)
    df = df.dropna(subset=["dep_lat", "dep_lon", "arr_lat", "arr_lon"])
    # Outbound before return within a week.
    df["_dir_order"] = (df["direction"] == "return").astype(int)
    df = df.sort_values(["season", "week", "away_team", "_dir_order", "leg_seq"])
    return df.drop(columns="_dir_order").reset_index(drop=True)


def load_flights(force: bool = False) -> pd.DataFrame:
    """Return the flights table, refreshing from GitHub at most every CACHE_TTL_SECONDS.

    Falls back to the last good copy in memory, then to the bundled CSV snapshot.
    """
    now = time.time()
    fresh = _cache["df"] is not None and now - _cache["loaded_at"] < CACHE_TTL_SECONDS
    if fresh and not force:
        return _cache["df"]

    try:
        df = _clean(_read_remote())
        source = "github"
    except Exception as exc:  # network error, bad CSV, etc.
        log.warning("Remote fetch failed (%s); using fallback data", exc)
        if _cache["df"] is not None:
            _cache["loaded_at"] = now  # back off before retrying
            return _cache["df"]
        df = _clean(pd.read_csv(FALLBACK_PATH))
        source = "local"

    _cache.update(df=df, loaded_at=now, source=source)
    return df


def data_source() -> str | None:
    return _cache["source"]


def teams(df: pd.DataFrame) -> pd.DataFrame:
    """One row per traveling team with name, abbr, conference and logo."""
    return (
        df[["away_team", "away_team_abbr", "away_conf", "logo_url"]]
        .drop_duplicates("away_team_abbr")
        .sort_values("away_team")
        .reset_index(drop=True)
    )


def great_circle(lat1, lon1, lat2, lon2, n: int = 48):
    """Points along the great circle between two coordinates.

    Longitudes are unwrapped so that trans-Pacific routes draw as one
    continuous arc instead of jumping across the map.
    """
    p1, l1, p2, l2 = map(np.radians, (lat1, lon1, lat2, lon2))
    a = np.array([np.cos(p1) * np.cos(l1), np.cos(p1) * np.sin(l1), np.sin(p1)])
    b = np.array([np.cos(p2) * np.cos(l2), np.cos(p2) * np.sin(l2), np.sin(p2)])
    omega = np.arccos(np.clip(np.dot(a, b), -1.0, 1.0))
    if omega < 1e-9:
        return [lat1, lat2], [lon1, lon2]
    t = np.linspace(0, 1, n)[:, None]
    pts = (np.sin((1 - t) * omega) * a + np.sin(t * omega) * b) / np.sin(omega)
    lats = np.degrees(np.arctan2(pts[:, 2], np.hypot(pts[:, 0], pts[:, 1])))
    lons = np.degrees(np.unwrap(np.arctan2(pts[:, 1], pts[:, 0])))
    return lats.tolist(), lons.tolist()
