"""
Big West Championships Tracker — Flask web app.
Auto-refreshes TFRRS data every 6 hours.
"""

import json
import logging
import os
import threading
from datetime import datetime, timezone

from flask import Flask, render_template_string, jsonify
from apscheduler.schedulers.background import BackgroundScheduler

from scraper import scrape_and_score, LIST_PAGE

app = Flask(__name__)
log = logging.getLogger("tracker")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

# ── In-memory cache ──
_cache = {
    "data": None,
    "updated_at": None,
    "refreshing": False,
}
_lock = threading.Lock()

REFRESH_HOURS = 6
CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data_cache.json")


def load_seed_data():
    """Load pre-baked data so the first page load is instant."""
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f:
                data = json.load(f)
            log.info(f"Loaded seed data from {CACHE_FILE} ({len(data.get('events', {}))} events)")
            return data
        except Exception as e:
            log.warning(f"Could not load seed data: {e}")
    return None


def save_cache(data):
    """Persist latest scrape to disk so restarts are fast."""
    try:
        with open(CACHE_FILE, "w") as f:
            json.dump(data, f)
    except Exception:
        pass


def refresh_data():
    """Scrape TFRRS and update cache. Safe to call from scheduler or on-demand."""
    with _lock:
        if _cache["refreshing"]:
            log.info("Refresh already in progress, skipping.")
            return
        _cache["refreshing"] = True

    log.info("Starting data refresh...")
    try:
        data = scrape_and_score(log=log.info)
        now = datetime.now(timezone.utc)
        with _lock:
            _cache["data"] = data
            _cache["updated_at"] = now.isoformat()
            _cache["refreshing"] = False
        save_cache(data)
        log.info(f"Data refreshed at {now.isoformat()} — {len(data['events'])} events")
    except Exception as e:
        log.error(f"Refresh failed: {e}")
        with _lock:
            _cache["refreshing"] = False


# ── Load seed data immediately, then schedule live refreshes ──
seed = load_seed_data()
if seed:
    _cache["data"] = seed
    _cache["updated_at"] = datetime.now(timezone.utc).isoformat()

scheduler = BackgroundScheduler(daemon=True)
scheduler.add_job(refresh_data, "interval", hours=REFRESH_HOURS, id="refresh")
scheduler.start()

# Kick off a background refresh so data gets updated from TFRRS soon
threading.Thread(target=refresh_data, daemon=True).start()


@app.route("/")
def index():
    with _lock:
        data = _cache["data"]
        updated = _cache["updated_at"]
        refreshing = _cache["refreshing"]

    if data is None and not refreshing:
        # Edge case: first visit before initial load completes
        refresh_data()
        with _lock:
            data = _cache["data"]
            updated = _cache["updated_at"]

    if data is None:
        return LOADING_HTML, 200

    return render_template_string(
        DASHBOARD_HTML,
        data_json=json.dumps(data),
        updated_at=updated or "",
        list_page=LIST_PAGE,
    )


@app.route("/api/data")
def api_data():
    with _lock:
        data = _cache["data"]
        updated = _cache["updated_at"]
        refreshing = _cache["refreshing"]
    return jsonify({"data": data, "updated_at": updated, "refreshing": refreshing})


@app.route("/api/refresh", methods=["POST"])
def api_refresh():
    threading.Thread(target=refresh_data, daemon=True).start()
    return jsonify({"status": "refresh_started"})


