"""Builds the animated SVGs shown on the GitHub profile README.

Run by .github/workflows/profile.yml once a day. Standard library only.

    GITHUB_TOKEN=... python scripts/build.py            # live data
    python scripts/build.py --fixture data.json         # offline, for testing
"""
import argparse
import datetime as dt
import json
import os
import urllib.request
from html import escape
from pathlib import Path

USER = os.environ.get("PROFILE_USER", "Kirthan156")
OUT = Path(__file__).resolve().parent.parent / "assets"

# Repos and languages left out of the language card.
EXCLUDE_REPOS = {"Infosys-certificate", "IDS-ASSIGNMENT"}
EXCLUDE_LANGS = {"HTML", "CSS", "Procfile"}

PHRASES = [
    "streaming sensor data: OPC-UA -> Kafka -> InfluxDB",
    "fault diagnosis on 2.1M samples, macro F1 0.9998",
    "RAG + LangGraph agents that write SQL",
    "open to AI / ML / data roles, 2027",
]

THEMES = {
    "dark": dict(bg="#0d1117", panel="#161b22", line="#30363d", text="#e6edf3",
                 muted="#8b949e", accent="#2dd4bf", alert="#f85149", grid="#1b222c"),
    "light": dict(bg="#ffffff", panel="#f6f8fa", line="#d0d7de", text="#1f2328",
                  muted="#59636e", accent="#0f766e", alert="#cf222e", grid="#eef1f4"),
}

MONO = "ui-monospace, SFMono-Regular, Menlo, Consolas, 'Liberation Mono', monospace"
SANS = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif"

QUERY = """
query($login: String!) {
  user(login: $login) {
    followers { totalCount }
    pullRequests { totalCount }
    repositories(ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC, first: 100) {
      totalCount
      nodes {
        name
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { contributionCount date } }
      }
    }
  }
}
"""


