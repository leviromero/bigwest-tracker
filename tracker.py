#!/usr/bin/env python3
"""
Big West Championships Tracker
Fetches 2026 Big West Outdoor T&F performance data from TFRRS,
calculates projected team scores (10-8-6-5-4-3-2-1), and generates
a beautiful Apple-inspired HTML dashboard.
"""

import requests
import warnings
import time
import json
import os
import sys
import webbrowser
from bs4 import BeautifulSoup
from collections import defaultdict

warnings.filterwarnings("ignore")

BASE_URL = "https://www.tfrrs.org/list_data/5660"
LIST_PAGE = "https://www.tfrrs.org/lists/5660/Big_West_Outdoor_Performance_List"

POINTS_TABLE = {1: 10, 2: 8, 3: 6, 4: 5, 5: 4, 6: 3, 7: 2, 8: 1}

# TFRRS event_type IDs
EVENTS = [
    # (event_type_id, gender_code, short_name, gender_label)
    ("6",  "m", "100m",      "Men"),
    ("6",  "f", "100m",      "Women"),
    ("7",  "m", "200m",      "Men"),
    ("7",  "f", "200m",      "Women"),
    ("11", "m", "400m",      "Men"),
    ("11", "f", "400m",      "Women"),
    ("12", "m", "800m",      "Men"),
    ("12", "f", "800m",      "Women"),
    ("13", "m", "1500m",     "Men"),
    ("13", "f", "1500m",     "Women"),
    ("21", "m", "5000m",     "Men"),
    ("21", "f", "5000m",     "Women"),
    ("22", "m", "10000m",    "Men"),
    ("22", "f", "10000m",    "Women"),
    ("5",  "m", "110mH",     "Men"),
    ("4",  "f", "100mH",     "Women"),
    ("9",  "m", "400mH",     "Men"),
    ("9",  "f", "400mH",     "Women"),
    ("19", "m", "3000mSC",   "Men"),
    ("19", "f", "3000mSC",   "Women"),
    ("31", "m", "4x100m",    "Men"),
    ("31", "f", "4x100m",    "Women"),
    ("33", "m", "4x400m",    "Men"),
    ("33", "f", "4x400m",    "Women"),
    ("23", "m", "HJ",        "Men"),
    ("23", "f", "HJ",        "Women"),
    ("24", "m", "PV",        "Men"),
    ("24", "f", "PV",        "Women"),
    ("25", "m", "LJ",        "Men"),
    ("25", "f", "LJ",        "Women"),
    ("26", "m", "TJ",        "Men"),
    ("26", "f", "TJ",        "Women"),
    ("30", "m", "SP",        "Men"),
    ("30", "f", "SP",        "Women"),
    ("27", "m", "DT",        "Men"),
    ("27", "f", "DT",        "Women"),
    ("28", "m", "HT",        "Men"),
    ("28", "f", "HT",        "Women"),
    ("29", "m", "JT",        "Men"),
    ("29", "f", "JT",        "Women"),
    ("39", "m", "Decathlon", "Men"),
    ("40", "f", "Heptathlon","Women"),
]

FIELD_EVENTS = {"HJ", "PV", "LJ", "TJ", "SP", "DT", "HT", "JT"}
MULTI_EVENTS = {"Decathlon", "Heptathlon"}
RELAY_EVENTS = {"4x100m", "4x400m"}

EVENT_CATEGORIES = {
    "Sprints":  ["100m", "200m", "400m"],
    "Distance": ["800m", "1500m", "5000m", "10000m"],
    "Hurdles":  ["110mH", "100mH", "400mH", "3000mSC"],
    "Relays":   ["4x100m", "4x400m"],
    "Jumps":    ["HJ", "PV", "LJ", "TJ"],
    "Throws":   ["SP", "DT", "HT", "JT"],
    "Multi":    ["Decathlon", "Heptathlon"],
}

