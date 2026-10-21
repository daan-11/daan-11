#!/usr/bin/env python3
"""Render public GitHub stats cards and refresh the README alt text.

Numbers come from the public contribution calendar and the public user API.
Forks are skipped for languages, matching the usual public language card.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
import urllib.request
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
USER = "daan-11"
README = ROOT / "README.md"
PROFILE = ROOT / "profile"
UA = "daan-11-profile-readme"

SANS = "ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Helvetica, Arial, 'DejaVu Sans', sans-serif"
MONO = "'JetBrains Mono', 'Cascadia Mono', ui-monospace, 'SFMono-Regular', Menlo, Consolas, 'DejaVu Sans Mono', monospace"

LANG_COLORS = {
    "Python": "#3572A5",
    "TypeScript": "#3178c6",
    "JavaScript": "#f1e05a",
    "Go": "#00ADD8",
    "Shell": "#89e051",
    "Java": "#b07219",
    "HTML": "#e34c26",
    "CSS": "#563d7c",
    "Rust": "#dea584",
    "C": "#555555",
    "C#": "#178600",
    "Ruby": "#701516",
    "PHP": "#4F5D95",
    "HCL": "#844FBA",
    "Dockerfile": "#384d54",
}

THEMES = {
    "light": {
        "file": "dashboard-light.svg",
        "card": "#ffffff",
        "stroke": "#e1ebe8",
        "ink": "#14212b",
        "muted": "#5c6e78",
        "accent": "#0f766e",
        "track": "#e7f0ee",
        "panel": "#f7fbfa",
    },
    "dark": {
        "file": "dashboard-dark.svg",
        "card": "#151c22",
        "stroke": "#24303a",
        "ink": "#eef4f6",
        "muted": "#9aafb8",
        "accent": "#7dcec6",
        "track": "#243038",
        "panel": "#121a1f",
    },
}


def _request(url: str) -> tuple[bytes, str]:
    headers = {
        "User-Agent": UA,
        "Accept": "application/vnd.github+json",
    }
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        body = response.read()
        link = response.headers.get("Link", "")
    return body, link


def _json(url: str):
    body, link = _request(url)
    return json.loads(body.decode("utf-8")), link


def _next_link(link: str) -> str | None:
    for part in link.split(","):
        if 'rel="next"' in part:
            match = re.search(r"<([^>]+)>", part)
            if match:
                return match.group(1)
    return None


def fetch_contributions(user: str) -> tuple[dict[str, int], int]:
    body, _ = _request(f"https://github.com/users/{user}/contributions")
    page = body.decode("utf-8", "replace")
    cells: dict[str, dict[str, int | str | None]] = {}
    for match in re.finditer(
        r'data-date="(\d{4}-\d{2}-\d{2})"[^>]*id="(contribution-day-component-\d+-\d+)"[^>]*data-level="(\d+)"',
        page,
    ):
        cells[match.group(2)] = {"date": match.group(1), "count": None}
    if len(cells) < 300:
        raise RuntimeError(f"contribution calendar parsed {len(cells)} days, expected a full year")
    for match in re.finditer(
        r'<tool-tip[^>]*for="(contribution-day-component-\d+-\d+)"[^>]*>(.*?)</tool-tip>',
        page,
    ):
        cell = cells.get(match.group(1))
        if cell is None:
            continue
        text = match.group(2)
        if text.startswith("No contribution"):
            cell["count"] = 0
            continue
        count = re.search(r"(\d[\d,]*)\s+contribution", text)
        if not count:
            raise RuntimeError(f"could not read contribution tooltip: {text}")
        cell["count"] = int(count.group(1).replace(",", ""))
    missing = [cell["date"] for cell in cells.values() if cell["count"] is None]
    if missing:
        raise RuntimeError(f"missing contribution counts for {len(missing)} days")
    by_day = {str(cell["date"]): int(cell["count"]) for cell in cells.values()}
    heading = re.search(r"(\d[\d,]*)\s+contributions\s+in the last year", page)
    if not heading:
        raise RuntimeError("could not find the public contribution total")
    total = int(heading.group(1).replace(",", ""))
    counted = sum(by_day.values())
    if counted != total:
        raise RuntimeError(f"calendar sum {counted} does not match GitHub total {total}")
    return by_day, total


def streaks(by_day: dict[str, int]) -> tuple[int, int]:
    start = date.fromisoformat(min(by_day))
    end = date.fromisoformat(max(by_day))
    longest = 0
    current_run = 0
    day = start
    while day <= end:
        if by_day.get(day.isoformat(), 0) > 0:
            current_run += 1
            longest = max(longest, current_run)
        else:
            current_run = 0
        day += timedelta(days=1)

    # Same rule as github-readme-streak-stats: if today is empty, count back
    # from yesterday so a quiet morning does not wipe the streak.
    cursor = end if by_day.get(end.isoformat(), 0) > 0 else end - timedelta(days=1)
    current = 0
    while cursor >= start and by_day.get(cursor.isoformat(), 0) > 0:
        current += 1
        cursor -= timedelta(days=1)
    return current, longest


def fetch_public_repos(user: str) -> tuple[int, list[tuple[str, int]]]:
    profile, _ = _json(f"https://api.github.com/users/{user}")
    public_repos = int(profile["public_repos"])
    languages: Counter[str] = Counter()
    url: str | None = f"https://api.github.com/users/{user}/repos?per_page=100&type=owner"
    pages = 0
    while url and pages < 10:
        repos, link = _json(url)
        pages += 1
        for repo in repos:
            if repo.get("fork") or repo.get("private"):
                continue
            lang_body, _ = _json(repo["languages_url"])
            for name, count in lang_body.items():
                languages[name] += int(count)
        url = _next_link(link)
    ranked = languages.most_common(5)
    return public_repos, ranked


def _percents(ranked: list[tuple[str, int]]) -> list[tuple[str, int]]:
    total = sum(count for _, count in ranked)
    if total <= 0:
        return []
    raw = [(name, count * 100 / total) for name, count in ranked]
    floors = [int(value) for _, value in raw]
    remainder = 100 - sum(floors)
    order = sorted(range(len(raw)), key=lambda index: raw[index][1] - floors[index], reverse=True)
    for index in order[:remainder]:
        floors[index] += 1
    return [(raw[index][0], floors[index]) for index in range(len(raw))]


def _days(count: int) -> str:
    return "1 day" if count == 1 else f"{count} days"


def describe(total: int, current: int, longest: int, public_repos: int, languages: list[tuple[str, int]]) -> str:
    sentence = (
        f"{total} contributions in the last year. "
        f"Current streak: {_days(current)}. "
        f"Longest streak: {_days(longest)}. "
        f"Public repositories: {public_repos}."
    )
    if languages:
        listed = ", ".join(f"{name} {percent}%" for name, percent in languages)
        sentence += f" Top languages: {listed}."
    else:
        sentence += " No detected language on public repositories yet."
    return sentence


def _svg(
    theme: dict[str, str],
    total: int,
    current: int,
    longest: int,
    public_repos: int,
    languages: list[tuple[str, int]],
) -> str:
    stats = [
        ("CONTRIBUTIONS", str(total), "last year"),
        ("CURRENT STREAK", str(current), "day" if current == 1 else "days"),
        ("LONGEST STREAK", str(longest), "day" if longest == 1 else "days"),
        ("PUBLIC REPOS", str(public_repos), "on GitHub"),
    ]
    gap = 16
    card_w = 213
    card_h = 122
    cards = []
    for index, (label, value, hint) in enumerate(stats):
        x = index * (card_w + gap)
        cards.append(
            f"""    <g transform="translate({x} 0)">
      <rect width="{card_w}" height="{card_h}" rx="16" fill="{theme["card"]}" stroke="{theme["stroke"]}"/>
      <text x="18" y="32" fill="{theme["accent"]}" font-family="{SANS}" font-size="11" font-weight="700" letter-spacing="0.08em">{label}</text>
      <text x="18" y="78" fill="{theme["ink"]}" font-family="{MONO}" font-size="36" font-weight="700">{html.escape(value)}</text>
      <text x="18" y="102" fill="{theme["muted"]}" font-family="{SANS}" font-size="13">{html.escape(hint)}</text>
    </g>"""
        )
    panel_y = card_h + gap
    if languages:
        panel_h = 48 + len(languages) * 28
    else:
        panel_h = 78
    height = panel_y + panel_h
    lang_rows = []
    if languages:
        lang_rows.append(
            f'<text x="20" y="{panel_y + 30}" fill="{theme["accent"]}" font-family="{SANS}" font-size="11" font-weight="700" letter-spacing="0.08em">TOP LANGUAGES</text>'
        )
        lang_rows.append(
            f'<text x="880" y="{panel_y + 30}" fill="{theme["muted"]}" font-family="{SANS}" font-size="12" text-anchor="end">public repositories, forks excluded</text>'
        )
        for index, (name, percent) in enumerate(languages):
            y = panel_y + 48 + index * 28
            bar_w = max(4, int(520 * percent / 100))
            color = LANG_COLORS.get(name, theme["accent"])
            lang_rows.append(
                f'<text x="20" y="{y + 14}" fill="{theme["ink"]}" font-family="{SANS}" font-size="14">{html.escape(name)}</text>'
            )
            lang_rows.append(
                f'<rect x="168" y="{y + 4}" width="520" height="10" rx="5" fill="{theme["track"]}"/>'
            )
            lang_rows.append(
                f'<rect x="168" y="{y + 4}" width="{bar_w}" height="10" rx="5" fill="{color}"/>'
            )
            lang_rows.append(
                f'<text x="704" y="{y + 14}" fill="{theme["muted"]}" font-family="{MONO}" font-size="13">{percent}%</text>'
            )
    else:
        lang_rows.append(
            f'<text x="20" y="{panel_y + 32}" fill="{theme["accent"]}" font-family="{SANS}" font-size="11" font-weight="700" letter-spacing="0.08em">TOP LANGUAGES</text>'
        )
        lang_rows.append(
            f'<text x="20" y="{panel_y + 56}" fill="{theme["muted"]}" font-family="{SANS}" font-size="15">No detected language on public repositories yet.</text>'
        )
    rows = "\n    ".join(lang_rows)
    card_markup = "\n".join(cards)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="900" height="{height}" viewBox="0 0 900 {height}" role="img" aria-labelledby="title desc">
  <title id="title">GitHub stats for {USER}</title>
  <desc id="desc">{html.escape(describe(total, current, longest, public_repos, languages))}</desc>
{card_markup}
  <rect x="0" y="{panel_y}" width="900" height="{panel_h}" rx="16" fill="{theme["panel"]}" stroke="{theme["stroke"]}"/>
    {rows}
</svg>
"""


