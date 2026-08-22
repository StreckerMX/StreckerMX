from __future__ import annotations

import html
import json
import os
import re
import textwrap
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

OWNER = "StreckerMX"
REPO = "FrameView-Analyzer"
BASE = f"https://api.github.com/repos/{OWNER}/{REPO}"
TOKEN = os.environ.get("GITHUB_TOKEN", "")

def api(path: str):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "StreckerMX-profile-updater",
    }
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    req = urllib.request.Request(BASE + path, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)

def safe_api(path: str, default):
    try:
        return api(path)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return default

def esc(value: object) -> str:
    return html.escape(str(value), quote=False)

def date_only(value: str | None) -> str:
    if not value:
        return "N/A"
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).strftime("%Y-%m-%d")
    except ValueError:
        return value[:10]

repo = safe_api("", {})
release = safe_api("/releases/latest", {})
commits = safe_api("/commits?sha=main&per_page=1", [])
runs = safe_api("/actions/runs?branch=main&status=completed&per_page=10", {"workflow_runs": []})
pulls = safe_api("/pulls?state=open&per_page=100", [])
languages = safe_api("/languages", {})

latest_commit = commits[0] if commits else {}
commit_data = latest_commit.get("commit", {})
commit_message = (commit_data.get("message") or "No commit data").splitlines()[0]
commit_message = textwrap.shorten(commit_message, width=58, placeholder="…")
commit_date = (commit_data.get("committer") or {}).get("date") or (commit_data.get("author") or {}).get("date")

workflow_runs = runs.get("workflow_runs", []) if isinstance(runs, dict) else []
ci_conclusion = next((r.get("conclusion") for r in workflow_runs if r.get("conclusion")), None)
ci_status = {
    "success": "PASSING",
    "failure": "FAILING",
    "cancelled": "CANCELLED",
    "timed_out": "TIMED OUT",
    "action_required": "ACTION REQUIRED",
    "neutral": "NEUTRAL",
    "skipped": "SKIPPED",
}.get(ci_conclusion, "UNKNOWN")

data = {
    "latest_release": release.get("tag_name") or release.get("name") or "No release",
    "stars": repo.get("stargazers_count", 0),
    "ci": ci_status,
    "prs": len(pulls) if isinstance(pulls, list) else 0,
    "language": max(languages, key=languages.get) if languages else repo.get("language") or "C#",
    "release_date": date_only(release.get("published_at") or release.get("created_at")),
    "commit_sha": (latest_commit.get("sha") or "N/A")[:7],
    "commit_msg": commit_message,
    "commit_date": date_only(commit_date),
    "sync": datetime.now(timezone.utc).strftime("%Y-%m-%d UTC"),
}

W, H = 1440, 9000
defs: list[str] = []
body: list[str] = []
typed: list[str] = []
counter = 0

defs.append(r'''
<linearGradient id="scan" x1="0" y1="0" x2="0" y2="1">
  <stop offset="0" stop-color="#76B900" stop-opacity="0"/>
  <stop offset=".30" stop-color="#76B900" stop-opacity=".018"/>
  <stop offset=".50" stop-color="#76B900" stop-opacity=".15"/>
  <stop offset=".70" stop-color="#76B900" stop-opacity=".018"/>
  <stop offset="1" stop-color="#76B900" stop-opacity="0"/>
</linearGradient>
<filter id="glow" x="-80%" y="-80%" width="260%" height="260%">
  <feGaussianBlur stdDeviation="8" result="b"/>
  <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
</filter>
<style>
.sans{font-family:Inter,"Segoe UI",Arial,sans-serif}
.mono{font-family:ui-monospace,"Cascadia Mono","Cascadia Code",Consolas,monospace}
.fg{fill:#F4F6F8}.muted{fill:#A5AFB9}.dim{fill:#6D7883}.green{fill:#76B900}.cyan{fill:#00D4FF}.pink{fill:#FF6FAE}
.rule{stroke:#fff;stroke-opacity:.075;stroke-width:1.35}
.terminalOutline{fill:none;stroke:#454545;stroke-width:1.6}.terminalTop{fill:#2D2D2D}.tabActive{fill:#0A0A0A}
.tabText{font-size:20px;font-weight:600}.topIcon{font-size:27px}.windowButton{font-size:22px}
.ps{font-size:20px;font-weight:700}.hero{font-size:82px;font-weight:720}.heroSub{font-size:23px;letter-spacing:.10em}
.lead{font-size:27px}.terminalTitle{font-size:17px;letter-spacing:.16em;font-weight:600}
.terminalHeading{font-size:30px;font-weight:650}.prompt{font-size:21px;font-weight:650}.code{font-size:19px}
.body{font-size:21px}.metricLabel{font-size:16px;letter-spacing:.10em}.metricValue{font-size:21px;font-weight:620}
.metricBig{font-size:27px;font-weight:680}.footer{font-size:17px;letter-spacing:.12em}
</style>
<g id="wtTop">
  <rect width="1216" height="64" rx="14" class="terminalTop"/>
  <rect width="246" height="64" rx="14" class="tabActive"/><rect y="48" width="246" height="16" class="tabActive"/>
  <text x="34" y="40" class="sans fg tabText">strecker</text><text x="214" y="41" class="sans fg topIcon">×</text>
  <line x1="246" y1="10" x2="246" y2="54" stroke="#444"/><text x="274" y="42" class="sans fg topIcon">＋</text>
  <line x1="316" y1="10" x2="316" y2="54" stroke="#444"/><text x="338" y="39" class="sans fg topIcon">⌄</text>
  <text x="1034" y="41" class="sans fg windowButton">−</text><text x="1100" y="39" class="sans fg windowButton">□</text><text x="1170" y="41" class="sans fg windowButton">×</text>
</g>
''')

