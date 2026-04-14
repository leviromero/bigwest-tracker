"""
TFRRS scraper and score calculator for Big West Conference T&F.
"""

import requests
import warnings
import time
import json
from bs4 import BeautifulSoup
from collections import defaultdict

warnings.filterwarnings("ignore")

BASE_URL = "https://www.tfrrs.org/list_data/5660"
LIST_PAGE = "https://www.tfrrs.org/lists/5660/Big_West_Outdoor_Performance_List"

POINTS_TABLE = {1: 10, 2: 8, 3: 6, 4: 5, 5: 4, 6: 3, 7: 2, 8: 1}

EVENTS = [
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
    "cal poly": "Cal Poly", "cal poly slo": "Cal Poly",
    "california polytechnic": "Cal Poly", "cal poly san luis obispo": "Cal Poly",
    "cal st. fullerton": "Cal St. Fullerton", "csuf": "Cal St. Fullerton",
    "cal state fullerton": "Cal St. Fullerton", "california state fullerton": "Cal St. Fullerton",
    "csun": "CSUN", "cal st. northridge": "CSUN",
    "cal state northridge": "CSUN", "california state northridge": "CSUN",
    "long beach st.": "Long Beach St.", "long beach state": "Long Beach St.",
    "csulb": "Long Beach St.", "csu long beach": "Long Beach St.",
    "csu bakersfield": "CSU Bakersfield", "cal st. bakersfield": "CSU Bakersfield",
    "cal state bakersfield": "CSU Bakersfield", "california state bakersfield": "CSU Bakersfield",
    "uc davis": "UC Davis", "california-davis": "UC Davis",
    "uc irvine": "UC Irvine", "california-irvine": "UC Irvine", "uci": "UC Irvine",
    "uc riverside": "UC Riverside", "california-riverside": "UC Riverside", "ucr": "UC Riverside",
    "uc san diego": "UC San Diego", "california-san diego": "UC San Diego", "ucsd": "UC San Diego",
    "uc santa barbara": "UC Santa Barbara", "california-santa barbara": "UC Santa Barbara", "ucsb": "UC Santa Barbara",
    "hawaii": "Hawaii", "hawai'i": "Hawaii", "university of hawaii": "Hawaii", "hawaii rainbow": "Hawaii",
}

BIG_WEST_SCHOOLS = {
    "Cal Poly", "Cal St. Fullerton", "CSUN", "CSU Bakersfield",
    "Long Beach St.", "UC Davis", "UC Irvine", "UC Riverside",
    "UC San Diego", "UC Santa Barbara", "Hawaii",
}

SCHOOL_COLORS = {
    "Cal Poly": "#154734", "Cal St. Fullerton": "#FF6600", "CSUN": "#CC0000",
    "CSU Bakersfield": "#00205B", "Long Beach St.": "#222222", "UC Davis": "#022851",
    "UC Irvine": "#0064A4", "UC Riverside": "#003DA5", "UC San Diego": "#182B49",
    "UC Santa Barbara": "#003660", "Hawaii": "#024731",
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
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/vnd.turbo-stream.html, text/html, application/xhtml+xml",
        "Referer": LIST_PAGE,
        "Turbo-Frame": "list_data",
    }
    params = {"event_type": event_type, "gender": gender, "limit": str(limit)}
    resp = requests.get(BASE_URL, params=params, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.text


def parse_event_html(html: str) -> list:
    soup = BeautifulSoup(html, "html.parser")
    rows = soup.find_all("div", class_="performance-list-row")
    athletes = []

    for row in rows:
        def col(label):
            el = row.find("div", attrs={"data-label": label})
            return el.get_text(strip=True) if el else ""

        is_relay = "is-relay" in row.get("class", [])
        team_div = row.find("div", class_="col-team")
        school_raw = team_div.get_text(strip=True) if team_div else ""
        school = normalize_school(school_raw)

        if is_relay:
            name = school_raw
            year = ""
        else:
            athlete_div = row.find("div", class_="col-athlete")
            name = athlete_div.get_text(strip=True) if athlete_div else ""
            if not name:
                continue
            if "," in name:
                parts = name.split(",", 1)
                name = parts[1].strip() + " " + parts[0].strip()
            year = col("Year")

        if not name:
            continue

        mark = col("Time") or col("Mark") or col("Distance") or col("Height")
        wind = col("Wind")

        athletes.append({
            "name": name, "school": school, "school_raw": school_raw,
            "mark": mark, "year": year, "wind": wind or None,
            "in_big_west": school in BIG_WEST_SCHOOLS,
        })

    return athletes


def fetch_all_events(log=print) -> dict:
    all_events = {}
    total = len(EVENTS)

    for i, (event_type, gender_code, short_name, gender_label) in enumerate(EVENTS, 1):
        event_key = f"{gender_label} {short_name}"
        log(f"  [{i:2d}/{total}] {event_key}...")
        try:
            html = fetch_event(event_type, gender_code, limit=50)
            athletes = parse_event_html(html)
            if athletes:
                all_events[event_key] = {
                    "athletes": athletes,
                    "short_name": short_name,
                    "gender": gender_label.lower(),
                    "category": get_category(short_name),
                }
        except Exception as e:
            log(f"    ERROR: {e}")
        time.sleep(0.3)

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
            school_best = {}
            for a in bw:
                s = a["school"]
                val = mark_to_float(a["mark"], short_name)
                if s not in school_best or val < school_best[s][0]:
                    school_best[s] = (val, a)
            bw = [v[1] for v in sorted(school_best.values(), key=lambda x: x[0])]
        else:
            reverse = is_field or is_multi
            bw = sorted(bw, key=lambda a: mark_to_float(a["mark"], short_name), reverse=reverse)

        top8 = bw[:8]
        scored = []
        for rank, athlete in enumerate(top8, 1):
            pts = POINTS_TABLE.get(rank, 0)
            school = athlete["school"]
            scored.append({
                "rank": rank, "name": athlete["name"], "school": school,
                "mark": athlete["mark"], "year": athlete.get("year", ""),
                "wind": athlete.get("wind"), "points": pts,
            })
            team_scores_combined[school] += pts
            if gender == "men":
                team_scores_men[school] += pts
            else:
                team_scores_women[school] += pts

        processed_events[event_key] = {
            "short_name": short_name, "gender": gender,
            "category": category, "top8": scored,
        }

    def make_board(scores):
        board = [{"school": s, "points": scores.get(s, 0)} for s in BIG_WEST_SCHOOLS]
        return sorted(board, key=lambda x: x["points"], reverse=True)

    return {
        "team_scores": {
            "combined": make_board(team_scores_combined),
            "men": make_board(team_scores_men),
            "women": make_board(team_scores_women),
        },
        "events": processed_events,
        "school_colors": SCHOOL_COLORS,
    }


def scrape_and_score(log=print) -> dict:
    """Full pipeline: fetch all events, calculate scores, return data dict."""
    log("Fetching event data from TFRRS...")
    all_events = fetch_all_events(log=log)
    log(f"Parsed {len(all_events)} events. Calculating scores...")
    data = calculate_scores(all_events)
    return data