def fetch(token):
    body = json.dumps({"query": QUERY, "variables": {"login": USER}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql", data=body,
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.load(resp)
    if "errors" in data:
        raise SystemExit(f"GraphQL error: {data['errors']}")
    return data["data"]["user"]


def summarise(user):
    days = [d for w in user["contributionsCollection"]["contributionCalendar"]["weeks"]
            for d in w["contributionDays"]]
    days.sort(key=lambda d: d["date"])
    counts = [d["contributionCount"] for d in days]

    longest = run = 0
    for c in counts:
        run = run + 1 if c else 0
        longest = max(longest, run)
    # Today often has no contributions yet; don't let that break the streak.
    current, i = 0, len(counts) - 1
    if i >= 0 and counts[i] == 0:
        i -= 1
    while i >= 0 and counts[i]:
        current += 1
        i -= 1

    weekly = [sum(d["contributionCount"] for d in w["contributionDays"])
              for w in user["contributionsCollection"]["contributionCalendar"]["weeks"]]

    langs = {}
    repos = [r for r in user["repositories"]["nodes"] if r["name"] not in EXCLUDE_REPOS]
    for r in repos:
        for e in r["languages"]["edges"]:
            name = e["node"]["name"]
            if name in EXCLUDE_LANGS:
                continue
            size, color = langs.get(name, (0, e["node"]["color"] or "#8b949e"))
            langs[name] = (size + e["size"], color)
    top = sorted(langs.items(), key=lambda kv: -kv[1][0])[:6]
    total = sum(s for _, (s, _) in top) or 1

    return dict(
        contributions=user["contributionsCollection"]["contributionCalendar"]["totalContributions"],
        current=current, longest=longest,
        repos=user["repositories"]["totalCount"],
        stars=sum(r["stargazerCount"] for r in repos),
        prs=user["pullRequests"]["totalCount"],
        followers=user["followers"]["totalCount"],
        weekly=weekly,
        langs=[(n, s / total, c) for n, (s, c) in top],
    )


def svg(w, h, t, body, extra_css=""):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img">
<style>
  .mono {{ font-family: {MONO}; }}
  .sans {{ font-family: {SANS}; }}
  .fade {{ opacity: 0; animation: fade .6s ease-out forwards; }}
  @keyframes fade {{ from {{ opacity: 0; transform: translateY(4px); }} to {{ opacity: 1; transform: none; }} }}
  {extra_css}
</style>
<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="12" fill="{t['bg']}" stroke="{t['line']}"/>
{body}
</svg>
"""


def waveform(x0, width, mid, amp, seed):
    """A vibration-like trace: two sines plus a fixed pseudo-random wobble."""
    import math
    pts = []
    for i in range(0, width + 1, 4):
        x = i / width * 2 * math.pi
        y = (math.sin(x * 3) * 0.55 + math.sin(x * 7 + seed) * 0.3
             + math.sin(x * 17 + seed * 2) * 0.15)
        pts.append(f"{x0 + i:.0f},{mid - y * amp:.1f}")
    return " ".join(pts)


def banner(t):
    w, h = 1000, 240
    cw, size = 10.8, 18  # monospace advance width forced with textLength
    n = len(PHRASES)
    cycle = 4.5 * n

    typing = []
    for k, phrase in enumerate(PHRASES):
        full = len(phrase) * cw
        start, slot = k / n, 1 / n
        chars = len(phrase)
        times, widths = [0.0], [0.0]
        type_end = start + slot * 0.45
        for c in range(chars + 1):
            times.append(start + (type_end - start) * c / chars + 1e-4)
            widths.append(c * cw)
        times += [start + slot * 0.9, start + slot * 0.9 + 1e-4, 1.0]
        widths += [full, 0.0, 0.0]
        clean_t, clean_w = [], []
        for tm, wd in zip(times, widths):
            tm = min(max(tm, 0.0), 1.0)
            if clean_t and tm <= clean_t[-1]:
                clean_w[-1] = wd
                continue
            clean_t.append(tm)
            clean_w.append(wd)
        kt = ";".join(f"{x:.4f}" for x in clean_t)
        vals = ";".join(f"{x:.1f}" for x in clean_w)
        cursor_vals = ";".join(f"{62 + x:.1f}" for x in clean_w)
        cursor_on = (f'keyTimes="0;{1 / n:.4f}" values="1;0"' if k == 0 else
                     f'keyTimes="0;{k / n:.4f};{(k + 1) / n:.4f}" values="0;1;0"')
        typing.append(f"""
  <clipPath id="c{k}"><rect x="62" y="128" height="30" width="0">
    <animate attributeName="width" dur="{cycle}s" repeatCount="indefinite" calcMode="discrete" keyTimes="{kt}" values="{vals}"/>
  </rect></clipPath>
  <text class="mono" x="62" y="150" font-size="{size}" fill="{t['text']}" textLength="{full:.1f}" lengthAdjust="spacingAndGlyphs" clip-path="url(#c{k})">{escape(phrase)}</text>
  <rect y="134" width="9" height="20" fill="{t['accent']}" x="62" opacity="{1 if k == 0 else 0}">
    <animate attributeName="x" dur="{cycle}s" repeatCount="indefinite" calcMode="discrete" keyTimes="{kt}" values="{cursor_vals}"/>
    <animate attributeName="opacity" dur="{cycle}s" repeatCount="indefinite" calcMode="discrete" {cursor_on}/>
  </rect>""")

    # Scrolling sensor trace on the right: the path is two copies wide and slides left by one copy.
    wx, ww, mid = 640, 320, 110
    trace = waveform(0, ww, 0, 26, 1.3)
    trace2 = " ".join(f"{float(p.split(',')[0]) + ww:.0f},{p.split(',')[1]}" for p in trace.split())
    body = f"""
<defs>
  <pattern id="grid" width="20" height="20" patternUnits="userSpaceOnUse">
    <path d="M20 0H0V20" fill="none" stroke="{t['grid']}" stroke-width="1"/>
  </pattern>
  <clipPath id="scope"><rect x="{wx}" y="40" width="{ww}" height="150" rx="8"/></clipPath>
</defs>
<rect x="{wx}" y="40" width="{ww}" height="150" rx="8" fill="{t['panel']}" stroke="{t['line']}"/>
<rect x="{wx}" y="40" width="{ww}" height="150" fill="url(#grid)" clip-path="url(#scope)"/>
<g clip-path="url(#scope)">
  <g class="scroll">
    <polyline transform="translate({wx},{mid})" points="{trace} {trace2}" fill="none" stroke="{t['accent']}" stroke-width="2" stroke-linejoin="round"/>
  </g>
</g>
<line x1="{wx + 12}" x2="{wx + ww - 12}" y1="{mid - 40}" y2="{mid - 40}" stroke="{t['alert']}" stroke-dasharray="4 4" opacity=".7"/>
<text class="mono" x="{wx + 14}" y="62" font-size="11" fill="{t['muted']}">vibration · ch0 · 1 kHz</text>
<text class="mono" x="{wx + ww - 14}" y="{mid - 46}" font-size="11" fill="{t['alert']}" text-anchor="end">alarm threshold</text>
<circle cx="{wx + ww - 22}" cy="174" r="4" fill="{t['accent']}" class="pulse"/>
<text class="mono" x="{wx + ww - 32}" y="178" font-size="11" fill="{t['muted']}" text-anchor="end">status: healthy</text>

<text class="mono fade" x="40" y="62" font-size="14" fill="{t['accent']}">// ML · data engineering · GenAI</text>
<text class="sans fade" x="40" y="108" font-size="40" font-weight="700" fill="{t['text']}" style="animation-delay:.1s">Kirthan Vivek Gada</text>
<text class="mono" x="40" y="150" font-size="{size}" fill="{t['accent']}">&gt;</text>
{''.join(typing)}
<text class="sans fade" x="40" y="200" font-size="14" fill="{t['muted']}" style="animation-delay:.3s">Hyderabad, India · B.Tech CSE (Data Science) '27 · VNR VJIET</text>
"""
    css = f"""
  .scroll {{ animation: scroll 6s linear infinite; }}
  @keyframes scroll {{ from {{ transform: translateX(0); }} to {{ transform: translateX(-{ww}px); }} }}
  .pulse {{ animation: pulse 1.6s ease-in-out infinite; transform-origin: {wx + ww - 22}px 174px; }}
  @keyframes pulse {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: .25; }} }}