# ── Loading page (shown while first scrape runs) ──
LOADING_HTML = """<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Big West Championships Tracker</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0a0a0a;color:#f5f5f7;font-family:-apple-system,BlinkMacSystemFont,"SF Pro Display","Helvetica Neue",sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;text-align:center}
.loader{display:flex;flex-direction:column;align-items:center;gap:28px;animation:fade-in .6s ease}
@keyframes fade-in{from{opacity:0;transform:translateY(20px)}to{opacity:1;transform:translateY(0)}}
h1{font-size:1.8rem;font-weight:700;background:linear-gradient(135deg,#fff,#00e676);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text}
p{color:#a1a1a6;font-size:1rem}
.spinner{width:40px;height:40px;border:3px solid rgba(0,230,118,.15);border-top-color:#00e676;border-radius:50%;animation:spin .8s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
.hint{color:#48484a;font-size:13px;margin-top:12px}
</style>
<meta http-equiv="refresh" content="5">
</head><body>
<div class="loader">
<div class="spinner"></div>
<h1>Big West Championships Tracker</h1>
<p>Fetching live data from TFRRS&hellip;</p>
<p class="hint">This page refreshes automatically. First load takes ~30 seconds.</p>
</div>
</body></html>"""


# ── Dashboard HTML template ──
DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Big West Championships Tracker</title>
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#0a0a0a;--surface:#141414;--elevated:#1e1e1e;
  --border:rgba(255,255,255,0.07);
  --accent:#00e676;--accent-glow:rgba(0,230,118,0.2);--accent-dim:#00b04f;
  --gold:#ffd700;--silver:#c0c0c0;--bronze:#cd7f32;
  --text:#f5f5f7;--text-2:#a1a1a6;--text-3:#48484a;
  --r:16px;--r-sm:10px;--ease:cubic-bezier(.4,0,.2,1);
}
html{scroll-behavior:smooth}
body{background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,"SF Pro Display","Helvetica Neue",Arial,sans-serif;font-size:15px;line-height:1.5;overflow-x:hidden;min-height:100vh}

.particles{position:fixed;inset:0;pointer-events:none;z-index:0;overflow:hidden}
.pt{position:absolute;border-radius:50%;background:var(--accent);opacity:0;animation:float-pt linear infinite}
@keyframes float-pt{0%{transform:translateY(100vh) scale(0);opacity:0}10%{opacity:.12}90%{opacity:.04}100%{transform:translateY(-20vh) scale(1);opacity:0}}

.wrap{position:relative;z-index:1;max-width:1200px;margin:0 auto;padding:0 24px 80px}

