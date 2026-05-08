"""
GUID Discovery Tool  —  run as: streamlit run find_guids.py
Keep this as a SEPARATE file from widget.py.
"""

import streamlit as st
import requests

BASE_URL = "https://api.microservices.iscoresports.com/api"
HEADERS  = {"Content-Type": "application/json"}

def fetch(endpoint, params=None):
    url = f"{BASE_URL}/{endpoint}"
    try:
        resp = requests.get(url, headers=HEADERS, params=params, timeout=10)
        try:
            data = resp.json()
        except Exception:
            data = {"raw": resp.text}
        return resp.status_code, data
    except Exception as e:
        return 0, {"error": str(e)}

st.title("🔍 iScore GUID Discovery")

# ── Step 0 ────────────────────────────────────────────────────────────────────
st.header("Step 0 — Start from a Season GUID")
st.markdown("If you already have a Season GUID, start here — the response contains your League GUID and team info.")

known_season = st.text_input("Season GUID:", placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx", key="known_season")
if known_season:
    if st.button("GET /public/seasons/{seasonGuid}", key="btn_step0"):
        code, data = fetch(f"public/seasons/{known_season}")
        st.write(f"**Status:** `{code}`")
        st.json(data)
        if code == 200:
            st.success("✅ Look for 'leagueGuid', 'league', and 'teams' in the response above.")

st.divider()

# ── Step 1 ────────────────────────────────────────────────────────────────────
st.header("Step 1 — Find your League GUID")
if st.button("GET /public/leagues", key="btn_step1"):
    code, data = fetch("public/leagues")
    st.write(f"**Status:** `{code}`")
    st.json(data)

manual_league = st.text_input("League GUID:", placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx", key="manual_league")

# ── Step 2 ────────────────────────────────────────────────────────────────────
if manual_league:
    st.header("Step 2 — Verify League & Get Seasons")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("GET .../leagues/{guid}/details", key="btn_details"):
            code, data = fetch(f"public/leagues/{manual_league}/details")
            st.write(f"**Status:** `{code}`")
            st.json(data)
    with col2:
        if st.button("GET .../leagues/{guid}/seasons/summary", key="btn_seasons_summary"):
            code, data = fetch(f"public/leagues/{manual_league}/seasons/summary")
            st.write(f"**Status:** `{code}`")
            st.json(data)
            if code == 200:
                st.success("✅ Grab the 'guid' from the active season — that's your SEASON_GUID.")

    if st.button("GET .../leagues/{guid}/seasons (full)", key="btn_seasons_full"):
        code, data = fetch(f"public/leagues/{manual_league}/seasons")
        st.write(f"**Status:** `{code}`")
        st.json(data)

    if st.button("GET .../leagues/{guid}/teams", key="btn_teams"):
        code, data = fetch(f"public/leagues/{manual_league}/teams")
        st.write(f"**Status:** `{code}`")
        st.json(data)
        if code == 200:
            st.success("✅ Grab any team 'guid' value to use in Steps 4 and 5.")

st.divider()

# ── Step 3 ────────────────────────────────────────────────────────────────────
st.header("Step 3 — Verify Season GUID")
manual_season = st.text_input("Season GUID:", placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx", key="manual_season")

if manual_season:
    if st.button("GET /public/seasons/{seasonGuid}", key="btn_season_verify"):
        code, data = fetch(f"public/seasons/{manual_season}")
        st.write(f"**Status:** `{code}`")
        st.json(data)

if manual_league and manual_season:
    if st.button("GET /public/games (first 5)", key="btn_games"):
        code, data = fetch("public/games", params={"leagueGuid": manual_league, "Take": 5})
        st.write(f"**Status:** `{code}`")
        st.json(data)

st.divider()

# ── Step 4 ────────────────────────────────────────────────────────────────────
st.header("Step 4 — Test a Team GUID")
manual_team = st.text_input("Team GUID:", placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx", key="manual_team")

if manual_team:
    if st.button("GET /public/teams/{guid}/players", key="btn_players"):
        code, data = fetch(f"public/teams/{manual_team}/players")
        st.write(f"**Status:** `{code}`")
        st.json(data)

    if st.button("GET /player-stats for this team", key="btn_player_stats"):
        manual_season_for_stats = st.session_state.get("manual_season", "")
        code, data = fetch("player-stats", params={"TeamId": manual_team, "SeasonId": manual_season_for_stats})
        st.write(f"**Status:** `{code}`")
        st.json(data)

st.divider()

# ── Step 5 ────────────────────────────────────────────────────────────────────
st.header("Step 5 — Test Leaderboards")
st.markdown("Fill in all three GUIDs below — independent of the fields above so you can test freely.")

lb_league = st.text_input("League GUID:", key="lb_league",
    value=st.session_state.get("manual_league", ""),
    placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx")
lb_season = st.text_input("Season GUID:", key="lb_season",
    value=st.session_state.get("manual_season", ""),
    placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx")
lb_team   = st.text_input("Team GUID (optional — leave blank for full league):", key="lb_team",
    placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx")

lb_type = st.selectbox("Leaderboard type", ["batting", "pitching", "fielding", "running"], key="lb_type")
lb_sort = st.text_input("SortBy", value="OPS", key="lb_sort")
lb_size = st.number_input("Number of results", min_value=1, max_value=200, value=5, key="lb_size")

if lb_league and lb_season:
    if st.button(f"GET /leaderboard/player/{{lb_type}}", key="btn_leaderboard"):
        params = {
            "LeagueId": lb_league,
            "SeasonId": lb_season,
            "SortBy":   lb_sort,
            "Size":     lb_size,
        }
        if lb_team:
            params["TeamId"] = lb_team
        code, data = fetch(f"leaderboard/player/{lb_type}", params=params)
        st.write(f"**Status:** `{code}`")
        st.json(data)
        if code == 200:
            st.success("✅ Working! Note the exact field names in 'stats' — you may need to update baseball_stats_iscore.py to match.")
else:
    st.info("Enter League GUID and Season GUID above to enable leaderboard testing.")

st.divider()
st.caption("Once all steps work, add to your .env:  LEAGUE_GUID=...  SEASON_GUID=...")