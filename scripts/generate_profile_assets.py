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


def make_contribution_topography(calendar, username):
    """Render authentic daily GitHub counts as a compact isometric contribution field."""
    weeks = calendar.get("weeks") or []
    entries = [(wi, di, day) for wi, week in enumerate(weeks)
               for di, day in enumerate(week.get("contributionDays") or [])]
    total = int(calendar.get("totalContributions") or 0)
    maximum = max((int(day.get("contributionCount") or 0) for _, _, day in entries), default=0)

    def pt(x, y):
        return (round(x, 2), round(y, 2))

    tiles, towers = [], []
    for wi, di, day in entries:
        count = int(day.get("contributionCount") or 0)
        x = 62 + wi * 15.2 - di * 7.35
        y = 119 + wi * 0.24 + di * 10.05
        p1, p2 = pt(x, y), pt(x + 13.2, y + 0.25)
        p3, p4 = pt(x + 6.6, y + 9.35), pt(x - 6.6, y + 9.10)
        tiles.append(poly([p1, p2, p3, p4], "#193020" if count else "#14231a", .96))
        if not count:
            continue
        height = 8 + math.log2(count + 1) * 11.5
        a1, a2, a3, a4 = [(px, py - height) for px, py in (p1, p2, p3, p4)]
        # Three visible faces give each real contribution day an isometric column.
        towers.append(poly([a4, a3, p3, p4], "#294e2c", .98))
        towers.append(poly([a2, a3, p3, p2], "#416f37", .98))
        level = 1 if count == 1 else min(4, 1 + int(4 * count / max(1, maximum)))
        top_colors = ["#47743b", "#669a42", "#8fbd4c", "#b7ec61"]
        towers.append(poly([a1, a2, a3, a4], top_colors[level - 1], 1))

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="960" height="322" viewBox="0 0 960 322" role="img" aria-labelledby="title desc">
<title id="title">{esc(username)} contribution topography</title>
<desc id="desc">{total:,} real GitHub contributions in the calendar window. Each raised isometric column represents a day with contributions; height is logarithmically scaled from the GitHub contribution count.</desc>
<rect x="0.5" y="0.5" width="959" height="321" rx="15" fill="#0a100f" stroke="#30443a"/>
<text x="24" y="29" fill="#b7ef65" font-family="monospace" font-size="11" font-weight="700" letter-spacing="1.8">CONTRIBUTION TOPOGRAPHY / 3D</text>
<text x="24" y="55" fill="#b7ef65" font-family="monospace" font-size="18" font-weight="700">{total:,} contributions</text>
<text x="936" y="29" text-anchor="end" fill="#87978e" font-family="monospace" font-size="9" font-weight="700">GITHUB CALENDAR / 1 YEAR</text>
<g>{''.join(tiles)}</g><g>{''.join(towers)}</g>
<path d="M24 273H936" stroke="#27362f" stroke-width="1"/>
<text x="24" y="299" fill="#9aa99f" font-family="monospace" font-size="9">DATE → / HEIGHT = LOG-SCALED CONTRIBUTION COUNT</text>
<text x="936" y="299" text-anchor="end" fill="#9aa99f" font-family="monospace" font-size="9">GENERATED FROM GITHUB GRAPHQL</text>
</svg>'''

def make_contribution_trace(calendar, username):
    """Render the actual calendar cells and animate a path through active days."""
    weeks = calendar.get("weeks") or []
    entries = [(wi, di, day) for wi, week in enumerate(weeks)
               for di, day in enumerate(week.get("contributionDays") or [])]
    total = int(calendar.get("totalContributions") or 0)
    maximum = max((int(day.get("contributionCount") or 0) for _, _, day in entries), default=0)
    palette = ["#18251f", "#2d4b30", "#4d7838", "#83b84b", "#b8ef68"]
    cells, points = [], []
    for wi, di, day in entries:
        count = int(day.get("contributionCount") or 0)
        x, y = 24 + wi * 16.05, 48 + di * 15.0
        level = 0 if count == 0 else min(4, 1 + int(4 * count / max(1, maximum)))
        cells.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="12" height="11" rx="2" fill="{palette[level]}"/>')
        if count:
            points.append((x + 6, y + 5.5))

    path_d = ""
    if points:
        path_d = "M " + " L ".join(f"{x:.2f} {y:.2f}" for x, y in points)
    path_len = max(1, len(points) * 20)
    pulse = ""
    if points:
        last_x, last_y = points[-1]
        pulse = f'<circle cx="{last_x:.2f}" cy="{last_y:.2f}" r="2.2" fill="#e5ffc4"><animate attributeName="r" values="2;4;2" dur="2.4s" repeatCount="indefinite"/><animate attributeName="opacity" values="1;.45;1" dur="2.4s" repeatCount="indefinite"/></circle>'

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="960" height="190" viewBox="0 0 960 190" role="img" aria-labelledby="title desc">
<title id="title">{esc(username)} contribution trace</title>
<desc id="desc">Real GitHub contribution calendar cells for {total:,} contributions. Brighter cells represent days with more activity. The animated trace connects dates with recorded contributions; blank days remain unconnected.</desc>
<rect x="0.5" y="0.5" width="959" height="189" rx="15" fill="#0a100f" stroke="#30443a"/>
<text x="24" y="28" fill="#b7ef65" font-family="monospace" font-size="11" font-weight="700" letter-spacing="1.6">CONTRIBUTION TRACE / REAL ACTIVITY</text>
<g fill="none" stroke="#b7ef65" stroke-opacity=".26" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round">
<path d="{path_d}" pathLength="1000" stroke-dasharray="1000" stroke-dashoffset="1000"><animate attributeName="stroke-dashoffset" from="1000" to="0" dur="12s" repeatCount="indefinite"/></path>
</g>
<g>{''.join(cells)}</g>{pulse}
<text x="24" y="169" fill="#9aa99f" font-family="monospace" font-size="9">ANIMATED TRACE THROUGH CONTRIBUTION DAYS / CALENDAR IS NOT SIMULATED</text>
<text x="936" y="169" text-anchor="end" fill="#9aa99f" font-family="monospace" font-size="9">{total:,} VERIFIED CALENDAR CONTRIBUTIONS</text>
</svg>'''


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
    outputs = {"contribution-topography.svg":make_contribution_topography(calendar,username),
               "contribution-trace.svg":make_contribution_trace(calendar,username),
               "contribution-skyline.svg":make_skyline(calendar,username),
               "profile-stats.svg":make_stats(user),
               "wakatime-stats.svg":make_wakatime(os.environ.get("WAKATIME_API_KEY","").strip() or None)}
    for name,content in outputs.items():
        path=OUT/name
        path.write_text(content+"\n",encoding="utf-8")
        print(f"Generated {path.relative_to(ROOT)} ({path.stat().st_size} bytes)")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