.hero{text-align:center;padding:72px 0 52px}
.hero-badge{display:inline-flex;align-items:center;gap:8px;background:rgba(0,230,118,.1);border:1px solid rgba(0,230,118,.3);border-radius:100px;padding:6px 16px;font-size:12px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;color:var(--accent);margin-bottom:24px;animation:fade-up .6s ease both}
.hero-badge::before{content:"";width:6px;height:6px;border-radius:50%;background:var(--accent);animation:pulse-dot 2s ease-in-out infinite}
@keyframes pulse-dot{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.5;transform:scale(.7)}}
.hero h1{font-size:clamp(2rem,5vw,3.5rem);font-weight:700;letter-spacing:-.03em;line-height:1.1;background:linear-gradient(135deg,#fff 0%,var(--accent) 55%,#00b04f 100%);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;margin-bottom:12px;animation:fade-up .6s .1s ease both}
.hero-sub{color:var(--text-2);font-size:1.05rem;animation:fade-up .6s .2s ease both}
@keyframes fade-up{from{opacity:0;transform:translateY(20px)}to{opacity:1;transform:translateY(0)}}

.updated-bar{text-align:center;margin-bottom:32px;animation:fade-up .6s .25s ease both}
.updated-pill{display:inline-flex;align-items:center;gap:8px;background:var(--surface);border:1px solid var(--border);border-radius:100px;padding:6px 18px;font-size:12px;color:var(--text-3)}
.updated-pill .dot{width:6px;height:6px;border-radius:50%;background:var(--accent);flex-shrink:0}
.refresh-btn{background:none;border:1px solid var(--border);color:var(--text-2);border-radius:100px;padding:4px 12px;font-size:11px;cursor:pointer;margin-left:8px;font-family:inherit;transition:all .25s}
.refresh-btn:hover{border-color:var(--accent);color:var(--accent)}
.refresh-btn.spinning{pointer-events:none;opacity:.5}

.toggle-wrap{display:flex;justify-content:center;margin-bottom:44px;animation:fade-up .6s .3s ease both}
.pills{display:flex;background:var(--surface);border:1px solid var(--border);border-radius:100px;padding:4px;gap:2px;position:relative}
.pill{position:relative;z-index:1;padding:8px 26px;border-radius:100px;border:none;background:transparent;color:var(--text-2);font-size:14px;font-weight:500;cursor:pointer;transition:color .25s var(--ease);font-family:inherit}
.pill.active{color:var(--bg)}
.pill-bg{position:absolute;top:4px;left:4px;height:calc(100% - 8px);background:var(--accent);border-radius:100px;transition:left .3s var(--ease),width .3s var(--ease);box-shadow:0 0 20px var(--accent-glow);z-index:0}

.sec-title{font-size:1.4rem;font-weight:700;letter-spacing:-.02em;margin-bottom:20px;display:flex;align-items:center;gap:10px}
.sec-title::after{content:"";flex:1;height:1px;background:var(--border)}

.lb-section{margin-bottom:56px}
.lb-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(270px,1fr));gap:12px}
.lb-card{background:var(--surface);border:1px solid var(--border);border-radius:var(--r);padding:16px 20px;display:flex;align-items:center;gap:14px;cursor:pointer;transition:transform .3s var(--ease),border-color .3s var(--ease),box-shadow .3s var(--ease);opacity:0;position:relative;overflow:hidden}
.lb-card::before{content:"";position:absolute;inset:0;background:linear-gradient(135deg,var(--accent-glow),transparent 60%);opacity:0;transition:opacity .3s var(--ease)}
.lb-card:hover{transform:translateY(-2px);border-color:rgba(0,230,118,.3);box-shadow:0 8px 32px rgba(0,0,0,.4)}
.lb-card:hover::before{opacity:1}
.lb-card.active{border-color:var(--accent)!important;box-shadow:0 0 0 1px var(--accent),0 0 28px var(--accent-glow)!important}
.lb-card.anim{animation:slide-left .45s ease both}
@keyframes slide-left{from{opacity:0;transform:translateX(-28px)}to{opacity:1;transform:translateX(0)}}
.lb-rank{font-size:1rem;font-weight:800;width:26px;text-align:center;flex-shrink:0;color:var(--text-3)}
.lb-medal{font-size:1.3rem;width:26px;text-align:center;flex-shrink:0;animation:shimmer 3s ease-in-out infinite}
@keyframes shimmer{0%,100%{filter:brightness(1)}50%{filter:brightness(1.5) drop-shadow(0 0 6px currentColor)}}
.lb-avatar{width:42px;height:42px;border-radius:12px;display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:800;letter-spacing:.02em;color:#fff;flex-shrink:0;text-shadow:0 1px 3px rgba(0,0,0,.6)}
.lb-info{flex:1;min-width:0}
.lb-school{font-weight:600;font-size:.9rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.lb-pts-label{font-size:11px;color:var(--text-3);text-transform:uppercase;letter-spacing:.06em}
.lb-score{font-size:1.6rem;font-weight:800;letter-spacing:-.03em;color:var(--accent);text-align:right;min-width:44px;font-variant-numeric:tabular-nums}
.lb-score.big{font-size:2rem}

.chips-wrap{margin-bottom:28px}
.chips{display:flex;gap:8px;flex-wrap:wrap}
.chip{padding:7px 16px;border-radius:100px;border:1px solid var(--border);background:var(--surface);color:var(--text-2);font-size:13px;font-weight:500;cursor:pointer;transition:all .25s var(--ease);font-family:inherit}
.chip:hover{border-color:rgba(0,230,118,.3);color:var(--text)}
.chip.active{background:rgba(0,230,118,.12);border-color:var(--accent);color:var(--accent)}

.ev-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:14px}
.ev-card{background:var(--surface);border:1px solid var(--border);border-radius:var(--r);overflow:hidden;transition:transform .3s var(--ease),border-color .3s var(--ease),box-shadow .3s var(--ease);opacity:0;transform:translateY(18px)}
.ev-card:hover{transform:translateY(-2px);border-color:rgba(0,230,118,.2);box-shadow:0 10px 36px rgba(0,0,0,.35)}
.ev-card.vis{animation:ev-in .4s ease both}
@keyframes ev-in{from{opacity:0;transform:translateY(18px)}to{opacity:1;transform:translateY(0)}}
.ev-head{padding:14px 18px;display:flex;align-items:center;justify-content:space-between;cursor:pointer;user-select:none;border-bottom:1px solid transparent;transition:border-color .25s,background .25s}
.ev-card.open .ev-head{border-bottom-color:var(--border);background:rgba(0,230,118,.04)}
.ev-name-wrap{display:flex;align-items:center;gap:9px}
.g-badge{font-size:10px;font-weight:700;letter-spacing:.08em;padding:3px 8px;border-radius:6px;text-transform:uppercase}
.g-m{background:rgba(100,160,255,.15);color:#64a0ff}
.g-f{background:rgba(255,100,160,.15);color:#ff64a0}
.ev-name{font-weight:600;font-size:.92rem}
.ev-cat{font-size:11px;color:var(--text-3);font-weight:500}
.ev-chevron{color:var(--text-3);transition:transform .25s var(--ease);font-size:11px}
.ev-card.open .ev-chevron{transform:rotate(180deg)}

.ev-preview{padding:2px 18px 14px}
.prev-row{display:flex;align-items:center;gap:8px;padding:6px 0;border-bottom:1px solid rgba(255,255,255,.04);font-size:13px}
.prev-row:last-child{border-bottom:none}
.prev-rk{width:18px;text-align:center;font-size:11px;font-weight:700;color:var(--text-3);flex-shrink:0}
.prev-name{flex:1;font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.prev-school{color:var(--text-2);font-size:12px;white-space:nowrap;flex-shrink:0}
.prev-mark{font-weight:600;font-variant-numeric:tabular-nums;font-size:13px;min-width:58px;text-align:right;flex-shrink:0}
.prev-pts{background:rgba(0,230,118,.12);color:var(--accent);font-size:11px;font-weight:700;padding:2px 7px;border-radius:6px;min-width:26px;text-align:center;flex-shrink:0}

.ev-tbl-wrap{display:none;padding:0 18px 16px}
.ev-card.open .ev-tbl-wrap{display:block}
table.rt{width:100%;border-collapse:collapse;font-size:13px}
table.rt th{text-align:left;color:var(--text-3);font-size:11px;font-weight:600;letter-spacing:.06em;text-transform:uppercase;padding:8px 6px;border-bottom:1px solid var(--border)}
table.rt td{padding:9px 6px;border-bottom:1px solid rgba(255,255,255,.03);vertical-align:middle}
table.rt tr:last-child td{border-bottom:none}
table.rt tr:hover td{background:rgba(255,255,255,.02)}
.pts-cell{background:rgba(0,230,118,.1);color:var(--accent);font-weight:700;border-radius:6px;padding:3px 8px!important;text-align:center}

.empty{text-align:center;padding:60px 20px;color:var(--text-3);grid-column:1/-1}
.empty .icon{font-size:2.5rem;margin-bottom:14px}

footer{text-align:center;padding:32px 24px;color:var(--text-3);font-size:12px;border-top:1px solid var(--border);margin-top:40px}
footer a{color:var(--accent-dim);text-decoration:none}
footer a:hover{color:var(--accent)}

::-webkit-scrollbar{width:8px}
::-webkit-scrollbar-track{background:var(--bg)}
::-webkit-scrollbar-thumb{background:var(--elevated);border-radius:4px}
.dimmed{opacity:.3}
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

  <div class="updated-bar">
    <span class="updated-pill">
      <span class="dot"></span>
      <span id="updatedText">Last updated: {{ updated_at[:16].replace('T',' ') }} UTC</span>
      <button class="refresh-btn" id="refreshBtn" onclick="triggerRefresh()">Refresh</button>
    </span>
  </div>

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
  Data sourced from <a href="{{ list_page }}" target="_blank">TFRRS Big West Outdoor Performance List</a>
  &middot; Auto-refreshes every 6 hours &middot; 10-8-6-5-4-3-2-1 top 8 scoring &middot; Projections only
</footer>

<script>
const DATA = {{ data_json|safe }};
let gender='combined',category='All',teamFilter=null;

const initials={
  'Cal Poly':'CP','Cal St. Fullerton':'CSF','CSUN':'CSUN','CSU Bakersfield':'CSUB',
  'Long Beach St.':'LBS','UC Davis':'UCD','UC Irvine':'UCI','UC Riverside':'UCR',
  'UC San Diego':'UCSD','UC Santa Barbara':'UCSB','Hawaii':'HAW'
};

function medal(r){return r===1?'\\u{1F947}':r===2?'\\u{1F948}':r===3?'\\u{1F949}':null}
function counter(el,target,ms=1100){let s=null;(function step(ts){if(!s)s=ts;const p=Math.min((ts-s)/ms,1),e=1-Math.pow(1-p,3);el.textContent=Math.round(target*e);if(p<1)requestAnimationFrame(step)})(performance.now())}
function spawnParticles(){const c=document.getElementById('pts');for(let i=0;i<20;i++){const p=document.createElement('div');p.className='pt';const sz=Math.random()*4+2;p.style.cssText=`width:${sz}px;height:${sz}px;left:${Math.random()*100}%;animation-duration:${9+Math.random()*14}s;animation-delay:${Math.random()*12}s`;c.appendChild(p)}}
function pillBg(){const a=document.querySelector('.pill.active'),bg=document.getElementById('pillBg');if(!a)return;bg.style.left=a.offsetLeft+'px';bg.style.width=a.offsetWidth+'px'}

function renderLB(){
  const grid=document.getElementById('lbGrid');grid.innerHTML='';
  DATA.team_scores[gender].forEach((item,i)=>{
    const r=i+1,m=medal(r),color=DATA.school_colors[item.school]||'#333';
    const card=document.createElement('div');card.className='lb-card';card.dataset.school=item.school;
    card.innerHTML=`${m?`<div class="lb-medal">${m}</div>`:`<div class="lb-rank">${r}</div>`}<div class="lb-avatar" style="background:${color}">${initials[item.school]||item.school.slice(0,3)}</div><div class="lb-info"><div class="lb-school">${item.school}</div><div class="lb-pts-label">points</div></div><div class="lb-score${r===1?' big':''}" data-t="${item.points}">0</div>`;
    if(teamFilter===item.school)card.classList.add('active');
    card.addEventListener('click',()=>{if(teamFilter===item.school){teamFilter=null;card.classList.remove('active')}else{document.querySelectorAll('.lb-card').forEach(c=>c.classList.remove('active'));teamFilter=item.school;card.classList.add('active')}renderEvents()});
    grid.appendChild(card);
    setTimeout(()=>{card.classList.add('anim');counter(card.querySelector('.lb-score'),item.points,900+i*60)},i*55);
  });
}

function renderChips(){
  const c=document.getElementById('chips');
  ['All','Sprints','Distance','Hurdles','Relays','Jumps','Throws','Multi'].forEach(cat=>{
    const chip=document.createElement('button');chip.className='chip'+(cat===category?' active':'');chip.textContent=cat;
    chip.addEventListener('click',()=>{category=cat;document.querySelectorAll('.chip').forEach(c=>c.classList.remove('active'));chip.classList.add('active');renderEvents()});
    c.appendChild(chip);
  });
}

function renderEvents(){
  const grid=document.getElementById('evGrid');grid.innerHTML='';let n=0;
  Object.entries(DATA.events).forEach(([key,ev])=>{
    if(gender!=='combined'&&ev.gender!==gender)return;
    if(category!=='All'&&ev.category!==category)return;
    if(teamFilter&&!ev.top8.some(a=>a.school===teamFilter))return;
    const card=document.createElement('div');card.className='ev-card';
    const gLabel=ev.gender==='men'?'Men':'Women',gClass=ev.gender==='men'?'g-m':'g-f';
    const prevRows=ev.top8.slice(0,3).map(a=>{const d=teamFilter&&a.school!==teamFilter?' class="prev-row dimmed"':' class="prev-row"';return `<div${d}><span class="prev-rk">${a.rank}</span><span class="prev-name">${a.name}</span><span class="prev-school">${a.school}</span><span class="prev-mark">${a.mark}</span><span class="prev-pts">${a.points}</span></div>`}).join('');
    const tblRows=ev.top8.map(a=>{const d=teamFilter&&a.school!==teamFilter?' class="dimmed"':'';const w=a.wind?` <small style="color:var(--text-3)">${a.wind}</small>`:'';return `<tr${d}><td>${a.rank}</td><td>${a.name}</td><td style="color:var(--text-2)">${a.year||''}</td><td style="color:var(--text-2)">${a.school}</td><td style="font-weight:600">${a.mark}${w}</td><td><span class="pts-cell">${a.points}</span></td></tr>`}).join('');
    card.innerHTML=`<div class="ev-head"><div class="ev-name-wrap"><span class="g-badge ${gClass}">${gLabel}</span><span class="ev-name">${ev.short_name}</span></div><div style="display:flex;align-items:center;gap:8px"><span class="ev-cat">${ev.category}</span><span class="ev-chevron">&#9660;</span></div></div><div class="ev-preview">${prevRows||'<p style="padding:8px 0;color:var(--text-3);font-size:13px">No Big West athletes ranked</p>'}</div><div class="ev-tbl-wrap"><table class="rt"><thead><tr><th>#</th><th>Athlete</th><th>Yr</th><th>School</th><th>Mark</th><th>Pts</th></tr></thead><tbody>${tblRows}</tbody></table></div>`;
    card.querySelector('.ev-head').addEventListener('click',()=>card.classList.toggle('open'));
    grid.appendChild(card);
    setTimeout(()=>{const obs=new IntersectionObserver(entries=>{entries.forEach(e=>{if(e.isIntersecting){e.target.classList.add('vis');obs.unobserve(e.target)}})},{threshold:.05});obs.observe(card)},n*25);
    n++;
  });
  if(!n)grid.innerHTML='<div class="empty"><div class="icon">\\u{1F3C3}</div><p>No events match the current filters.</p></div>';
}

function triggerRefresh(){
  const btn=document.getElementById('refreshBtn');
  btn.textContent='Refreshing...';btn.classList.add('spinning');
  fetch('/api/refresh',{method:'POST'}).then(()=>{
    setTimeout(()=>location.reload(),35000);
  });
}

document.querySelectorAll('.pill').forEach(p=>{
  p.addEventListener('click',()=>{document.querySelectorAll('.pill').forEach(x=>x.classList.remove('active'));p.classList.add('active');gender=p.dataset.g;pillBg();teamFilter=null;renderLB();renderEvents()});
});

spawnParticles();renderChips();renderLB();renderEvents();requestAnimationFrame(pillBg);
</script>
</body>
</html>"""


if __name__ == "__main__":
    app.run(debug=True, port=5000)