def update_readme(sentence: str) -> None:
    text = README.read_text(encoding="utf-8")
    pattern = re.compile(r'(<img\b[^>]*\bsrc="\./profile/dashboard-light\.svg"[^>]*)>')

    def replace(match: re.Match[str]) -> str:
        tag = match.group(1)
        safe = sentence.replace('"', "'")
        if 'alt="' in tag:
            tag = re.sub(r'alt="[^"]*"', f'alt="{safe}"', tag, count=1)
        else:
            tag += f' alt="{safe}"'
        return tag + ">"

    updated, count = pattern.subn(replace, text, count=1)
    if count != 1:
        raise RuntimeError("README is missing the dashboard image")
    block = re.compile(r"<!-- stats:start -->.*?<!-- stats:end -->", re.DOTALL)
    caption = (
        "<!-- stats:start -->\n"
        f'<p align="center"><sub>{html.escape(sentence)}</sub></p>\n'
        "<!-- stats:end -->"
    )
    updated, blocks = block.subn(caption, updated, count=1)
    if blocks != 1:
        raise RuntimeError("README is missing the stats caption markers")
    if updated != text:
        README.write_text(updated, encoding="utf-8")


def render(write: bool) -> str:
    by_day, total = fetch_contributions(USER)
    current, longest = streaks(by_day)
    public_repos, ranked = fetch_public_repos(USER)
    languages = _percents(ranked)
    sentence = describe(total, current, longest, public_repos, languages)
    if write:
        PROFILE.mkdir(parents=True, exist_ok=True)
        for theme in THEMES.values():
            svg = _svg(theme, total, current, longest, public_repos, languages)
            (PROFILE / theme["file"]).write_text(svg, encoding="utf-8")
        update_readme(sentence)
    return sentence


def _self_test() -> None:
    by_day = {
        "2026-10-17": 0,
        "2026-10-18": 2,
        "2026-10-19": 4,
        "2026-10-20": 1,
        "2026-10-21": 0,
    }
    current, longest = streaks(by_day)
    if (current, longest) != (3, 3):
        raise SystemExit(f"streak self-test failed: {(current, longest)}")
    empty_today = {
        "2026-10-18": 0,
        "2026-10-19": 0,
        "2026-10-20": 0,
        "2026-10-21": 0,
    }
    if streaks(empty_today) != (0, 0):
        raise SystemExit("empty streak self-test failed")
    percents = _percents([("Go", 2), ("Python", 1)])
    if sorted(percents) != [("Go", 67), ("Python", 33)]:
        raise SystemExit(f"percent self-test failed: {percents}")
    print("self-test ok")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        _self_test()
        return
    sentence = render(write=not args.dry_run)
    print(sentence)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001 - surface a single actionable error in Actions
        print(f"render_dashboard failed: {exc}", file=sys.stderr)
        sys.exit(1)
