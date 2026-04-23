"""
GUID Discovery Tool  —  run as: streamlit run find_guids.py
DO NOT paste this into widget.py. Run it as its own separate file.
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
st.info("Run this file separately: `streamlit run find_guids.py`")

# ── Step 1 ───────────────────────────────────────────────────────────────────
st.header("Step 1 — Find your League GUID")

if st.button("Fetch all leagues  →  GET /public/leagues"):
    code, data = fetch("public/leagues")
    st.write(f"**Status:** `{code}`")
    st.json(data)

st.markdown("If Step 1 returns a 500, paste a GUID you already know below:")
manual_league = st.text_input("League GUID:", placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx")

# ── Step 2 ───────────────────────────────────────────────────────────────────
if manual_league:
    st.header("Step 2 — Verify League & Get Seasons")
    col1, col2 = st.columns(2)

    with col1:
        if st.button("GET .../leagues/{guid}/details"):
            code, data = fetch(f"public/leagues/{manual_league}/details")
            st.write(f"**Status:** `{code}`")
            st.json(data)

    with col2:
        if st.button("GET .../leagues/{guid}/seasons/summary"):
            code, data = fetch(f"public/leagues/{manual_league}/seasons/summary")
            st.write(f"**Status:** `{code}`")
            st.json(data)

    if st.button("GET .../leagues/{guid}/seasons (full)"):
        code, data = fetch(f"public/leagues/{manual_league}/seasons")
        st.write(f"**Status:** `{code}`")
        st.json(data)

    if st.button("GET .../leagues/{guid}/teams"):
        code, data = fetch(f"public/leagues/{manual_league}/teams")
        st.write(f"**Status:** `{code}`")
        st.json(data)

# ── Step 3 ───────────────────────────────────────────────────────────────────
st.header("Step 3 — Verify Season GUID")
manual_season = st.text_input("Season GUID:", placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx")

if manual_league and manual_season:
    if st.button("GET /public/seasons/{seasonGuid}"):
        code, data = fetch(f"public/seasons/{manual_season}")
        st.write(f"**Status:** `{code}`")
        st.json(data)

    if st.button("GET /public/games (league filter, first 5)"):
        code, data = fetch("public/games", params={"leagueGuid": manual_league, "Take": 5})
        st.write(f"**Status:** `{code}`")
        st.json(data)

# ── Step 4 ───────────────────────────────────────────────────────────────────
st.header("Step 4 — Test a Team GUID")
manual_team = st.text_input("Team GUID:", placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx")

if manual_team:
    if st.button("GET /public/teams/{guid}/players"):
        code, data = fetch(f"public/teams/{manual_team}/players")
        st.write(f"**Status:** `{code}`")
        st.json(data)

# ── Step 5 ───────────────────────────────────────────────────────────────────
st.header("Step 5 — Test Leaderboards")

if manual_league and manual_season:
    lb_type = st.selectbox("Leaderboard type", ["batting", "pitching", "fielding", "running"])
    lb_sort = st.text_input("SortBy", value="OPS")

    if st.button(f"GET /leaderboard/player/{{lb_type}}"):
        code, data = fetch(f"leaderboard/player/{lb_type}", params={
            "LeagueId": manual_league,
            "SeasonId": manual_season,
            "SortBy":   lb_sort,
            "Size":     5,
        })
        st.write(f"**Status:** `{code}`")
        st.json(data)

st.divider()
st.caption("Once you have confirmed GUIDs, add them to your .env:  LEAGUE_GUID=...  SEASON_GUID=...")