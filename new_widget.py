"""
Baseball Performance Widget (iScore API)
-----------------------------------------
Migrated from Pointstreak to iScore Sports API.
Preserves all original UI, columns, percentile rankings, and hot/cold indicators.

Endpoint mapping (Pointstreak → iScore):
  - Teams of league       → GET /public/leagues/{leagueGuid}/teams
  - Players of team       → GET /public/teams/{teamGuid}/players
  - Games by league       → GET /public/games?leagueGuid=...
  - Player stats          → GET /player-stats?TeamId=...&SeasonId=...
  - Player games          → GET /public/player/games?PlayerGuid=...&SeasonGuid=...
  - Batting leaderboard   → GET /api/leaderboard/player/batting
  - Pitching leaderboard  → GET /api/leaderboard/player/pitching
  - Fielding leaderboard  → GET /api/leaderboard/player/fielding

Dependencies:
  streamlit, pandas, requests, reportlab, zoneinfo
"""

# -------------------------
# Imports and Configuration
# -------------------------

import streamlit as st
import pandas as pd
import requests
from datetime import datetime
from reportlab.lib.pagesizes import LETTER, landscape
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
import os
from io import BytesIO
from zoneinfo import ZoneInfo
from dotenv import load_dotenv


# -------------------
# PDF Generation
# -------------------

