#!/usr/bin/env python3
"""Generate locally stored profile SVGs from GitHub GraphQL and optional WakaTime."""
from __future__ import annotations
import base64, datetime as dt, html, json, math, os, sys, urllib.error, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "generated"
BG, PANEL = "#1a1b26", "#24283b"
TEXT, MUTED = "#c0caf5", "#7982a9"
CYAN, PURPLE, PINK = "#7dcfff", "#bb9af7", "#f7768e"
ORANGE, BLUE, GREEN = "#ff9e64", "#7aa2f7", "#9ece6a"

def esc(value):
    return html.escape(str(value), quote=True)

def get_json(url, method="GET", headers=None, payload=None):
    body = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=body, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code}: {exc.read().decode('utf-8','replace')[:400]}") from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Request failed: {exc}") from exc

def github_data(token, username):
    now = dt.datetime.now(dt.timezone.utc)
    start = now - dt.timedelta(days=365)
    query = """
    query ProfileData($login: String!, $from: DateTime!, $to: DateTime!) {
      user(login: $login) {
        login
        contributionsCollection(from: $from, to: $to) {
          totalCommitContributions totalIssueContributions totalPullRequestContributions
          contributionCalendar { totalContributions weeks { contributionDays { date contributionCount } } }
        }
        repositories(first: 100, ownerAffiliations: OWNER, privacy: PUBLIC, isFork: false,
          orderBy: {field: UPDATED_AT, direction: DESC}) {
          nodes { stargazerCount languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
            edges { size node { name color } }
          } }
        }
      }
    }
    """
    variables = {"login": username,
      "from": start.isoformat(timespec="seconds").replace("+00:00","Z"),
      "to": now.isoformat(timespec="seconds").replace("+00:00","Z")}
    result = get_json("https://api.github.com/graphql", "POST",
      {"Authorization": f"Bearer {token}", "Content-Type": "application/json",
       "User-Agent": "obunto-byte-profile-assets"},
      {"query": query, "variables": variables})
    if result.get("errors"):
        raise RuntimeError("GitHub GraphQL: " + "; ".join(x.get("message","error") for x in result["errors"]))
    user = (result.get("data") or {}).get("user")
    if not user:
        raise RuntimeError(f"GitHub profile {username!r} not returned")
    return user

def poly(points, fill, opacity=1):
    coords = " ".join(f"{x:.1f},{y:.1f}" for x,y in points)
    return f'<polygon points="{coords}" fill="{fill}" opacity="{opacity:.2f}"/>'