SCHOOL_NORMALIZE = {
    "cal poly": "Cal Poly",
    "cal poly slo": "Cal Poly",
    "california polytechnic": "Cal Poly",
    "cal poly san luis obispo": "Cal Poly",
    "cal st. fullerton": "Cal St. Fullerton",
    "csuf": "Cal St. Fullerton",
    "cal state fullerton": "Cal St. Fullerton",
    "california state fullerton": "Cal St. Fullerton",
    "csun": "CSUN",
    "cal st. northridge": "CSUN",
    "cal state northridge": "CSUN",
    "california state northridge": "CSUN",
    "long beach st.": "Long Beach St.",
    "long beach state": "Long Beach St.",
    "csulb": "Long Beach St.",
    "csu long beach": "Long Beach St.",
    "csu bakersfield": "CSU Bakersfield",
    "cal st. bakersfield": "CSU Bakersfield",
    "cal state bakersfield": "CSU Bakersfield",
    "california state bakersfield": "CSU Bakersfield",
    "uc davis": "UC Davis",
    "california-davis": "UC Davis",
    "uc irvine": "UC Irvine",
    "california-irvine": "UC Irvine",
    "uci": "UC Irvine",
    "uc riverside": "UC Riverside",
    "california-riverside": "UC Riverside",
    "ucr": "UC Riverside",
    "uc san diego": "UC San Diego",
    "california-san diego": "UC San Diego",
    "ucsd": "UC San Diego",
    "uc santa barbara": "UC Santa Barbara",
    "california-santa barbara": "UC Santa Barbara",
    "ucsb": "UC Santa Barbara",
    "hawaii": "Hawaii",
    "hawai'i": "Hawaii",
    "university of hawaii": "Hawaii",
    "hawaii rainbow": "Hawaii",
}

BIG_WEST_SCHOOLS = {
    "Cal Poly", "Cal St. Fullerton", "CSUN", "CSU Bakersfield",
    "Long Beach St.", "UC Davis", "UC Irvine", "UC Riverside",
    "UC San Diego", "UC Santa Barbara", "Hawaii",
}

SCHOOL_COLORS = {
    "Cal Poly":         "#154734",
    "Cal St. Fullerton":"#FF6600",
    "CSUN":             "#CC0000",
    "CSU Bakersfield":  "#00205B",
    "Long Beach St.":   "#222222",
    "UC Davis":         "#022851",
    "UC Irvine":        "#0064A4",
    "UC Riverside":     "#003DA5",
    "UC San Diego":     "#182B49",
    "UC Santa Barbara": "#003660",
    "Hawaii":           "#024731",
}


def normalize_school(name: str) -> str:
    key = name.strip().lower()
    for pattern, canonical in SCHOOL_NORMALIZE.items():
        if key == pattern or pattern in key:
            return canonical
    for school in BIG_WEST_SCHOOLS:
        if school.lower() in key or key in school.lower():
            return school
    return name.strip()


def get_category(event_short: str) -> str:
    for cat, events in EVENT_CATEGORIES.items():
        if event_short in events:
            return cat
    return "Other"


def mark_to_float(mark: str, event_short: str) -> float:
    """Lower = better for track; higher = better for field/multi."""
    mark = mark.strip().replace(",", "").split("w")[0].strip()
    try:
        if ":" in mark:
            parts = mark.split(":")
            return float(parts[0]) * 60 + float(parts[1])
        return float(mark)
    except (ValueError, IndexError):
        return float("inf") if event_short not in FIELD_EVENTS | MULTI_EVENTS else 0.0