def generate_pdf(df, title, subtitle, selected_cols):
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=landscape(LETTER),
        leftMargin=24, rightMargin=24, topMargin=24, bottomMargin=24
    )
    elements = []
    styles = getSampleStyleSheet()

    custom_title_style = ParagraphStyle(
        name="CustomTitle", parent=styles["Title"],
        textColor=colors.HexColor("#000c66"), fontSize=14, alignment=1
    )
    subtitle_style = ParagraphStyle(
        name="SubtitleStyle", parent=styles["Normal"],
        textColor=colors.HexColor("#c62127"), fontSize=9, alignment=1
    )
    date_style = ParagraphStyle(
        name="DateStyle", parent=styles["Normal"],
        textColor=colors.HexColor("#000c66"), fontSize=7, alignment=1
    )

    now = datetime.now(ZoneInfo("America/New_York"))
    elements.append(Paragraph(now.strftime("Report Date: %B %d, %Y at %I:%M %p"), date_style))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph(title, custom_title_style))
    elements.append(Spacer(1, 4))
    elements.append(Paragraph(subtitle, subtitle_style))
    elements.append(Spacer(1, 14))

    display_df = df[selected_cols].copy()

    HOT_COLOR  = colors.HexColor("#d64e4e")
    COLD_COLOR = colors.HexColor("#316daa")

    raw_data    = display_df.values.tolist()
    cell_colors = {}

    cleaned_data = []
    for row_i, row in enumerate(raw_data):
        cleaned_row = []
        for col_i, cell in enumerate(row):
            cell_str = str(cell)
            if cell_str.startswith("🔥"):
                cell_colors[(row_i + 1, col_i)] = HOT_COLOR
                cell_str = cell_str.replace("🔥 ", "").replace("🔥", "")
            elif cell_str.startswith("🧊"):
                cell_colors[(row_i + 1, col_i)] = COLD_COLOR
                cell_str = cell_str.replace("🧊 ", "").replace("🧊", "")
            cleaned_row.append(cell_str)
        cleaned_data.append(cleaned_row)

    data      = [display_df.columns.tolist()] + cleaned_data
    col_count = len(selected_cols)
    col_width = 720 / col_count

    table = Table(data, repeatRows=1, colWidths=[col_width] * col_count)

    table_style = [
        ("BACKGROUND",     (0, 0), (-1, 0),  colors.HexColor("#0072eb")),
        ("TEXTCOLOR",      (0, 0), (-1, 0),  colors.white),
        ("ALIGN",          (0, 0), (-1, -1), "CENTER"),
        ("FONTNAME",       (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTNAME",       (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE",       (0, 0), (-1, 0),  9),
        ("FONTSIZE",       (0, 1), (-1, -1), 8),
        ("BOTTOMPADDING",  (0, 0), (-1, 0),  8),
        ("BOTTOMPADDING",  (0, 1), (-1, -1), 6),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#eef3fb")]),
        ("GRID",           (0, 0), (-1, -1), 0.25, colors.black),
    ]

    for (row_i, col_i), color in cell_colors.items():
        table_style.append(("BACKGROUND", (col_i, row_i), (col_i, row_i), color))

    table.setStyle(TableStyle(table_style))
    elements.append(table)
    doc.build(elements)
    buffer.seek(0)
    return buffer


def pdf_filename(label):
    now = datetime.now(ZoneInfo("America/New_York"))
    return f"{label}_{now.strftime('%Y-%m-%d_%H-%M')}.pdf"


# -------------------
# iScore API Setup
# -------------------

BASE_URL = "https://api.microservices.iscoresports.com/api"

# ── Set your league and season GUIDs here ──────────────────────────────────────
LEAGUE_GUID = os.getenv("LEAGUE_GUID")
SEASON_GUID = os.getenv("SEASON_GUID")
# ───────────────────────────────────────────────────────────────────────────────

HEADERS = {"Content-Type": "application/json"}


# -------------------
# API Fetch Helper
# -------------------

def fetch(endpoint, params=None):
    """GET {BASE_URL}/{endpoint} with optional query params."""
    url = f"{BASE_URL}/{endpoint}"
    try:
        resp = requests.get(url, headers=HEADERS, params=params)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        st.error(f"Error fetching {url}: {e}")
        return {}


# ─────────────────────────────────────────────
# Data-fetch functions (iScore endpoints)
# ─────────────────────────────────────────────

# GET /public/leagues/{leagueGuid}/teams
@st.cache_data
def get_league_teams():
    """Returns DataFrame of all teams in the configured league."""
    data = fetch(f"public/leagues/{LEAGUE_GUID}/teams")
    if not data:
        return pd.DataFrame()
    teams = data if isinstance(data, list) else data.get("items", data.get("data", []))
    df = pd.DataFrame(teams)
    # Normalise to known column names used downstream
    rename_map = {
        "guid":      "team_guid",
        "id":        "team_guid",       # fallback
        "name":      "TEAM",
        "shortName": "SHORT_NAME",
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
    return df


# GET /public/teams/{teamGuid}/players
@st.cache_data
def get_team_players(team_guid):
    """Returns DataFrame of players for a given team."""
    data = fetch(f"public/teams/{team_guid}/players")
    if not data:
        return pd.DataFrame()
    players = data if isinstance(data, list) else data.get("items", data.get("data", []))
    df = pd.DataFrame(players)
    rename_map = {
        "guid":        "player_id",
        "id":          "player_id",
        "name":        "PLAYER",
        "throwsHand":  "PITCH HAND",
        "bats":        "BAT HAND",
        "number":      "JERSEY",
        "position":    "POSITION",
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
    return df


# GET /public/games?leagueGuid=...
@st.cache_data
def get_all_games():
    """Returns all games for the configured league/season."""
    data = fetch("public/games", params={"leagueGuid": LEAGUE_GUID, "Take": 1000})
    if not data:
        return pd.DataFrame()
    games = data if isinstance(data, list) else data.get("items", data.get("data", []))
    return pd.DataFrame(games)


# GET /public/player/games?PlayerGuid=...&SeasonGuid=...
@st.cache_data
def get_player_games(player_guid):
    """Returns games played by a specific player this season."""
    data = fetch(
        "public/player/games",
        params={"PlayerGuid": player_guid, "SeasonGuid": SEASON_GUID}
    )
    if not data:
        return pd.DataFrame()
    games = data if isinstance(data, list) else data.get("items", data.get("data", []))
    return pd.DataFrame(games)


# GET /player-stats?TeamId=...&SeasonId=...
@st.cache_data
def get_team_player_stats(team_guid):
    """Returns raw player stats rows for every player on a team."""
    data = fetch("player-stats", params={"TeamId": team_guid, "SeasonId": SEASON_GUID})
    if not data:
        return pd.DataFrame()
    rows = data if isinstance(data, list) else data.get("items", data.get("data", []))
    return pd.DataFrame(rows)


# GET /api/leaderboard/player/batting
@st.cache_data
def get_batting_leaderboard(team_guid=None):
    params = {
        "SeasonId": SEASON_GUID,
        "LeagueId": LEAGUE_GUID,
        "SortBy":   "OPS",
        "Size":     200,
    }
    if team_guid:
        params["TeamId"] = team_guid
    data = fetch("leaderboard/player/batting", params=params)
    items = data.get("items", []) if data else []
    rows = []
    for player in items:
        stats = player.get("stats", {})
        rows.append({
            "BATTER":      f"{player.get('firstName', '')} {player.get('lastName', '')}".strip(),
            "player_id":   player.get("playerGuid") or player.get("guid") or player.get("id"),
            "team_guid":   player.get("teamGuid")   or player.get("teamId"),
            "TEAM":        player.get("teamName",   ""),
            "AVG":         stats.get("avg")         or stats.get("battingAverage"),
            "OBP":         stats.get("obp")         or stats.get("onBasePercentage"),
            "SLG":         stats.get("slg")         or stats.get("sluggingPercentage"),
            "OPS":         stats.get("ops")         or stats.get("onBasePlusSlugging"),
            "HR":          stats.get("hr")          or stats.get("homeRuns"),
            "H":           stats.get("hits"),
            "AB":          stats.get("ab")          or stats.get("atBats"),
            "BB":          stats.get("walks")       or stats.get("bb"),
            "SO":          stats.get("strikeouts")  or stats.get("so"),
            "HBP":         stats.get("hbp")         or stats.get("hitByPitch"),
            "G":           stats.get("gamesPlayed") or stats.get("g"),
        })
    return pd.DataFrame(rows)


# GET /api/leaderboard/player/pitching
@st.cache_data
def get_pitching_leaderboard(team_guid=None):
    params = {
        "SeasonId": SEASON_GUID,
        "LeagueId": LEAGUE_GUID,
        "SortBy":   "ERA",
        "Size":     200,
    }
    if team_guid:
        params["TeamId"] = team_guid
    data = fetch("leaderboard/player/pitching", params=params)
    items = data.get("items", []) if data else []
    rows = []
    for player in items:
        stats = player.get("stats", {})
        rows.append({
            "PITCHER":   f"{player.get('firstName', '')} {player.get('lastName', '')}".strip(),
            "player_id": player.get("playerGuid") or player.get("guid") or player.get("id"),
            "team_guid": player.get("teamGuid")   or player.get("teamId"),
            "TEAM":      player.get("teamName",   ""),
            "IP":        stats.get("inningsPitched"),
            "SO":        stats.get("strikeouts")  or stats.get("so"),
            "BB":        stats.get("walks")       or stats.get("bb"),
            "H":         stats.get("hits"),
            "HR":        stats.get("homeRuns")    or stats.get("hr"),
            "R":         stats.get("runs")        or stats.get("r"),
            "ERA":       stats.get("era"),
            "WHIP":      stats.get("whip"),
            "G":         stats.get("gamesPlayed") or stats.get("g"),
            "NP":        stats.get("pitchCount")  or stats.get("np"),
        })
    return pd.DataFrame(rows)


# GET /api/leaderboard/player/fielding
@st.cache_data
def get_fielding_leaderboard(team_guid=None):
    params = {
        "SeasonId": SEASON_GUID,
        "LeagueId": LEAGUE_GUID,
        "SortBy":   "FPCT",
        "Size":     200,
    }
    if team_guid:
        params["TeamId"] = team_guid
    data = fetch("leaderboard/player/fielding", params=params)
    items = data.get("items", []) if data else []
    rows = []
    for player in items:
        stats = player.get("stats", {})
        rows.append({
            "FIELDER":   f"{player.get('firstName', '')} {player.get('lastName', '')}".strip(),
            "player_id": player.get("playerGuid") or player.get("guid") or player.get("id"),
            "team_guid": player.get("teamGuid")   or player.get("teamId"),
            "TEAM":      player.get("teamName",   ""),
            "PO":        stats.get("putouts")     or stats.get("po"),
            "A":         stats.get("assists")     or stats.get("a"),
            "E":         stats.get("errors")      or stats.get("e"),
            "FPCT":      stats.get("fieldingPct") or stats.get("fpct"),
            "G":         stats.get("gamesPlayed") or stats.get("g"),
            "INN":       stats.get("innings")     or stats.get("inn"),
        })
    return pd.DataFrame(rows)


# ─────────────────────────────────────────────
# Per-game stat builders from player-stats
# ─────────────────────────────────────────────

def build_hitter_game_log(player_stats_df, player_guid, games_df, selected_team):
    """
    Build a per-game batting log for an individual hitter from the /player-stats response.
    The iScore /player-stats endpoint returns one row per player (season totals) *or*
    one row per player per game — exact shape depends on the league config.
    We handle both: if a 'gameGuid'/'gameId' column is present we use it directly;
    otherwise we fall back to season totals as a single-row log.
    """
    df = player_stats_df[
        (player_stats_df.get("playerGuid", player_stats_df.get("player_id", pd.Series(dtype=str))) == player_guid)
        | (player_stats_df.get("player_id", pd.Series(dtype=str)) == player_guid)
    ].copy()

    if df.empty:
        return pd.DataFrame()

    # Normalise column names
    col_rename = {
        "gameGuid": "GAME_ID", "gameId": "GAME_ID", "game_id": "GAME_ID",
        "date":     "DATE",    "gameDate": "DATE",
        "hits":     "H",       "atBats": "AB",
        "homeRuns": "HR",      "walks": "BB",
        "strikeouts": "SO",    "hitByPitch": "HBP",
        "avg": "AVG", "obp": "OBP", "slg": "SLG", "ops": "OPS",
        "singles": "singles",  "doubles": "doubles", "triples": "triples",
    }
    df = df.rename(columns={k: v for k, v in col_rename.items() if k in df.columns})

    # Compute rate stats if raw counts present
    for col in ["H","AB","BB","HBP","HR","singles","doubles","triples"]:
        if col not in df.columns:
            df[col] = 0

    df = compute_hitter_rate_stats(df)

    # If we have per-game rows, add opponent/location
    if "GAME_ID" in df.columns and not games_df.empty:
        df = game_context(df, games_df, selected_team)

    return df


def build_pitcher_game_log(player_stats_df, player_guid, games_df, selected_team):
    """Build per-game pitching log from /player-stats response."""
    df = player_stats_df[
        (player_stats_df.get("playerGuid", player_stats_df.get("player_id", pd.Series(dtype=str))) == player_guid)
        | (player_stats_df.get("player_id", pd.Series(dtype=str)) == player_guid)
    ].copy()

    if df.empty:
        return pd.DataFrame()

    col_rename = {
        "gameGuid": "GAME_ID", "gameId": "GAME_ID", "game_id": "GAME_ID",
        "date": "DATE", "gameDate": "DATE",
        "inningsPitched": "IP", "strikeouts": "SO", "walks": "BB",
        "hits": "H", "homeRuns": "HR", "runs": "R",
        "era": "ERA", "whip": "WHIP", "pitchCount": "NP",
        "pitcherName": "PITCHER",
    }
    df = df.rename(columns={k: v for k, v in col_rename.items() if k in df.columns})

    if "GAME_ID" in df.columns and not games_df.empty:
        df = game_context(df, games_df, selected_team)

    return df


# ─────────────────────────────────────────────
# Shared stat helpers (unchanged from widget.py)
# ─────────────────────────────────────────────

def compute_hitter_rate_stats(df):
    df = df.copy()
    for col in ["H","AB","BB","HBP","HR","singles","doubles","triples"]:
        df[col] = pd.to_numeric(df.get(col, 0), errors="coerce").fillna(0)

    df["AVG"] = (df["H"] / df["AB"].replace(0, pd.NA)).round(3)
    df["OBP"] = ((df["H"] + df["BB"] + df["HBP"]) /
                 (df["AB"] + df["BB"] + df["HBP"]).replace(0, pd.NA)).round(3)
    df["SLG"] = ((df["singles"] + 2*df["doubles"] + 3*df["triples"] + 4*df["HR"]) /
                 df["AB"].replace(0, pd.NA)).round(3)
    df["OPS"] = (df["OBP"] + df["SLG"]).round(3)
    df = df.drop(columns=["singles","doubles","triples"], errors="ignore")
    return df


def game_context(game_info_df, games_df, selected_team):
    """Merge games_df to add OPPONENT and LOCATION columns."""
    if games_df.empty:
        return game_info_df

    # Normalise game id column name
    id_col = next((c for c in ["gameGuid","guid","id","game_id"] if c in games_df.columns), None)
    if id_col and id_col != "GAME_ID":
        games_df = games_df.rename(columns={id_col: "GAME_ID"})

    # Normalise team-name columns (iScore uses homeTeamName / visitingTeamName or similar)
    for old, new in [
        ("homeTeamName", "home_team_name"),
        ("awayTeamName", "visiting_team_name"),
        ("visitingTeamName", "visiting_team_name"),
    ]:
        if old in games_df.columns:
            games_df = games_df.rename(columns={old: new})

    if "GAME_ID" not in game_info_df.columns:
        return game_info_df

    merged = game_info_df.merge(games_df, on="GAME_ID", how="left")

    def get_opponent(row):
        home = row.get("home_team_name", "")
        away = row.get("visiting_team_name", "")
        return away if home == selected_team else home

    def get_location(row):
        home = row.get("home_team_name", "")
        return "HOME" if home == selected_team else "AWAY"

    if "home_team_name" in merged.columns:
        merged["OPPONENT"] = merged.apply(get_opponent, axis=1)
        merged["LOCATION"] = merged.apply(get_location, axis=1)

    return merged


def hot_cold_label(val, pct, reverse=False):
    if pd.isna(pct):
        return str(val)
    if reverse:
        return f"🔥 {val}" if pct <= 25 else (f"🧊 {val}" if pct >= 75 else str(val))
    else:
        return f"🔥 {val}" if pct >= 75 else (f"🧊 {val}" if pct <= 25 else str(val))


def compute_rolling_percentiles(df, group_col, stat, pct_name, reverse=False, window=5):
    df = df.copy().sort_values("DATE")
    last_n = df.groupby(group_col, group_keys=False).tail(window).copy()
    last_n[pct_name] = last_n[stat].rank(pct=True, ascending=not reverse) * 100
    df = df.merge(last_n[[group_col, "GAME_ID", pct_name]], on=[group_col, "GAME_ID"], how="left")
    return df


def apply_hot_cold_labels(df, stat_config):
    df = df.copy()
    for stat, (pct_col, reverse) in stat_config.items():
        if stat in df.columns and pct_col in df.columns:
            df[stat] = df.apply(
                lambda row, s=stat, p=pct_col, r=reverse: hot_cold_label(row[s], row[p], r),
                axis=1
            )
    df = df.drop(columns=[v[0] for v in stat_config.values()], errors="ignore")
    return df


def add_season_percentiles(df, stat_config):
    """Compute cross-player percentiles for season leaderboard views."""
    df = df.copy()
    for stat, (pct_col, reverse) in stat_config.items():
        if stat in df.columns:
            df[pct_col] = pd.to_numeric(df[stat], errors="coerce").rank(
                pct=True, ascending=not reverse
            ) * 100
    return df


# ─────────────────────────────────────────────
# UI
# ─────────────────────────────────────────────

st.title("ALPB League Stats")

# Load teams
teams_df = get_league_teams()
if teams_df.empty:
    st.warning("Could not load teams. Check your LEAGUE_GUID and API connectivity.")
    st.stop()

all_teams = sorted(teams_df["TEAM"].dropna().unique())
selected_team = st.selectbox("Select a Team", all_teams)

team_row  = teams_df[teams_df["TEAM"] == selected_team].iloc[0]
team_guid = team_row["team_guid"]

# Load players
team_players = get_team_players(team_guid)

tab1, tab2, tab3 = st.tabs(["Pitchers", "Hitters", "Fielding"])


# ─────────────────────────────────────────────
# Tab 1 – Pitchers
# ─────────────────────────────────────────────
with tab1:
    st.subheader("Pitchers")

    pitching_df = get_pitching_leaderboard(team_guid)

    if pitching_df.empty:
        st.info("No pitching data available for this team.")
    else:
        # Add PITCH HAND from roster if available
        if not team_players.empty and "PITCH HAND" in team_players.columns:
            hand_lookup = team_players[["PLAYER","PITCH HAND"]].rename(columns={"PLAYER":"PITCHER"})
            pitching_df = pitching_df.merge(hand_lookup, on="PITCHER", how="left")

        pitcher_options = ["All Pitchers"] + pitching_df["PITCHER"].dropna().tolist()
        selected_pitcher = st.selectbox("Select Pitcher", pitcher_options)

        # ── All Pitchers: season leaderboard with hot/cold ──────────────────
        if selected_pitcher == "All Pitchers":
            pitcher_stat_config = {
                "ERA":  ("ERA_PERCENTILE",  True),
                "WHIP": ("WHIP_PERCENTILE", True),
                "SO":   ("SO_PERCENTILE",   False),
                "BB":   ("BB_PERCENTILE",   True),
                "HR":   ("HR_PERCENTILE",   True),
                "H":    ("H_PERCENTILE",    True),
                "R":    ("R_PERCENTILE",    True),
            }

            season_stats = add_season_percentiles(pitching_df, pitcher_stat_config)

            allowed_cols = [c for c in
                ["PITCHER","PITCH HAND","G","IP","NP","H","R","HR","BB","SO","ERA","WHIP"]
                if c in season_stats.columns]
            default_cols = [c for c in
                ["PITCHER","PITCH HAND","G","IP","H","R","HR","BB","SO","ERA","WHIP"]
                if c in season_stats.columns]

            selected_columns = st.multiselect(
                "Select stats to display", options=allowed_cols, default=default_cols
            )

            hot_cold_stats = st.multiselect(
                "🔥🧊 Show Hot/Cold labels for:",
                options=[k for k in pitcher_stat_config if k in season_stats.columns],
                default=[k for k in pitcher_stat_config if k in season_stats.columns],
                key="pitcher_season_hot_cold_stats"
            )

            filtered_config = {k: v for k, v in pitcher_stat_config.items() if k in hot_cold_stats}
            season_stats = apply_hot_cold_labels(season_stats, filtered_config)

            display_cols = [c for c in selected_columns if c in season_stats.columns]
            pdf_df = season_stats[display_cols].reset_index(drop=True)

            st.subheader("Pitcher Season Stats")
            st.dataframe(pdf_df, use_container_width=True, hide_index=True)

            st.download_button(
                label="🖨️ Download PDF",
                data=generate_pdf(
                    df=pdf_df, title="Pitcher Season Stats",
                    subtitle=f"Team: {selected_team}", selected_cols=display_cols,
                ),
                file_name=pdf_filename("pitcher_season"),
                mime="application/pdf", key="pdf_pitcher_season",
            )

        # ── Individual Pitcher: per-game log with rolling hot/cold ───────────
        else:
            pitcher_row  = pitching_df[pitching_df["PITCHER"] == selected_pitcher].iloc[0]
            pitcher_guid = pitcher_row.get("player_id")

            # Fetch per-game data from /player-stats
            player_stats = get_team_player_stats(team_guid)
            games_df     = get_all_games()

            game_log = build_pitcher_game_log(player_stats, pitcher_guid, games_df, selected_team)

            if game_log.empty:
                st.info("No per-game data available for this pitcher. Showing season totals.")
                # Fall back to single season-total row
                game_log = pitching_df[pitching_df["PITCHER"] == selected_pitcher].copy()
                game_log["DATE"] = "Season"

            pitcher_game_stat_list = [
                ("H",  True), ("HR", True), ("BB", True),
                ("SO", False), ("R",  True),
            ]
            if "ERA" in game_log.columns:
                pitcher_game_stat_list.append(("ERA", True))

            if "GAME_ID" in game_log.columns and "DATE" in game_log.columns:
                for stat, reverse in pitcher_game_stat_list:
                    if stat in game_log.columns:
                        game_log = compute_rolling_percentiles(
                            game_log, group_col="PITCHER", stat=stat,
                            pct_name=f"{stat}_PERCENTILE", reverse=reverse, window=5
                        )

            pitcher_game_stat_config = {
                s: (f"{s}_PERCENTILE", r) for s, r in pitcher_game_stat_list
            }

            base_cols = ["DATE","OPPONENT","LOCATION","NP","IP","H","R","HR","BB","SO","ERA","WHIP"]
            allowed_cols = [c for c in base_cols if c in game_log.columns]
            default_cols = [c for c in
                ["DATE","OPPONENT","LOCATION","NP","IP","H","R","HR","BB","SO"]
                if c in game_log.columns]

            selected_columns = st.multiselect(
                "Select stats to display", options=allowed_cols, default=default_cols
            )

            hot_cold_stats = st.multiselect(
                "🔥🧊 Show Hot/Cold labels for:",
                options=[k for k in pitcher_game_stat_config if k in game_log.columns],
                default=[k for k in pitcher_game_stat_config if k in game_log.columns],
                key="pitcher_game_hot_cold_stats"
            )

            filtered_config = {k: v for k, v in pitcher_game_stat_config.items() if k in hot_cold_stats}
            game_log = apply_hot_cold_labels(game_log, filtered_config)

            display_cols = [c for c in selected_columns if c in game_log.columns]
            pdf_df = game_log[display_cols].reset_index(drop=True)

            st.subheader(f"{selected_pitcher} Game By Game Stats")
            st.dataframe(pdf_df, use_container_width=True, hide_index=True)

            st.download_button(
                label="🖨️ Download PDF",
                data=generate_pdf(
                    df=pdf_df, title="Pitcher Game Log",
                    subtitle=f"Team: {selected_team} | Pitcher: {selected_pitcher}",
                    selected_cols=display_cols,
                ),
                file_name=pdf_filename("pitcher_game_log"),
                mime="application/pdf", key="pdf_pitcher_game_log",
            )


# ─────────────────────────────────────────────
# Tab 2 – Hitters
# ─────────────────────────────────────────────
with tab2:
    st.subheader("Hitters")

    batting_df = get_batting_leaderboard(team_guid)

    if batting_df.empty:
        st.info("No batting data available for this team.")
    else:
        # Add BAT HAND from roster if available
        if not team_players.empty and "BAT HAND" in team_players.columns:
            hand_lookup = team_players[["PLAYER","BAT HAND"]].rename(columns={"PLAYER":"BATTER"})
            batting_df = batting_df.merge(hand_lookup, on="BATTER", how="left")

        hitter_options = ["All Hitters"] + batting_df["BATTER"].dropna().tolist()
        selected_hitter = st.selectbox("Select Hitter", hitter_options)

        # ── All Hitters: season leaderboard with hot/cold ───────────────────
        if selected_hitter == "All Hitters":
            hitter_season_stat_config = {
                "AVG": ("AVG_PERCENTILE", False),
                "OBP": ("OBP_PERCENTILE", False),
                "SLG": ("SLG_PERCENTILE", False),
                "OPS": ("OPS_PERCENTILE", False),
                "H":   ("H_PERCENTILE",   False),
                "HR":  ("HR_PERCENTILE",  False),
                "BB":  ("BB_PERCENTILE",  False),
                "SO":  ("SO_PERCENTILE",  True),
            }

            season_stats = add_season_percentiles(batting_df, hitter_season_stat_config)

            allowed_cols = [c for c in
                ["BATTER","BAT HAND","G","AB","H","HR","BB","SO","HBP","AVG","OBP","SLG","OPS"]
                if c in season_stats.columns]
            default_cols = [c for c in
                ["BATTER","BAT HAND","G","AB","H","HR","BB","SO","AVG","OBP","SLG","OPS"]
                if c in season_stats.columns]

            selected_columns = st.multiselect(
                "Select stats to display", options=allowed_cols, default=default_cols
            )

            hot_cold_stats = st.multiselect(
                "🔥🧊 Show Hot/Cold labels for:",
                options=[k for k in hitter_season_stat_config if k in season_stats.columns],
                default=[k for k in hitter_season_stat_config if k in season_stats.columns],
                key="hitter_season_hot_cold_stats"
            )

            filtered_config = {k: v for k, v in hitter_season_stat_config.items() if k in hot_cold_stats}
            season_stats = apply_hot_cold_labels(season_stats, filtered_config)

            display_cols = [c for c in selected_columns if c in season_stats.columns]
            pdf_df = season_stats[display_cols].reset_index(drop=True)

            st.subheader("Hitter Season Stats")
            st.dataframe(pdf_df, use_container_width=True, hide_index=True)

            st.download_button(
                label="🖨️ Download PDF",
                data=generate_pdf(
                    df=pdf_df, title="Hitter Season Stats",
                    subtitle=f"Team: {selected_team}", selected_cols=display_cols,
                ),
                file_name=pdf_filename("hitter_season"),
                mime="application/pdf", key="pdf_hitter_season",
            )

        # ── Individual Hitter: per-game log with rolling hot/cold ────────────
        else:
            hitter_row  = batting_df[batting_df["BATTER"] == selected_hitter].iloc[0]
            hitter_guid = hitter_row.get("player_id")

            player_stats = get_team_player_stats(team_guid)
            games_df     = get_all_games()

            game_log = build_hitter_game_log(player_stats, hitter_guid, games_df, selected_team)

            if game_log.empty:
                st.info("No per-game data available for this hitter. Showing season totals.")
                game_log = batting_df[batting_df["BATTER"] == selected_hitter].copy()
                game_log["DATE"] = "Season"

            hitter_game_stat_list = [
                ("AVG", False), ("OBP", False), ("SLG", False), ("OPS", False),
                ("H",   False), ("HR",  False), ("BB",  False), ("SO",  True),
            ]

            if "GAME_ID" in game_log.columns and "DATE" in game_log.columns:
                for stat, reverse in hitter_game_stat_list:
                    if stat in game_log.columns:
                        game_log = compute_rolling_percentiles(
                            game_log, group_col="BATTER", stat=stat,
                            pct_name=f"{stat}_PERCENTILE", reverse=reverse, window=5
                        )

            hitter_game_stat_config = {
                s: (f"{s}_PERCENTILE", r) for s, r in hitter_game_stat_list
            }

            base_cols = ["DATE","OPPONENT","LOCATION","AB","H","HR","BB","SO","HBP","AVG","OBP","SLG","OPS"]
            allowed_cols = [c for c in base_cols if c in game_log.columns]
            default_cols = [c for c in
                ["DATE","OPPONENT","LOCATION","AB","H","HR","BB","SO","AVG","OBP","SLG","OPS"]
                if c in game_log.columns]

            selected_hitter_cols = st.multiselect(
                "Select stats to display", options=allowed_cols, default=default_cols,
                key="hitter_game_log_cols"
            )

            hot_cold_stats = st.multiselect(
                "🔥🧊 Show Hot/Cold labels for:",
                options=[k for k in hitter_game_stat_config if k in game_log.columns],
                default=[k for k in hitter_game_stat_config if k in game_log.columns],
                key="hitter_game_hot_cold_stats"
            )

            filtered_config = {k: v for k, v in hitter_game_stat_config.items() if k in hot_cold_stats}
            game_log = apply_hot_cold_labels(game_log, filtered_config)

            display_cols = [c for c in selected_hitter_cols if c in game_log.columns]
            pdf_df = game_log[display_cols].reset_index(drop=True)

            st.subheader(f"{selected_hitter} Game By Game Stats")
            st.dataframe(pdf_df, use_container_width=True, hide_index=True)

            st.download_button(
                label="🖨️ Download PDF",
                data=generate_pdf(
                    df=pdf_df, title="Hitter Game Log",
                    subtitle=f"Team: {selected_team}  |  Hitter: {selected_hitter}",
                    selected_cols=display_cols,
                ),
                file_name=pdf_filename("hitter_game_log"),
                mime="application/pdf", key="pdf_hitter_game_log",
            )


# ─────────────────────────────────────────────
# Tab 3 – Fielding (new, uses iScore fielding endpoint)
# ─────────────────────────────────────────────
with tab3:
    st.subheader("Fielding")

    fielding_df = get_fielding_leaderboard(team_guid)

    if fielding_df.empty:
        st.info("No fielding data available for this team.")
    else:
        fielding_stat_config = {
            "FPCT": ("FPCT_PERCENTILE", False),
            "PO":   ("PO_PERCENTILE",   False),
            "A":    ("A_PERCENTILE",    False),
            "E":    ("E_PERCENTILE",    True),
        }

        season_stats = add_season_percentiles(fielding_df, fielding_stat_config)

        allowed_cols = [c for c in ["FIELDER","G","INN","PO","A","E","FPCT"] if c in season_stats.columns]
        default_cols = allowed_cols

        selected_columns = st.multiselect(
            "Select stats to display", options=allowed_cols, default=default_cols,
            key="fielding_cols"
        )

        hot_cold_stats = st.multiselect(
            "🔥🧊 Show Hot/Cold labels for:",
            options=[k for k in fielding_stat_config if k in season_stats.columns],
            default=[k for k in fielding_stat_config if k in season_stats.columns],
            key="fielding_hot_cold_stats"
        )

        filtered_config = {k: v for k, v in fielding_stat_config.items() if k in hot_cold_stats}
        season_stats = apply_hot_cold_labels(season_stats, filtered_config)

        display_cols = [c for c in selected_columns if c in season_stats.columns]
        pdf_df = season_stats[display_cols].reset_index(drop=True)

        st.subheader("Fielding Season Stats")
        st.dataframe(pdf_df, use_container_width=True, hide_index=True)

        st.download_button(
            label="🖨️ Download PDF",
            data=generate_pdf(
                df=pdf_df, title="Fielding Season Stats",
                subtitle=f"Team: {selected_team}", selected_cols=display_cols,
            ),
            file_name=pdf_filename("fielding_season"),
            mime="application/pdf", key="pdf_fielding_season",
        )