def make_skyline(calendar, username):
    weeks = calendar.get("weeks") or []
    entries = [(wi,di,d) for wi,w in enumerate(weeks) for di,d in enumerate(w.get("contributionDays") or [])]
    maximum = max((int(d.get("contributionCount") or 0) for _,_,d in entries), default=0)
    total = int(calendar.get("totalContributions") or 0)
    colors = ["#292e42","#3d4c75","#536da8","#7aa2f7","#bb9af7"]
    shapes = []
    for wi,di,day in entries:
        count = int(day.get("contributionCount") or 0)
        level = 0 if not count else min(4, 1 + int(4*count/max(1,maximum)))
        cx, by = 250+(wi-di)*14, 145+(wi+di)*5.3
        ty = by - math.sqrt(count)*5
        top, left, right, bottom = (cx,ty),(cx-7,ty+4.5),(cx+7,ty+4.5),(cx,ty+9)
        if count:
            shapes.append(poly([top,left,(cx-7,by+4.5),(cx,by)],"#3b4261"))
            shapes.append(poly([top,right,(cx+7,by+4.5),(cx,by)],"#565f89"))
        shapes.append(poly([top,right,bottom,left],colors[level],.92))
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="600" viewBox="0 0 1200 600" role="img" aria-labelledby="title desc">
<title id="title">{esc(username)} contribution skyline</title>
<desc id="desc">{total} contributions in the last 365 days. Each day is an isometric building, with height scaled using the square root of its contribution count.</desc>
<defs><linearGradient id="bg" x2="1" y2="1"><stop stop-color="#1a1b26"/><stop offset="1" stop-color="#10121d"/></linearGradient><pattern id="grid" width="36" height="36" patternUnits="userSpaceOnUse"><path d="M36 0H0V36" fill="none" stroke="#7c85aa" stroke-opacity=".08"/></pattern></defs>
<rect width="1200" height="600" rx="22" fill="url(#bg)"/><rect width="1200" height="600" rx="22" fill="url(#grid)"/>
<text x="48" y="58" fill="{CYAN}" font-family="monospace" font-size="14" letter-spacing="3">XEBAC HAT / ACTIVITY INTELLIGENCE</text>
<text x="48" y="100" fill="{TEXT}" font-family="monospace" font-size="29" font-weight="700">CONTRIBUTION SKYLINE</text>
<text x="48" y="126" fill="{MUTED}" font-family="monospace" font-size="13">365-DAY WINDOW • SQRT-SCALED ISOMETRIC BUILDINGS</text>
<path d="M48 150H1152" stroke="#7aa2f7" stroke-opacity=".35"/><g>{''.join(shapes)}</g>
<text x="48" y="548" fill="{MUTED}" font-family="monospace" font-size="12">LOWER ACTIVITY</text>
<g transform="translate(190 538)"><rect width="16" height="10" rx="2" fill="#292e42"/><rect x="23" width="16" height="10" rx="2" fill="#3d4c75"/><rect x="46" width="16" height="10" rx="2" fill="#536da8"/><rect x="69" width="16" height="10" rx="2" fill="#7aa2f7"/><rect x="92" width="16" height="10" rx="2" fill="#bb9af7"/></g>
<text x="1148" y="548" text-anchor="end" fill="{MUTED}" font-family="monospace" font-size="12">HIGHER ACTIVITY</text>
<text x="48" y="580" fill="{MUTED}" font-family="monospace" font-size="11">A DAY-BY-DAY MAP OF CONSISTENCY — NOT A RANKING</text>
<text x="1148" y="58" text-anchor="end" fill="{PURPLE}" font-family="monospace" font-size="20" font-weight="700">{total:,}</text><text x="1148" y="80" text-anchor="end" fill="{MUTED}" font-family="monospace" font-size="10">CONTRIBUTIONS</text></svg>'''

def make_stats(user):
    cc, repos = user["contributionsCollection"], user.get("repositories",{}).get("nodes",[])
    calendar = cc["contributionCalendar"]
    metrics = [
      ("CONTRIBUTIONS",int(calendar.get("totalContributions") or 0),CYAN),
      ("COMMITS",int(cc.get("totalCommitContributions") or 0),PURPLE),
      ("PULL REQUESTS",int(cc.get("totalPullRequestContributions") or 0),PINK),
      ("ISSUES",int(cc.get("totalIssueContributions") or 0),ORANGE),
      ("PUBLIC REPOS",len(repos),BLUE),
      ("STARS EARNED",sum(int(r.get("stargazerCount") or 0) for r in repos),GREEN)]
    cards = []
    for i,(label,value,color) in enumerate(metrics):
        x,y = 48+(i%3)*368,150+(i//3)*120
        cards.append(f'<rect x="{x}" y="{y}" width="336" height="92" rx="13" fill="{PANEL}" stroke="#414868"/><text x="{x+20}" y="{y+30}" fill="{MUTED}" font-family="monospace" font-size="12">{label}</text><text x="{x+20}" y="{y+69}" fill="{color}" font-family="monospace" font-size="29" font-weight="700">{value:,}</text>')
    langs = {}
    for repo in repos:
        for edge in (repo.get("languages") or {}).get("edges",[]):
            node = edge.get("node") or {}
            if node.get("name"):
                item = langs.setdefault(node["name"],{"size":0,"color":node.get("color") or CYAN})
                item["size"] += int(edge.get("size") or 0)
    top = sorted(langs.items(),key=lambda x:x[1]["size"],reverse=True)[:6]
    total_size = sum(x["size"] for _,x in top) or 1
    bars = []
    for i,(name,item) in enumerate(top):
        y,width = 430+i*24,530*item["size"]/total_size
        bars.append(f'<text x="50" y="{y+11}" fill="{TEXT}" font-family="monospace" font-size="13">{esc(name)}</text><rect x="220" y="{y}" width="530" height="12" rx="6" fill="#292e42"/><rect x="220" y="{y}" width="{width:.1f}" height="12" rx="6" fill="{esc(item["color"])}"/><text x="770" y="{y+11}" fill="{MUTED}" font-family="monospace" font-size="12">{100*item["size"]/total_size:.1f}%</text>')
    if not bars:
        bars.append(f'<text x="50" y="445" fill="{MUTED}" font-family="monospace" font-size="14">No public language data returned yet.</text>')
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="610" viewBox="0 0 1200 610" role="img" aria-labelledby="title desc">
<title id="title">XEBAC HAT GitHub diagnostics</title><desc id="desc">Locally generated GitHub contribution totals, public repository count, stars and top languages.</desc>
<rect width="1200" height="610" rx="22" fill="{BG}" stroke="#414868"/>
<text x="48" y="56" fill="{CYAN}" font-family="monospace" font-size="14" letter-spacing="3">LOCAL SNAPSHOT / GITHUB GRAPHQL</text><text x="48" y="104" fill="{TEXT}" font-family="monospace" font-size="30" font-weight="700">PROFILE DIAGNOSTICS</text>
<text x="1150" y="56" text-anchor="end" fill="{MUTED}" font-family="monospace" font-size="12">ROLLING 365 DAYS</text>{''.join(cards)}
<text x="48" y="390" fill="{PURPLE}" font-family="monospace" font-size="16" font-weight="700">LANGUAGE FOOTPRINT / TOP REPOSITORY LANGUAGES</text>{''.join(bars)}
<text x="48" y="580" fill="{MUTED}" font-family="monospace" font-size="11">Generated by this repository's workflow • source: GitHub GraphQL API</text></svg>'''