def type_text(x: int, y: int, text: object, cls: str, begin: float, dur: float = .75,
              width: int | None = None, anchor: str | None = None, clip_x: int | None = None):
    global counter
    counter += 1
    value = esc(text)
    if width is None:
        width = min(1160, max(70, len(re.sub(r"&[^;]+;", "X", value)) * 13 + 28))
    cx = clip_x if clip_x is not None else x
    cid = f"t{counter}"
    defs.append(
        f'<clipPath id="{cid}"><rect x="{cx}" y="{y-34}" width="0" height="48">'
        f'<animate attributeName="width" from="0" to="{width}" begin="{begin:.2f}s" dur="{dur:.2f}s" fill="freeze"/>'
        f'</rect></clipPath>'
    )
    anchor_attr = f' text-anchor="{anchor}"' if anchor else ""
    typed.append(f'<text x="{x}" y="{y}" class="{cls}" clip-path="url(#{cid})"{anchor_attr}>{value}</text>')

def shell(y: int, h: int):
    body.append(f'<rect x="112" y="{y}" width="1216" height="{h}" rx="14" class="terminalOutline"/>')
    body.append(f'<g transform="translate(112 {y})"><use href="#wtTop"/></g>')

body += [
    f'<rect width="{W}" height="{H}" rx="34" fill="#000000"/>',
    f'<rect x="2" y="2" width="{W-4}" height="{H-4}" rx="32" fill="none" stroke="#76B900" stroke-opacity=".10" stroke-width="2"/>',
    f'<rect x="28" y="28" width="{W-56}" height="{H-56}" rx="28" fill="none" stroke="#FFFFFF" stroke-opacity=".035"/>',
    f'<rect y="-620" width="{W}" height="620" fill="url(#scan)"><animate attributeName="y" from="-620" to="{H+620}" dur="36s" repeatCount="indefinite"/></rect>',
]

type_text(112,238,"Strecker","sans fg hero",.20,.70,420)
body.append('<rect x="114" y="268" width="170" height="9" rx="4.5" fill="#76B900" opacity="0"><animate attributeName="opacity" from="0" to="1" begin=".8s" dur=".08s" fill="freeze"/></rect>')
type_text(112,346,"WINDOWS SOFTWARE / PERFORMANCE / AUTOMATION / LOCAL AI","mono muted heroSub",1.0,1.15,1030)
type_text(112,418,"Practical software. Measurable performance. Clear interfaces.","sans muted lead",2.2,1.0,910)
type_text(112,540,"❯ whoami","mono cyan prompt",3.3,.55,190)
type_text(144,590,"developer building fast, practical desktop tools and technical workflows","mono muted code",3.9,1.25,860)
type_text(112,660,"❯ status --current","mono cyan prompt",5.2,.65,270)
type_text(144,710,"building · measuring · refining · shipping","mono green code",5.9,1.0,650)

y=860; shell(y,900); t=1.0
for text,x,dy,cls,dur,width in [
    ("PowerShell 7.6.5",142,118,"mono green ps",.8,240),
    ("01 / IDENTITY",142,176,"mono cyan terminalTitle",.65,220),
    ("What I build",142,236,"sans pink terminalHeading",.8,270),
    ("Desktop software and workflows where performance, clarity, and repeatability matter.",142,290,"sans muted body",1.3,1050),
    ("❯ whoami",142,390,"mono cyan prompt",.55,180),
    ("developer building fast, practical desktop tools",174,438,"mono muted code",1.0,650),
    ("❯ priorities",142,520,"mono cyan prompt",.60,210),
    ("predictable behavior · readable complexity · measurable results",174,568,"mono muted code",1.1,820),
]:
    type_text(x,y+dy,text,cls,t,dur,width); t += dur+.10
