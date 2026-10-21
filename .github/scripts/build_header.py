#!/usr/bin/env python3
"""Build the static header and Cyberline banner SVGs.

The typed line is SMIL, which GitHub can play inside an <img>.
Run this again if the phrases change. Stats cards are a different script.
"""

from __future__ import annotations

import html
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "assets"

PHRASES = [
    "Security engineer in a SOC",
    "Splunk, SPL, indexes, and alerting",
    "Kafka-based log pipelines",
    "Founder of Cyberline",
    "Home lab on Kubernetes and Tailscale",
    "A self-hosted Project Zomboid server",
]

# JetBrains Mono at 20px is 12px per glyph. textLength locks that width
# so the caret stays aligned when a viewer's mono font differs.
CHAR_W = 12
TYPE_MS = 46
HOLD_MS = 1600
DELETE_MS = 26
GAP_MS = 420

SANS = "ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Helvetica, Arial, 'DejaVu Sans', sans-serif"
MONO = "'JetBrains Mono', 'Cascadia Mono', ui-monospace, 'SFMono-Regular', Menlo, Consolas, 'DejaVu Sans Mono', monospace"

THEMES = {
    "light": {
        "header": "header-light.svg",
        "cta": "cyberline-light.svg",
        "card": "#f3faf8",
        "stroke": "#d2e6e2",
        "ink": "#14212b",
        "muted": "#5c6e78",
        "accent": "#0f766e",
        "copper": "#c45c26",
        "pill": "#c45c26",
        "pill_ink": "#ffffff",
        "cta_card": "#f7fbfa",
        "cta_stroke": "#cfe3de",
    },
    "dark": {
        "header": "header-dark.svg",
        "cta": "cyberline-dark.svg",
        "card": "#101a1c",
        "stroke": "#1d3d3a",
        "ink": "#eef4f6",
        "muted": "#9aafb8",
        "accent": "#7dcec6",
        "copper": "#e2a078",
        "pill": "#e2a078",
        "pill_ink": "#1c120c",
        "cta_card": "#10211f",
        "cta_stroke": "#1e4f4a",
    },
}


def _dedupe(points: list[tuple[int, float]], total: int) -> list[tuple[int, float]]:
    ordered: list[tuple[int, float]] = []
    for ms, value in points:
        ms = max(0, min(total, int(ms)))
        if ordered and ms < ordered[-1][0]:
            continue
        if ordered and ms == ordered[-1][0]:
            ordered[-1] = (ms, value)
        else:
            ordered.append((ms, value))
    if not ordered or ordered[0][0] != 0:
        ordered.insert(0, (0, ordered[0][1] if ordered else 0))
    if ordered[-1][0] != total:
        ordered.append((total, ordered[-1][1]))
    return ordered


def _anim(points: list[tuple[int, float]], total: int) -> str:
    points = _dedupe(points, total)
    values = ";".join(str(int(value)) if float(value).is_integer() else f"{value:.2f}" for _, value in points)
    times = [ms / total for ms, _ in points]
    times[0] = 0.0
    times[-1] = 1.0
    for earlier, later in zip(times, times[1:]):
        if later <= earlier:
            raise RuntimeError("animation timeline is not strictly increasing")
    key_times = ";".join(f"{stamp:.6f}" for stamp in times)
    dur = f"{total / 1000:.3f}s"
    return (
        f'values="{values}" keyTimes="{key_times}" dur="{dur}" '
        'repeatCount="indefinite" calcMode="discrete"'
    )


def _timeline() -> tuple[int, list[tuple[int, float]], list[list[tuple[int, float]]]]:
    caret: list[tuple[int, float]] = [(0, 0)]
    clips: list[list[tuple[int, float]]] = [[(0, 0)] for _ in PHRASES]
    clock = 0
    for index, phrase in enumerate(PHRASES):
        width_steps = range(1, len(phrase) + 1)
        for step in width_steps:
            clock += TYPE_MS
            width = step * CHAR_W
            caret.append((clock, width))
            clips[index].append((clock, width))
        clock += HOLD_MS
        full = len(phrase) * CHAR_W
        caret.append((clock, full))
        clips[index].append((clock, full))
        for step in range(len(phrase) - 1, -1, -1):
            clock += DELETE_MS
            width = step * CHAR_W
            caret.append((clock, width))
            clips[index].append((clock, width))
        clock += GAP_MS
        caret.append((clock, 0))
        clips[index].append((clock, 0))
    for clip in clips:
        clip.append((clock, 0))
    return clock, caret, clips