def make_wakatime(api_key):
    if not api_key:
        return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="260" viewBox="0 0 1200 260" role="img" aria-labelledby="title desc"><title id="title">WakaTime setup</title><desc id="desc">Optional WakaTime panel awaiting the API key secret.</desc><rect width="1200" height="260" rx="22" fill="{BG}" stroke="#414868"/><text x="44" y="58" fill="{CYAN}" font-family="monospace" font-size="14">OPTIONAL MODULE / WAKATIME</text><text x="44" y="112" fill="{TEXT}" font-family="monospace" font-size="28">CODING TIME TELEMETRY</text><text x="44" y="158" fill="{MUTED}" font-family="monospace" font-size="16">Add WAKATIME_API_KEY under Settings → Secrets and variables → Actions.</text></svg>'''
    auth = base64.b64encode(api_key.encode()).decode()
    try:
        payload = get_json("https://wakatime.com/api/v1/users/current/stats/last_7_days",
          headers={"Authorization":f"Basic {auth}","User-Agent":"obunto-byte-profile-assets"})
        data, rows = payload.get("data") or {}, []
        for i,lang in enumerate((payload.get("data") or {}).get("languages",[])[:7]):
            y = 115+i*20
            pct = max(0.0,min(100.0,float(lang.get("percent") or 0)))
            color = lang.get("color") or [CYAN,PURPLE,PINK,ORANGE,BLUE,GREEN,"#e0af68"][i]
            rows.append(f'<text x="48" y="{y+10}" fill="{TEXT}" font-family="monospace" font-size="12">{esc(lang.get("name","Other"))}</text><rect x="220" y="{y}" width="650" height="10" rx="5" fill="#292e42"/><rect x="220" y="{y}" width="{6.5*pct:.1f}" height="10" rx="5" fill="{esc(color)}"/><text x="890" y="{y+10}" fill="{MUTED}" font-family="monospace" font-size="11">{pct:.1f}%</text><text x="980" y="{y+10}" fill="{MUTED}" font-family="monospace" font-size="11">{esc(lang.get("text",""))}</text>')
        if not rows:
            rows.append(f'<text x="48" y="145" fill="{MUTED}" font-family="monospace" font-size="14">No language activity returned for the last seven days.</text>')
        return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="300" viewBox="0 0 1200 300" role="img" aria-labelledby="title desc"><title id="title">WakaTime coding stats</title><desc id="desc">WakaTime language breakdown from the last seven days.</desc><rect width="1200" height="300" rx="22" fill="{BG}" stroke="#414868"/><text x="48" y="45" fill="{CYAN}" font-family="monospace" font-size="13">WAKATIME / LAST 7 DAYS</text><text x="1150" y="45" text-anchor="end" fill="{PURPLE}" font-family="monospace" font-size="18">{esc(data.get("human_readable_total","last 7 days"))}</text>{''.join(rows)}<text x="48" y="278" fill="{MUTED}" font-family="monospace" font-size="11">Fetched and rendered by GitHub Actions • SVG stored in this repository</text></svg>'''
    except Exception as exc:
        return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="200" viewBox="0 0 1200 200" role="img"><rect width="1200" height="200" rx="22" fill="{BG}" stroke="#414868"/><text x="44" y="60" fill="{CYAN}" font-family="monospace" font-size="14">WAKATIME / TEMPORARILY UNAVAILABLE</text><text x="44" y="108" fill="{TEXT}" font-family="monospace" font-size="15">{esc(str(exc)[:150])}</text><text x="44" y="150" fill="{MUTED}" font-family="monospace" font-size="12">The profile refresh continues; this optional module retries next run.</text></svg>'''

def main():
    token = os.environ.get("GITHUB_TOKEN","").strip()
    username = os.environ.get("GITHUB_USERNAME","obunto-byte").strip()
    if not token:
        print("GITHUB_TOKEN is required.",file=sys.stderr)
        return 2
    user = github_data(token,username)
    OUT.mkdir(parents=True,exist_ok=True)
    calendar = user["contributionsCollection"]["contributionCalendar"]
    outputs = {"contribution-skyline.svg":make_skyline(calendar,username),
               "profile-stats.svg":make_stats(user),
               "wakatime-stats.svg":make_wakatime(os.environ.get("WAKATIME_API_KEY","").strip() or None)}
    for name,content in outputs.items():
        path=OUT/name
        path.write_text(content+"\n",encoding="utf-8")
        print(f"Generated {path.relative_to(ROOT)} ({path.stat().st_size} bytes)")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