body.append(f'<line x1="142" y1="{y+640}" x2="1298" y2="{y+640}" class="rule"/>')
for text,x,cls,w in [("PRIMARY",142,"mono dim metricLabel",110),("C# / .NET",350,"mono fg metricValue",180),
                     ("UI",760,"mono dim metricLabel",60),("WPF / Windows",890,"mono fg metricValue",230)]:
    type_text(x,y+710,text,cls,t,.45,w); t += .35

y=1940; shell(y,1160); t=8.5
for text,x,dy,cls,dur,w in [
    ("PowerShell 7.6.5",142,118,"mono green ps",.75,240),("02 / FOCUS",142,176,"mono cyan terminalTitle",.55,180),
    ("Where I spend my time",142,236,"sans pink terminalHeading",.9,420),
    ("The same themes keep showing up across the tools I build.",142,290,"sans muted body",1.05,800),
    ("❯ performance",142,390,"mono cyan prompt",.55,230),("Benchmarking · telemetry · filtering · visualization",174,438,"mono fg code",.9,670),
    ("Turn noisy technical data into something you can inspect, compare, and trust.",174,482,"mono muted code",1.25,980),
    ("❯ automation",142,590,"mono cyan prompt",.55,210),("Repeatable workflows instead of repeated effort",174,638,"mono fg code",.9,700),
    ("Scripts, CI, and practical AI tooling that remove friction from development.",174,682,"mono muted code",1.25,980),
    ("❯ interface-design",142,790,"mono cyan prompt",.65,270),("Technical software should still feel polished",174,838,"mono fg code",.9,650),
    ("Information hierarchy and visual feedback are part of engineering.",174,882,"mono muted code",1.1,850),
]:
    type_text(x,y+dy,text,cls,t,dur,w); t += dur+.10

y=3280; shell(y,1100); t=16.0
for text,x,dy,cls,dur,w in [
    ("PowerShell 7.6.5",142,118,"mono green ps",.75,240),("03 / TOOLBOX",142,176,"mono cyan terminalTitle",.55,220),
    ("Tools I reach for",142,236,"sans pink terminalHeading",.8,320),
    ("A compact stack for desktop work, automation, testing, and delivery.",142,290,"sans muted body",1.15,900),
]:
    type_text(x,y+dy,text,cls,t,dur,w); t += dur+.10
body.append(f'<line x1="142" y1="{y+350}" x2="1298" y2="{y+350}" class="rule"/>')
for lab,val,col,dy in [
    ("LANGUAGE","C#","fg",435),("RUNTIME",".NET 10","fg",517),("DESKTOP UI","WPF","fg",599),
    ("AUTOMATION","Python · PowerShell","fg",681),("DELIVERY","GitHub Actions · Releases","fg",763),
    ("AI WORKFLOWS","Local models · API-assisted development","green",845),
]:
    type_text(142,y+dy,lab,"mono dim metricLabel",t,.42,180); t+=.30
    type_text(410,y+dy,val,f"mono {col} metricValue",t,.70,620); t+=.50

y=4560; shell(y,960); t=21.0
for text,x,dy,cls,dur,w in [
    ("PowerShell 7.6.5",142,118,"mono green ps",.75,240),("04 / WORKFLOW",142,176,"mono cyan terminalTitle",.55,220),
    ("How I like to work",142,236,"sans pink terminalHeading",.8,350),
    ("Small feedback loops, measurable results, and less ceremony.",142,290,"sans muted body",1.05,800),
]:
    type_text(x,y+dy,text,cls,t,dur,w); t += dur+.10
for cmd,desc,dy in [
    ("01 inspect","understand the actual problem",410),("02 build","prefer the simplest clear solution",500),
    ("03 measure","test performance, behavior, and UX",590),("04 refine","remove friction and fragile edges",680),
]:
    type_text(142,y+dy,cmd,"mono cyan prompt",t,.50,190); t+=.30
    type_text(400,y+dy,desc,"mono muted code",t,.75,650); t+=.55