def _header(theme: dict[str, str], total: int, caret: list[tuple[int, float]], clips: list[list[tuple[int, float]]]) -> str:
    text_x = 64
    baseline = 186
    caret_anim = _anim([(ms, text_x + width) for ms, width in caret], total)
    phrase_svg: list[str] = []
    for index, phrase in enumerate(PHRASES):
        full = len(phrase) * CHAR_W
        phrase_svg.append(
            f"""    <clipPath id="clip{index}">
      <rect x="{text_x}" y="{baseline - 22}" height="30" width="0">
        <animate attributeName="width" {_anim(clips[index], total)} />
      </rect>
    </clipPath>
    <g clip-path="url(#clip{index})">
      <text x="{text_x}" y="{baseline}" fill="{theme["accent"]}" font-family="{MONO}" font-size="20" textLength="{full}" lengthAdjust="spacing">{html.escape(phrase)}</text>
    </g>"""
        )
    phrases = "\n".join(phrase_svg)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="900" height="220" viewBox="0 0 900 220" role="img" aria-labelledby="title desc">
  <title id="title">Daan Derksen</title>
  <desc id="desc">Security engineer in the Netherlands. The line under the name types through his work, Cyberline, home lab, and Project Zomboid server.</desc>
  <rect x="0.5" y="0.5" width="899" height="219" rx="18" fill="{theme["card"]}" stroke="{theme["stroke"]}"/>
  <circle cx="40" cy="42" r="4" fill="{theme["accent"]}"/>
  <text x="54" y="47" fill="{theme["accent"]}" font-family="{SANS}" font-size="13" font-weight="700" letter-spacing="0.18em">NETHERLANDS</text>
  <text x="36" y="104" fill="{theme["ink"]}" font-family="{SANS}" font-size="48" font-weight="700">Daan Derksen</text>
  <rect x="38" y="120" width="52" height="3" rx="1.5" fill="{theme["copper"]}"/>
  <text x="36" y="152" fill="{theme["muted"]}" font-family="{SANS}" font-size="18">Security engineer</text>
  <text x="862" y="152" fill="{theme["muted"]}" font-family="{SANS}" font-size="15" text-anchor="end">SOC · Splunk · Kafka</text>
  <text x="36" y="{baseline}" fill="{theme["copper"]}" font-family="{MONO}" font-size="20">&gt;</text>
{phrases}
  <rect x="{text_x}" y="{baseline - 16}" width="2" height="18" rx="1" fill="{theme["copper"]}">
    <animate attributeName="x" {caret_anim} />
    <animate attributeName="opacity" values="1;1;0;0" keyTimes="0;0.45;0.5;1" dur="1.05s" repeatCount="indefinite" calcMode="discrete" />
  </rect>
</svg>
"""


def _cta(theme: dict[str, str]) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="900" height="128" viewBox="0 0 900 128" role="img" aria-labelledby="title desc">
  <title id="title">Cyberline</title>
  <desc id="desc">Security quick scans, NIS2 readiness, and managed hosting. Visit cyberline.nl.</desc>
  <defs>
    <clipPath id="cta-clip">
      <rect width="900" height="128" rx="18"/>
    </clipPath>
  </defs>
  <g clip-path="url(#cta-clip)">
    <rect width="900" height="128" fill="{theme["cta_card"]}"/>
    <rect width="8" height="128" fill="{theme["accent"]}"/>
    <text x="36" y="40" fill="{theme["accent"]}" font-family="{SANS}" font-size="13" font-weight="700" letter-spacing="0.16em">CYBERLINE</text>
    <text x="36" y="72" fill="{theme["ink"]}" font-family="{SANS}" font-size="22" font-weight="700">Security quick scans</text>
    <text x="36" y="98" fill="{theme["muted"]}" font-family="{SANS}" font-size="16">NIS2 readiness and managed hosting</text>
    <rect x="688" y="44" width="180" height="40" rx="20" fill="{theme["pill"]}"/>
    <text x="778" y="69" fill="{theme["pill_ink"]}" font-family="{SANS}" font-size="14" font-weight="700" text-anchor="middle">Visit cyberline.nl</text>
  </g>
  <rect x="0.5" y="0.5" width="899" height="127" rx="18" fill="none" stroke="{theme["cta_stroke"]}"/>
</svg>
"""


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    total, caret, clips = _timeline()
    for theme in THEMES.values():
        (ASSETS / theme["header"]).write_text(_header(theme, total, caret, clips), encoding="utf-8")
        (ASSETS / theme["cta"]).write_text(_cta(theme), encoding="utf-8")
        print(f"wrote {theme['header']} and {theme['cta']}")


if __name__ == "__main__":
    main()
