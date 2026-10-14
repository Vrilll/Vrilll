"""Build the PROJECTS.LIST cards for the profile README.

Reads projects.json, fetches live repo data (stars, languages, last push) from the
GitHub API when GITHUB_TOKEN is set, embeds each logo from logos/, and writes one
dark and one light SVG per project plus a header strip into the output folder.

Standard library only, so it runs on a plain GitHub Actions runner.
Usage: python3 .github/scripts/build_cards.py projects.json out/
"""
import base64
import datetime as dt
import json
import math
import os
import sys
import urllib.request
from html import escape

W, H = 600, 200
MIME = {".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}
MERGE = {"Hack": "PHP", "Blade": "PHP"}  # Linguist sometimes labels .php files as Hack

THEMES = {
    "dark": dict(bg="#07040D", card="#0E0818", stroke="#2A1747", text="#F4ECF7", muted="#A99BB8",
                 dim="#6B5A7E", head="#E33DBF", tag_bg="#24103F", tag_text="#D9B8F2", track="#24103F",
                 l1="#E33DBF", l2="#7B4DE0", l3="#A99BB8", live="#E33DBF"),
    "light": dict(bg="#FFFFFF", card="#FBF7FD", stroke="#E4D6EE", text="#1A0F2B", muted="#5E4E70",
                  dim="#9C8DAE", head="#A0087F", tag_bg="#EFE3F7", tag_text="#5A1A8C", track="#EFE3F7",
                  l1="#A0087F", l2="#3A1B99", l3="#9C8DAE", live="#A0087F"),
}
FONT_MONO = "'JetBrains Mono','Fira Code','SFMono-Regular',Consolas,'Liberation Mono',Menlo,monospace"
FONT_SANS = "-apple-system,'Segoe UI','Inter','Helvetica Neue',Arial,sans-serif"


def api(path, token):
    req = urllib.request.Request("https://api.github.com" + path, headers={
        "Accept": "application/vnd.github+json", "User-Agent": "profile-cards",
        **({"Authorization": f"Bearer {token}"} if token else {})})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def live_data(owner, repo, token):
    try:
        meta = api(f"/repos/{owner}/{repo}", token)
        langs = api(f"/repos/{owner}/{repo}/languages", token)
        return dict(stars=meta.get("stargazers_count", 0), pushed=meta.get("pushed_at"), langs=langs)
    except Exception as e:  # offline or rate-limited: render without live numbers
        print(f"  ! {repo}: live data unavailable ({e})")
        return None


def shares(langs):
    merged = {}
    for k, v in (langs or {}).items():
        k = MERGE.get(k, k)
        merged[k] = merged.get(k, 0) + v
    tot = sum(merged.values())
    if not tot:
        return []
    return [(k, v * 100 / tot) for k, v in sorted(merged.items(), key=lambda kv: -kv[1])]


def ago(iso):
    if not iso:
        return ""
    t = dt.datetime.fromisoformat(iso.replace("Z", "+00:00"))
    d = (dt.datetime.now(dt.timezone.utc) - t).days
    if d < 1:
        return "updated today"
    if d < 30:
        return f"updated {d}d ago"
    if d < 365:
        return f"updated {d // 30}mo ago"
    return f"updated {d // 365}y ago"


def wrap(text, width=54, lines=2):
    words, out, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + (1 if cur else 0) > width:
            out.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    out.append(cur)
    if len(out) > lines:
        out = out[:lines]
        out[-1] = out[-1][: width - 1].rstrip() + "…"
    return out


def logo_tag(root, path, x, y, size, name):
    full = os.path.join(root, path) if path else ""
    if full and os.path.isfile(full):
        ext = os.path.splitext(full)[1].lower()
        data = base64.b64encode(open(full, "rb").read()).decode()
        uri = f"data:{MIME.get(ext, 'image/png')};base64,{data}"
        return (f'<clipPath id="lc"><rect x="{x}" y="{y}" width="{size}" height="{size}" rx="10"/></clipPath>'
                f'<image x="{x}" y="{y}" width="{size}" height="{size}" clip-path="url(#lc)" preserveAspectRatio="xMidYMid slice" href="{uri}"/>')
    # fallback: initial on a brand tile
    return (f'<rect x="{x}" y="{y}" width="{size}" height="{size}" rx="10" fill="url(#tile)"/>'
            f'<text x="{x + size / 2}" y="{y + size * 0.66}" text-anchor="middle" font-family="{FONT_MONO}" '
            f'font-weight="700" font-size="{size * 0.45:.0f}" fill="#FFFFFF">{escape(name[:1])}</text>')


def card(p, owner, live, root, t):
    url = f"https://github.com/{owner}/{p['repo']}"
    s = shares(live["langs"]) if live else shares(p.get("langs"))
    parts = [f'<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="12" fill="{t["card"]}" stroke="{t["stroke"]}"/>',
             f'<text x="20" y="28" font-family="{FONT_MONO}" font-size="12" fill="{t["dim"]}">&#8226; {escape(owner.lower())}/{escape(p["repo"])}</text>',
             f'<circle cx="{W - 22}" cy="24" r="4" fill="{t["live"]}"><animate attributeName="opacity" values="1;.3;1" dur="2.4s" repeatCount="indefinite"/></circle>',
             logo_tag(root, p.get("logo"), 20, 46, 48, p["name"])]
    tx = 84
    parts.append(f'<text x="{tx}" y="66" font-family="{FONT_SANS}" font-weight="700" font-size="18" fill="{t["text"]}">'
                 f'{escape(p["name"])}<tspan fill="{t["head"]}">_</tspan></text>')
    for i, line in enumerate(wrap(p.get("desc", ""))):
        parts.append(f'<text x="{tx}" y="{90 + i * 18}" font-family="{FONT_SANS}" font-size="12.5" fill="{t["muted"]}">{escape(line)}</text>')
    cx = tx
    for tag in p.get("tags", [])[:4]:
        tw = 16 + len(tag) * 7.0
        parts.append(f'<rect x="{cx:.0f}" y="138" width="{tw:.0f}" height="20" rx="10" fill="{t["tag_bg"]}"/>'
                     f'<text x="{cx + tw / 2:.0f}" y="152" text-anchor="middle" font-family="{FONT_MONO}" font-size="11" fill="{t["tag_text"]}">{escape(tag)}</text>')
        cx += tw + 8
    foot = []
    if live:
        foot.append(f"★ {live['stars']}")
        if live.get("pushed"):
            foot.append(ago(live["pushed"]))
    if foot:
        parts.append(f'<text x="{tx}" y="182" font-family="{FONT_MONO}" font-size="11" fill="{t["dim"]}">{escape("  ·  ".join(foot))}</text>')
    if s:
        r, dcx, dcy = 26, W - 56, 76
        circ = 2 * math.pi * r
        on = circ * s[0][1] / 100
        parts.append(f'<circle cx="{dcx}" cy="{dcy}" r="{r}" fill="none" stroke="{t["track"]}" stroke-width="8"/>'
                     f'<circle cx="{dcx}" cy="{dcy}" r="{r}" fill="none" stroke="url(#ring)" stroke-width="8" stroke-linecap="round" '
                     f'stroke-dasharray="{on:.1f} {circ:.1f}" transform="rotate(-90 {dcx} {dcy})"/>'
                     f'<text x="{dcx}" y="{dcy + 5}" text-anchor="middle" font-family="{FONT_MONO}" font-weight="700" font-size="14" fill="{t["text"]}">{round(s[0][1])}%</text>')
        rx = W - 22
        for i, (lang, v) in enumerate(s[:3]):
            col = (t["l1"], t["l2"], t["l3"])[i]
            ly = 128 + i * 17
            parts.append(f'<text x="{rx - 12}" y="{ly}" text-anchor="end" font-family="{FONT_MONO}" font-size="11" fill="{t["muted"]}">{escape(lang)} {v:.0f}%</text>'
                         f'<circle cx="{rx - 3}" cy="{ly - 4}" r="4" fill="{col}"/>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="{escape(p["name"])}">'
            f'<defs><linearGradient id="tile" x1="0" y1="1" x2="1" y2="0"><stop offset="0" stop-color="#3A1B99"/><stop offset="1" stop-color="#B30994"/></linearGradient>'
            f'<linearGradient id="ring" x1="0" y1="1" x2="1" y2="0"><stop offset="0" stop-color="#3A1B99"/><stop offset="1" stop-color="#E33DBF"/></linearGradient></defs>'
            f'<a href="{url}" target="_blank">{"".join(parts)}</a></svg>\n')


def header(t, count):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="44" viewBox="0 0 1200 44" role="img" aria-label="Projects">'
            f'<rect width="1200" height="44" rx="10" fill="{t["card"]}" stroke="{t["stroke"]}"/>'
            f'<text x="20" y="28" font-family="{FONT_MONO}" font-weight="700" font-size="13" letter-spacing="1.5" fill="{t["head"]}">PROJECTS.LIST</text>'
            f'<text x="150" y="28" font-family="{FONT_MONO}" font-size="12" fill="{t["dim"]}">./projects.sh --selected  ({count})</text>'
            f'<text x="1180" y="28" text-anchor="end" font-family="{FONT_MONO}" font-size="12" fill="{t["dim"]}">click a card to open the repo &#8599;</text></svg>\n')


def main():
    cfg_path, out = sys.argv[1], sys.argv[2]
    root = os.path.dirname(os.path.abspath(cfg_path))
    cfg = json.load(open(cfg_path, encoding="utf-8"))
    owner = cfg["owner"]
    token = os.environ.get("GITHUB_TOKEN", "")
    os.makedirs(out, exist_ok=True)
    for p in cfg["projects"]:
        live = live_data(owner, p["repo"], token) if token or os.environ.get("FETCH_LIVE") else None
        for name, t in THEMES.items():
            with open(os.path.join(out, f"{p['repo']}-{name}.svg"), "w", encoding="utf-8") as f:
                f.write(card(p, owner, live, root, t))
        print(f"  - {p['repo']}: {'live' if live else 'static'}")
    for name, t in THEMES.items():
        with open(os.path.join(out, f"header-{name}.svg"), "w", encoding="utf-8") as f:
            f.write(header(t, len(cfg["projects"])))


if __name__ == "__main__":
    main()