"""
    return svg(w, h, t, body, css)


def stats_card(t, s):
    w, h = 480, 230
    rows = [
        ("Contributions (12 mo)", s["contributions"]),
        ("Current streak", f"{s['current']} d"),
        ("Longest streak", f"{s['longest']} d"),
        ("Public repos", s["repos"]),
        ("Stars earned", s["stars"]),
        ("Pull requests", s["prs"]),
    ]
    items = []
    for i, (label, value) in enumerate(rows):
        col, row = i % 2, i // 2
        x, y = 24 + col * 228, 74 + row * 42
        items.append(
            f'<g class="fade" style="animation-delay:{0.1 + i * 0.08:.2f}s">'
            f'<text class="mono" x="{x}" y="{y}" font-size="20" font-weight="600" fill="{t["text"]}">{escape(str(value))}</text>'
            f'<text class="sans" x="{x}" y="{y + 15}" font-size="11" fill="{t["muted"]}">{escape(label)}</text></g>')

    # Weekly contributions as a sparkline along the bottom.
    weekly = s["weekly"][-52:] or [0]
    peak = max(weekly) or 1
    sx, sw, sy, sh = 24, w - 48, h - 16, 26
    step = sw / max(len(weekly) - 1, 1)
    pts = " ".join(f"{sx + i * step:.1f},{sy - v / peak * sh:.1f}" for i, v in enumerate(weekly))
    area = f"{sx},{sy} {pts} {sx + sw:.1f},{sy}"
    length = sw * 3
    body = f"""