y=5680; shell(y,1540); t=25.4
for text,x,dy,cls,dur,w in [
    ("PowerShell 7.6.5",142,118,"mono green ps",.75,240),
    ("05 / LIVE PROJECT TELEMETRY",142,176,"mono cyan terminalTitle",.75,420),
    ("FrameView Analyzer",142,236,"sans pink terminalHeading",.85,360),
    ("Real repository data, refreshed automatically by GitHub Actions.",142,290,"sans muted body",1.1,850),
]:
    type_text(x,y+dy,text,cls,t,dur,w); t += dur+.10
type_text(1298,y+118,f"SYNC {data['sync']}","mono dim code",t,.8,280,"end",1010); t+=.9
body.append(f'<line x1="142" y1="{y+360}" x2="1298" y2="{y+360}" class="rule"/>')
for lab,val,x,col in [
    ("LATEST RELEASE",data["latest_release"],142,"fg"),("STARS",data["stars"],510,"fg"),
    ("CI",data["ci"],760,"green"),("OPEN PRS",data["prs"],1060,"fg"),
]:
    type_text(x,y+450,lab,"mono dim metricLabel",t,.42,190); t+=.28
    type_text(x,y+505,val,f"mono {col} metricBig",t,.50,220); t+=.38
body.append(f'<line x1="142" y1="{y+590}" x2="1298" y2="{y+590}" class="rule"/>')
for lab,val,x1,x2 in [
    ("PRIMARY LANGUAGE",data["language"],142,450),("RELEASE DATE",data["release_date"],770,1040),
]:
    type_text(x1,y+680,lab,"mono dim metricLabel",t,.45,230); t+=.30
    type_text(x2,y+680,val,"mono fg metricValue",t,.50,250); t+=.38
for text,x,dy,cls,dur,w in [
    ("❯ git log -1 --oneline",142,820,"mono cyan prompt",.65,320),
    (f"{data['commit_sha']}  {data['commit_msg']}",174,875,"mono fg code",1.3,1000),
    (f"committed {data['commit_date']}",174,925,"mono dim code",.7,400),
]:
    type_text(x,y+dy,text,cls,t,dur,w); t += dur+.10
body.append(f'<line x1="142" y1="{y+1000}" x2="1298" y2="{y+1000}" class="rule"/>')
for text,x,dy,cls,dur,w in [
    ("STATUS",142,1090,"mono dim metricLabel",.4,100),
    ("BUILDING · REFINING · RELEASING",410,1090,"mono green metricValue",.9,520),
    ("Native Windows benchmark analysis for NVIDIA FrameView captures and NVIDIA App logs.",142,1190,"sans muted body",1.25,1100),
    ("Telemetry is generated from the repository itself, not a third-party badge service.",142,1240,"sans muted body",1.15,1000),
]:
    type_text(x,y+dy,text,cls,t,dur,w); t += dur+.10

y=7420; shell(y,980); final_start=t+1.0
type_text(142,y+118,"PowerShell 7.6.5","mono green ps",final_start,.75,240)
type_text(142,y+198,"❯","mono cyan prompt",final_start+.9,.30,40)
body.append(
    f'<rect x="174" y="{y+174}" width="12" height="28" rx="1" fill="#76B900" opacity="0">'
    f'<animate attributeName="opacity" values="0;1;1;0" keyTimes="0;.1;.55;1" begin="{final_start+1.25:.2f}s" dur="1.1s" repeatCount="indefinite"/>'
    f'</rect>'
)

body += [
    '<line x1="112" y1="8580" x2="1328" y2="8580" class="rule"/>',
    '<text x="112" y="8650" class="mono dim footer">PROFILE INTERFACE / WINDOWS TERMINAL / TYPED SESSION / LIVE TELEMETRY</text>',
    '<text x="1328" y="8650" class="mono dim footer" text-anchor="end">GITHUB.COM/STRECKERMX</text>',
    '<circle cx="112" cy="8720" r="6" fill="#76B900" filter="url(#glow)"/><text x="140" y="8728" class="mono green ps">still building</text>',
]

svg = (
    f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-labelledby="title desc">'
    '<title id="title">Strecker developer profile</title>'
    '<desc id="desc">Windows Terminal shells visible immediately, typed content, live GitHub telemetry, a soft green scan, and a final waiting prompt.</desc>'
    f'<defs>{"".join(defs)}</defs>{"".join(body)}{"".join(typed)}</svg>'
)

Path("assets/profile-hero.svg").write_text(svg, encoding="utf-8")
print("Updated assets/profile-hero.svg")
print("Telemetry:", data)
print(f"Generated {counter} typed lines; final prompt at {final_start + 1.25:.1f}s")