def fetch_event(event_type: str, gender: str, limit: int = 50) -> str:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/vnd.turbo-stream.html, text/html, application/xhtml+xml",
        "Referer": LIST_PAGE,
        "Turbo-Frame": "list_data",
    }
    params = {"event_type": event_type, "gender": gender, "limit": str(limit)}
    resp = requests.get(BASE_URL, params=params, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.text


def parse_event_html(html: str) -> list:
    """Parse TFRRS performance-list-row divs into athlete dicts."""
    soup = BeautifulSoup(html, "html.parser")
    rows = soup.find_all("div", class_="performance-list-row")
    athletes = []

    for row in rows:
        def col(label):
            el = row.find("div", attrs={"data-label": label})
            return el.get_text(strip=True) if el else ""

        is_relay = "is-relay" in row.get("class", [])

        # Team
        team_div = row.find("div", class_="col-team")
        school_raw = team_div.get_text(strip=True) if team_div else ""
        school = normalize_school(school_raw)

        if is_relay:
            # For relays the team IS the entry; use school name as athlete name too
            name = school_raw
            year = ""
        else:
            # Individual athlete
            athlete_div = row.find("div", class_="col-athlete")
            name = athlete_div.get_text(strip=True) if athlete_div else ""
            if not name:
                continue
            # Normalize "Last, First" → "First Last"
            if "," in name:
                parts = name.split(",", 1)
                name = parts[1].strip() + " " + parts[0].strip()
            year = col("Year")

        if not name:
            continue

        # Mark — could be labeled Time, Mark, Distance, or Height
        mark = col("Time") or col("Mark") or col("Distance") or col("Height")
        wind = col("Wind")

        athletes.append({
            "name": name,
            "school": school,
            "school_raw": school_raw,
            "mark": mark,
            "year": year,
            "wind": wind or None,
            "in_big_west": school in BIG_WEST_SCHOOLS,
        })

    return athletes


def fetch_all_events() -> dict:
    """Fetch data for all events and return structured dict."""
    all_events = {}
    total = len(EVENTS)

    for i, (event_type, gender_code, short_name, gender_label) in enumerate(EVENTS, 1):
        event_key = f"{gender_label} {short_name}"
        print(f"  [{i:2d}/{total}] {event_key}...", end=" ", flush=True)

        try:
            html = fetch_event(event_type, gender_code, limit=50)
            athletes = parse_event_html(html)
            bw_count = sum(1 for a in athletes if a["in_big_west"])
            print(f"{len(athletes)} total, {bw_count} Big West")
            if athletes:
                all_events[event_key] = {
                    "athletes": athletes,
                    "short_name": short_name,
                    "gender": gender_label.lower(),
                    "category": get_category(short_name),
                }
        except Exception as e:
            print(f"ERROR: {e}")

        # Be polite to the server
        time.sleep(0.4)

    return all_events


def calculate_scores(all_events: dict) -> dict:
    team_scores_combined = defaultdict(int)
    team_scores_men = defaultdict(int)
    team_scores_women = defaultdict(int)
    processed_events = {}

    for event_key, ev in all_events.items():
        short_name = ev["short_name"]
        gender = ev["gender"]
        category = ev["category"]
        athletes = ev["athletes"]
        is_field = short_name in FIELD_EVENTS
        is_multi = short_name in MULTI_EVENTS
        is_relay = short_name in RELAY_EVENTS

        bw = [a for a in athletes if a.get("in_big_west")]

        if is_relay:
            # One best-mark entry per school
            school_best = {}
            for a in bw:
                s = a["school"]
                val = mark_to_float(a["mark"], short_name)
                if s not in school_best or val < school_best[s][0]:
                    school_best[s] = (val, a)
            bw = [v[1] for v in sorted(school_best.values(), key=lambda x: x[0])]
        else:
            reverse = is_field or is_multi
            bw = sorted(
                bw,
                key=lambda a: mark_to_float(a["mark"], short_name),
                reverse=reverse,
            )

        top8 = bw[:8]
        scored = []
        for rank, athlete in enumerate(top8, 1):
            pts = POINTS_TABLE.get(rank, 0)
            school = athlete["school"]
            scored.append({
                "rank": rank,
                "name": athlete["name"],
                "school": school,
                "mark": athlete["mark"],
                "year": athlete.get("year", ""),
                "wind": athlete.get("wind"),
                "points": pts,
            })
            team_scores_combined[school] += pts
            if gender == "men":
                team_scores_men[school] += pts
            else:
                team_scores_women[school] += pts

        processed_events[event_key] = {
            "short_name": short_name,
            "gender": gender,
            "category": category,
            "top8": scored,
        }

    def make_board(scores):
        board = [{"school": s, "points": scores.get(s, 0)} for s in BIG_WEST_SCHOOLS]
        return sorted(board, key=lambda x: x["points"], reverse=True)

    return {
        "team_scores": {
            "combined": make_board(team_scores_combined),
            "men":      make_board(team_scores_men),
            "women":    make_board(team_scores_women),
        },
        "events": processed_events,
        "school_colors": SCHOOL_COLORS,
    }


def generate_html(data: dict) -> str:
    data_json = json.dumps(data, indent=2)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Big West Championships Tracker</title>
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
:root{{
  --bg:#0a0a0a;--surface:#141414;--elevated:#1e1e1e;
  --border:rgba(255,255,255,0.07);
  --accent:#00e676;--accent-glow:rgba(0,230,118,0.2);--accent-dim:#00b04f;
  --gold:#ffd700;--silver:#c0c0c0;--bronze:#cd7f32;
  --text:#f5f5f7;--text-2:#a1a1a6;--text-3:#48484a;
  --r:16px;--r-sm:10px;--ease:cubic-bezier(.4,0,.2,1);
}}
html{{scroll-behavior:smooth}}
body{{background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,"SF Pro Display","Helvetica Neue",Arial,sans-serif;font-size:15px;line-height:1.5;overflow-x:hidden;min-height:100vh}}

/* ── particles ── */
.particles{{position:fixed;inset:0;pointer-events:none;z-index:0;overflow:hidden}}
.pt{{position:absolute;border-radius:50%;background:var(--accent);opacity:0;animation:float-pt linear infinite}}
@keyframes float-pt{{0%{{transform:translateY(100vh) scale(0);opacity:0}}10%{{opacity:.12}}90%{{opacity:.04}}100%{{transform:translateY(-20vh) scale(1);opacity:0}}}}

/* ── layout ── */
.wrap{{position:relative;z-index:1;max-width:1200px;margin:0 auto;padding:0 24px 80px}}

/* ── hero ── */
.hero{{text-align:center;padding:72px 0 52px}}
.hero-badge{{display:inline-flex;align-items:center;gap:8px;background:rgba(0,230,118,.1);border:1px solid rgba(0,230,118,.3);border-radius:100px;padding:6px 16px;font-size:12px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;color:var(--accent);margin-bottom:24px;animation:fade-up .6s ease both}}
.hero-badge::before{{content:"";width:6px;height:6px;border-radius:50%;background:var(--accent);animation:pulse-dot 2s ease-in-out infinite}}
@keyframes pulse-dot{{0%,100%{{opacity:1;transform:scale(1)}}50%{{opacity:.5;transform:scale(.7)}}}}
.hero h1{{font-size:clamp(2rem,5vw,3.5rem);font-weight:700;letter-spacing:-.03em;line-height:1.1;background:linear-gradient(135deg,#fff 0%,var(--accent) 55%,#00b04f 100%);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;margin-bottom:12px;animation:fade-up .6s .1s ease both}}
.hero-sub{{color:var(--text-2);font-size:1.05rem;animation:fade-up .6s .2s ease both}}
@keyframes fade-up{{from{{opacity:0;transform:translateY(20px)}}to{{opacity:1;transform:translateY(0)}}}}

/* ── toggle ── */
.toggle-wrap{{display:flex;justify-content:center;margin-bottom:44px;animation:fade-up .6s .3s ease both}}
.pills{{display:flex;background:var(--surface);border:1px solid var(--border);border-radius:100px;padding:4px;gap:2px;position:relative}}
.pill{{position:relative;z-index:1;padding:8px 26px;border-radius:100px;border:none;background:transparent;color:var(--text-2);font-size:14px;font-weight:500;cursor:pointer;transition:color .25s var(--ease);font-family:inherit}}
.pill.active{{color:var(--bg)}}
.pill-bg{{position:absolute;top:4px;left:4px;height:calc(100% - 8px);background:var(--accent);border-radius:100px;transition:left .3s var(--ease),width .3s var(--ease);box-shadow:0 0 20px var(--accent-glow);z-index:0}}

/* ── section heading ── */
.sec-title{{font-size:1.4rem;font-weight:700;letter-spacing:-.02em;margin-bottom:20px;display:flex;align-items:center;gap:10px}}
.sec-title::after{{content:"";flex:1;height:1px;background:var(--border)}}

/* ── leaderboard ── */
.lb-section{{margin-bottom:56px}}
.lb-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(270px,1fr));gap:12px}}
.lb-card{{background:var(--surface);border:1px solid var(--border);border-radius:var(--r);padding:16px 20px;display:flex;align-items:center;gap:14px;cursor:pointer;transition:transform .3s var(--ease),border-color .3s var(--ease),box-shadow .3s var(--ease);opacity:0;position:relative;overflow:hidden}}
.lb-card::before{{content:"";position:absolute;inset:0;background:linear-gradient(135deg,var(--accent-glow),transparent 60%);opacity:0;transition:opacity .3s var(--ease)}}
.lb-card:hover{{transform:translateY(-2px);border-color:rgba(0,230,118,.3);box-shadow:0 8px 32px rgba(0,0,0,.4)}}
.lb-card:hover::before{{opacity:1}}
.lb-card.active{{border-color:var(--accent)!important;box-shadow:0 0 0 1px var(--accent),0 0 28px var(--accent-glow)!important}}
.lb-card.anim{{animation:slide-left .45s ease both}}
@keyframes slide-left{{from{{opacity:0;transform:translateX(-28px)}}to{{opacity:1;transform:translateX(0)}}}}
.lb-rank{{font-size:1rem;font-weight:800;width:26px;text-align:center;flex-shrink:0;color:var(--text-3)}}
.lb-medal{{font-size:1.3rem;width:26px;text-align:center;flex-shrink:0;animation:shimmer 3s ease-in-out infinite}}
@keyframes shimmer{{0%,100%{{filter:brightness(1)}}50%{{filter:brightness(1.5) drop-shadow(0 0 6px currentColor)}}}}
.lb-avatar{{width:42px;height:42px;border-radius:12px;display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:800;letter-spacing:.02em;color:#fff;flex-shrink:0;text-shadow:0 1px 3px rgba(0,0,0,.6)}}
.lb-info{{flex:1;min-width:0}}
.lb-school{{font-weight:600;font-size:.9rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.lb-pts-label{{font-size:11px;color:var(--text-3);text-transform:uppercase;letter-spacing:.06em}}
.lb-score{{font-size:1.6rem;font-weight:800;letter-spacing:-.03em;color:var(--accent);text-align:right;min-width:44px;font-variant-numeric:tabular-nums}}
.lb-score.big{{font-size:2rem}}

/* ── chips ── */
.chips-wrap{{margin-bottom:28px}}
.chips{{display:flex;gap:8px;flex-wrap:wrap}}
.chip{{padding:7px 16px;border-radius:100px;border:1px solid var(--border);background:var(--surface);color:var(--text-2);font-size:13px;font-weight:500;cursor:pointer;transition:all .25s var(--ease);font-family:inherit}}
.chip:hover{{border-color:rgba(0,230,118,.3);color:var(--text)}}
.chip.active{{background:rgba(0,230,118,.12);border-color:var(--accent);color:var(--accent)}}

/* ── events grid ── */
.ev-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:14px}}
.ev-card{{background:var(--surface);border:1px solid var(--border);border-radius:var(--r);overflow:hidden;transition:transform .3s var(--ease),border-color .3s var(--ease),box-shadow .3s var(--ease);opacity:0;transform:translateY(18px)}}
.ev-card:hover{{transform:translateY(-2px);border-color:rgba(0,230,118,.2);box-shadow:0 10px 36px rgba(0,0,0,.35)}}
.ev-card.vis{{animation:ev-in .4s ease both}}
@keyframes ev-in{{from{{opacity:0;transform:translateY(18px)}}to{{opacity:1;transform:translateY(0)}}}}
.ev-head{{padding:14px 18px;display:flex;align-items:center;justify-content:space-between;cursor:pointer;user-select:none;border-bottom:1px solid transparent;transition:border-color .25s,background .25s}}
.ev-card.open .ev-head{{border-bottom-color:var(--border);background:rgba(0,230,118,.04)}}
.ev-name-wrap{{display:flex;align-items:center;gap:9px}}
.g-badge{{font-size:10px;font-weight:700;letter-spacing:.08em;padding:3px 8px;border-radius:6px;text-transform:uppercase}}
.g-m{{background:rgba(100,160,255,.15);color:#64a0ff}}
.g-f{{background:rgba(255,100,160,.15);color:#ff64a0}}
.ev-name{{font-weight:600;font-size:.92rem}}
.ev-cat{{font-size:11px;color:var(--text-3);font-weight:500}}
.ev-chevron{{color:var(--text-3);transition:transform .25s var(--ease);font-size:11px}}
.ev-card.open .ev-chevron{{transform:rotate(180deg)}}

/* ── preview rows ── */
.ev-preview{{padding:2px 18px 14px}}
.prev-row{{display:flex;align-items:center;gap:8px;padding:6px 0;border-bottom:1px solid rgba(255,255,255,.04);font-size:13px}}
.prev-row:last-child{{border-bottom:none}}
.prev-rk{{width:18px;text-align:center;font-size:11px;font-weight:700;color:var(--text-3);flex-shrink:0}}
.prev-name{{flex:1;font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.prev-school{{color:var(--text-2);font-size:12px;white-space:nowrap;flex-shrink:0}}
.prev-mark{{font-weight:600;font-variant-numeric:tabular-nums;font-size:13px;min-width:58px;text-align:right;flex-shrink:0}}
.prev-pts{{background:rgba(0,230,118,.12);color:var(--accent);font-size:11px;font-weight:700;padding:2px 7px;border-radius:6px;min-width:26px;text-align:center;flex-shrink:0}}

/* ── full table ── */
.ev-tbl-wrap{{display:none;padding:0 18px 16px}}
.ev-card.open .ev-tbl-wrap{{display:block}}
table.rt{{width:100%;border-collapse:collapse;font-size:13px}}
table.rt th{{text-align:left;color:var(--text-3);font-size:11px;font-weight:600;letter-spacing:.06em;text-transform:uppercase;padding:8px 6px;border-bottom:1px solid var(--border)}}
table.rt td{{padding:9px 6px;border-bottom:1px solid rgba(255,255,255,.03);vertical-align:middle}}
table.rt tr:last-child td{{border-bottom:none}}
table.rt tr:hover td{{background:rgba(255,255,255,.02)}}
.pts-cell{{background:rgba(0,230,118,.1);color:var(--accent);font-weight:700;border-radius:6px;padding:3px 8px!important;text-align:center}}

/* ── empty state ── */
.empty{{text-align:center;padding:60px 20px;color:var(--text-3);grid-column:1/-1}}
.empty .icon{{font-size:2.5rem;margin-bottom:14px}}

/* ── footer ── */
footer{{text-align:center;padding:32px 24px;color:var(--text-3);font-size:12px;border-top:1px solid var(--border);margin-top:40px}}
footer a{{color:var(--accent-dim);text-decoration:none}}
footer a:hover{{color:var(--accent)}}

::-webkit-scrollbar{{width:8px}}
::-webkit-scrollbar-track{{background:var(--bg)}}
::-webkit-scrollbar-thumb{{background:var(--elevated);border-radius:4px}}
.dimmed{{opacity:.3}}
</style>
</head>
<body>
<div class="particles" id="pts"></div>
<div class="wrap">

  <header class="hero">
    <div class="hero-badge">2026 Outdoor Season</div>
    <h1>Big West Championships<br>Tracker</h1>
    <p class="hero-sub">Projected scores based on season-best performances &mdash; 10-8-6-5-4-3-2-1 scoring</p>
  </header>

  <div class="toggle-wrap">
    <div class="pills" id="pills">
      <div class="pill-bg" id="pillBg"></div>
      <button class="pill active" data-g="combined">Combined</button>
      <button class="pill" data-g="men">Men&rsquo;s</button>
      <button class="pill" data-g="women">Women&rsquo;s</button>
    </div>
  </div>

  <section class="lb-section">
    <h2 class="sec-title">Team Standings</h2>
    <div class="lb-grid" id="lbGrid"></div>
  </section>

  <div class="chips-wrap">
    <div class="chips" id="chips"></div>
  </div>

  <section>
    <h2 class="sec-title">Event Results</h2>
    <div class="ev-grid" id="evGrid"></div>
  </section>
</div>

<footer>
  Data sourced from <a href="{LIST_PAGE}" target="_blank">TFRRS Big West Outdoor Performance List</a>
  &middot; Scoring: 10-8-6-5-4-3-2-1 top 8 finishers &middot; Projections only
</footer>

<script>
const DATA = {data_json};
let gender = 'combined', category = 'All', teamFilter = null;

const initials = {{
  'Cal Poly':'CP','Cal St. Fullerton':'CSF','CSUN':'CSUN','CSU Bakersfield':'CSUB',
  'Long Beach St.':'LBS','UC Davis':'UCD','UC Irvine':'UCI','UC Riverside':'UCR',
  'UC San Diego':'UCSD','UC Santa Barbara':'UCSB','Hawaii':'HAW'
}};

function medal(r){{return r===1?'🥇':r===2?'🥈':r===3?'🥉':null}}

function counter(el, target, ms=1100){{
  let s=null;
  (function step(ts){{
    if(!s)s=ts;
    const p=Math.min((ts-s)/ms,1), e=1-Math.pow(1-p,3);
    el.textContent=Math.round(target*e);
    if(p<1)requestAnimationFrame(step);
  }})(performance.now());
}}

function spawnParticles(){{
  const c=document.getElementById('pts');
  for(let i=0;i<20;i++){{
    const p=document.createElement('div');
    p.className='pt';
    const sz=Math.random()*4+2;
    p.style.cssText=`width:${{sz}}px;height:${{sz}}px;left:${{Math.random()*100}}%;animation-duration:${{9+Math.random()*14}}s;animation-delay:${{Math.random()*12}}s`;
    c.appendChild(p);
  }}
}}

function pillBg(){{
  const active=document.querySelector('.pill.active');
  const bg=document.getElementById('pillBg');
  if(!active)return;
  bg.style.left=active.offsetLeft+'px';
  bg.style.width=active.offsetWidth+'px';
}}

function renderLB(){{
  const grid=document.getElementById('lbGrid');
  grid.innerHTML='';
  DATA.team_scores[gender].forEach((item,i)=>{{
    const r=i+1, m=medal(r), color=DATA.school_colors[item.school]||'#333';
    const card=document.createElement('div');
    card.className='lb-card';
    card.dataset.school=item.school;
    card.innerHTML=`
      ${{m?`<div class="lb-medal">${{m}}</div>`:`<div class="lb-rank">${{r}}</div>`}}
      <div class="lb-avatar" style="background:${{color}}">${{initials[item.school]||item.school.slice(0,3)}}</div>
      <div class="lb-info">
        <div class="lb-school">${{item.school}}</div>
        <div class="lb-pts-label">points</div>
      </div>
      <div class="lb-score${{r===1?' big':''}}" data-t="${{item.points}}">0</div>`;
    if(teamFilter===item.school)card.classList.add('active');
    card.addEventListener('click',()=>{{
      if(teamFilter===item.school){{teamFilter=null;card.classList.remove('active');}}
      else{{document.querySelectorAll('.lb-card').forEach(c=>c.classList.remove('active'));teamFilter=item.school;card.classList.add('active');}}
      renderEvents();
    }});
    grid.appendChild(card);
    setTimeout(()=>{{
      card.classList.add('anim');
      counter(card.querySelector('.lb-score'),item.points,900+i*60);
    }},i*55);
  }});
}}

function renderChips(){{
  const c=document.getElementById('chips');
  ['All','Sprints','Distance','Hurdles','Relays','Jumps','Throws','Multi'].forEach(cat=>{{
    const chip=document.createElement('button');
    chip.className='chip'+(cat===category?' active':'');
    chip.textContent=cat;
    chip.addEventListener('click',()=>{{
      category=cat;
      document.querySelectorAll('.chip').forEach(c=>c.classList.remove('active'));
      chip.classList.add('active');
      renderEvents();
    }});
    c.appendChild(chip);
  }});
}}

function renderEvents(){{
  const grid=document.getElementById('evGrid');
  grid.innerHTML='';
  let n=0;
  Object.entries(DATA.events).forEach(([key,ev])=>{{
    if(gender!=='combined'&&ev.gender!==gender)return;
    if(category!=='All'&&ev.category!==category)return;
    if(teamFilter&&!ev.top8.some(a=>a.school===teamFilter))return;

    const card=document.createElement('div');
    card.className='ev-card';
    const gLabel=ev.gender==='men'?'Men':'Women';
    const gClass=ev.gender==='men'?'g-m':'g-f';

    const prevRows=ev.top8.slice(0,3).map(a=>{{
      const d=teamFilter&&a.school!==teamFilter?' class="prev-row dimmed"':' class="prev-row"';
      return `<div${{d}}><span class="prev-rk">${{a.rank}}</span><span class="prev-name">${{a.name}}</span><span class="prev-school">${{a.school}}</span><span class="prev-mark">${{a.mark}}</span><span class="prev-pts">${{a.points}}</span></div>`;
    }}).join('');

    const tblRows=ev.top8.map(a=>{{
      const d=teamFilter&&a.school!==teamFilter?' class="dimmed"':'';
      const w=a.wind?` <small style="color:var(--text-3)">${{a.wind}}</small>`:'';
      return `<tr${{d}}><td>${{a.rank}}</td><td>${{a.name}}</td><td style="color:var(--text-2)">${{a.year||''}}</td><td style="color:var(--text-2)">${{a.school}}</td><td style="font-weight:600">${{a.mark}}${{w}}</td><td><span class="pts-cell">${{a.points}}</span></td></tr>`;
    }}).join('');

    card.innerHTML=`
      <div class="ev-head">
        <div class="ev-name-wrap">
          <span class="g-badge ${{gClass}}">${{gLabel}}</span>
          <span class="ev-name">${{ev.short_name}}</span>
        </div>
        <div style="display:flex;align-items:center;gap:8px">
          <span class="ev-cat">${{ev.category}}</span>
          <span class="ev-chevron">&#9660;</span>
        </div>
      </div>
      <div class="ev-preview">${{prevRows||'<p style="padding:8px 0;color:var(--text-3);font-size:13px">No Big West athletes ranked</p>'}}</div>
      <div class="ev-tbl-wrap">
        <table class="rt"><thead><tr><th>#</th><th>Athlete</th><th>Yr</th><th>School</th><th>Mark</th><th>Pts</th></tr></thead>
        <tbody>${{tblRows}}</tbody></table>
      </div>`;

    card.querySelector('.ev-head').addEventListener('click',()=>card.classList.toggle('open'));
    grid.appendChild(card);

    const delay=n*25;
    setTimeout(()=>{{
      const obs=new IntersectionObserver(entries=>{{
        entries.forEach(e=>{{if(e.isIntersecting){{e.target.classList.add('vis');obs.unobserve(e.target);}}}});
      }},{{threshold:.05}});
      obs.observe(card);
    }},delay);
    n++;
  }});

  if(!n){{
    grid.innerHTML=`<div class="empty"><div class="icon">🏃</div><p>No events match the current filters.</p></div>`;
  }}
}}

document.querySelectorAll('.pill').forEach(p=>{{
  p.addEventListener('click',()=>{{
    document.querySelectorAll('.pill').forEach(x=>x.classList.remove('active'));
    p.classList.add('active');
    gender=p.dataset.g;
    pillBg();
    teamFilter=null;
    renderLB();
    renderEvents();
  }});
}});

spawnParticles();
renderChips();
renderLB();
renderEvents();
requestAnimationFrame(pillBg);
</script>
</body>
</html>"""


def main():
    print("=" * 54)
    print("  Big West Championships Tracker  |  2026 Outdoor")
    print("=" * 54)
    print()
    print("Fetching event data from TFRRS...")
    print()

    all_events = fetch_all_events()

    if not all_events:
        print("\nWARNING: No event data retrieved.")
        sys.exit(1)

    print()
    print(f"Parsed {len(all_events)} events. Calculating scores...")
    data = calculate_scores(all_events)

    print()
    print("  Combined Leaderboard (projected):")
    for i, t in enumerate(data["team_scores"]["combined"], 1):
        bar = "█" * (t["points"] // 5)
        print(f"  {i:2d}. {t['school']:<22} {t['points']:>4} pts  {bar}")

    print()
    print("Generating HTML dashboard...")
    html_content = generate_html(data)

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"Saved: {out}")
    print("Opening in browser...")
    webbrowser.open("file://" + out)
    print("Done! ✓")


if __name__ == "__main__":
    main()