<text class="sans" x="24" y="36" font-size="15" font-weight="600" fill="{t['text']}">GitHub activity</text>
<text class="mono" x="{w - 24}" y="36" font-size="11" fill="{t['muted']}" text-anchor="end">@{USER}</text>
{''.join(items)}
<polygon points="{area}" fill="{t['accent']}" opacity=".12"/>
<polyline class="draw" points="{pts}" fill="none" stroke="{t['accent']}" stroke-width="1.5" stroke-linejoin="round"
  stroke-dasharray="{length:.0f}" stroke-dashoffset="{length:.0f}"/>
"""
    css = f".draw {{ animation: draw 1.8s ease-out .4s forwards; }} @keyframes draw {{ to {{ stroke-dashoffset: 0; }} }}"
    return svg(w, h, t, body, css)


def langs_card(t, s):
    w, h = 480, 230
    langs = s["langs"] or [("No data yet", 1.0, t["muted"])]
    bar, x = [], 24.0
    bw = w - 48
    for i, (name, share, color) in enumerate(langs):
        seg = bw * share
        bar.append(f'<rect class="grow" style="animation-delay:{i * 0.08:.2f}s" x="{x:.1f}" y="52" width="{max(seg - 2, 1):.1f}" height="8" rx="2" fill="{color}"/>')
        x += seg
    rows = []
    for i, (name, share, color) in enumerate(langs):
        col, row = i % 2, i // 2
        rx, ry = 24 + col * 228, 98 + row * 40
        rows.append(
            f'<g class="fade" style="animation-delay:{0.2 + i * 0.08:.2f}s">'
            f'<circle cx="{rx + 5}" cy="{ry - 4}" r="5" fill="{color}"/>'
            f'<text class="sans" x="{rx + 18}" y="{ry}" font-size="13" fill="{t["text"]}">{escape(name)}</text>'
            f'<text class="mono" x="{rx + 200}" y="{ry}" font-size="12" fill="{t["muted"]}" text-anchor="end">{share * 100:.1f}%</text></g>')
    body = f"""
<text class="sans" x="24" y="36" font-size="15" font-weight="600" fill="{t['text']}">Most used languages</text>
<rect x="24" y="52" width="{bw}" height="8" rx="2" fill="{t['panel']}"/>
<clipPath id="barclip"><rect x="24" y="52" width="{bw}" height="8" rx="4"/></clipPath>
<g clip-path="url(#barclip)">{''.join(bar)}</g>
{''.join(rows)}
"""
    css = (".grow { transform-box: fill-box; transform-origin: left; transform: scaleX(0); "
           "animation: grow .7s ease-out forwards; } @keyframes grow { to { transform: scaleX(1); } }")
    return svg(w, h, t, body, css)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture", help="JSON file with a GraphQL `user` payload, instead of calling the API")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()

    if args.fixture:
        user = json.loads(Path(args.fixture).read_text())
    else:
        token = os.environ.get("GITHUB_TOKEN")
        if not token:
            raise SystemExit("Set GITHUB_TOKEN or pass --fixture")
        user = fetch(token)

    s = summarise(user)
    args.out.mkdir(exist_ok=True)
    for name, t in THEMES.items():
        (args.out / f"banner-{name}.svg").write_text(banner(t))
        (args.out / f"stats-{name}.svg").write_text(stats_card(t, s))
        (args.out / f"languages-{name}.svg").write_text(langs_card(t, s))
    print(f"Wrote assets for {USER} at {dt.datetime.now(dt.timezone.utc):%Y-%m-%d %H:%M} UTC")


if __name__ == "__main__":
    main()
