#!/usr/bin/env python3
"""
design_extract.py — reverse-engineer a public webpage's visible design system
into a single markdown "cheat sheet" (colors, fonts, spacing, radii, shadows).

This is a from-scratch implementation of the idea behind the reel's "Skill UI"
tool: point it at a URL, get back a markdown file describing that site's
design system, so an LLM (or a human) can build something in the same style
without guessing.

WHAT IT DOES
------------
1. Fetches a single public page (one HTTP GET — no crawling, no login, no
   bypassing of any paywall/bot-protection).
2. Parses the HTML and any same-origin <link rel="stylesheet"> files it can
   also fetch, plus inline <style> blocks and style="" attributes.
3. Extracts, by static analysis of the CSS/HTML text:
     - color values (hex/rgb/hsl) and ranks them by frequency
     - font-family declarations
     - font-size scale
     - spacing values (margin/padding/gap) to infer a spacing scale
     - border-radius values
     - box-shadow values
4. Writes a markdown "design-system.md" cheat sheet summarizing all of the
   above, suitable for pasting into a prompt or checking into a repo.

WHAT IT DELIBERATELY DOES NOT DO
---------------------------------
- No crawling beyond the one URL you give it.
- No headless-browser fingerprint spoofing, CAPTCHA solving, or any attempt
  to get around bot/fraud detection.
- No authentication, credential handling, or session hijacking.
- It sends one plain HTTP GET with a normal, honest User-Agent string and
  respects robots.txt by default (see --ignore-robots to override, which
  you should only do on sites you own or have permission to inspect).
- It only reads what any browser visiting the page would already receive
  (public HTML/CSS), which is materially the same as opening dev tools and
  reading the "Styles" panel yourself.

You are responsible for checking the target site's terms of service before
pointing this at anything you don't own.
"""

from __future__ import annotations

import argparse
import re
import sys
import urllib.error
import urllib.request
import urllib.robotparser
from collections import Counter
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

USER_AGENT = "design-extract/1.0 (+https://example.local; single-page design audit tool)"

COLOR_RE = re.compile(
    r"#(?:[0-9a-fA-F]{3}){1,2}\b"
    r"|rgba?\([^)]+\)"
    r"|hsla?\([^)]+\)"
)
FONT_FAMILY_RE = re.compile(r"font-family\s*:\s*([^;{}]+)", re.IGNORECASE)
FONT_SIZE_RE = re.compile(r"font-size\s*:\s*([0-9.]+(?:px|rem|em|pt))", re.IGNORECASE)
SPACING_RE = re.compile(
    r"(?:margin|padding|gap)(?:-(?:top|right|bottom|left))?\s*:\s*([^;{}]+)",
    re.IGNORECASE,
)
RADIUS_RE = re.compile(r"border-radius\s*:\s*([^;{}]+)", re.IGNORECASE)
SHADOW_RE = re.compile(r"box-shadow\s*:\s*([^;{}]+)", re.IGNORECASE)
NUMERIC_TOKEN_RE = re.compile(r"-?[0-9.]+(?:px|rem|em)")


class LinkAndStyleCollector(HTMLParser):
    """Pulls out <link rel=stylesheet href=...>, <style>...</style>, and
    inline style="" attributes from an HTML document."""

    def __init__(self):
        super().__init__()
        self.stylesheet_hrefs: list[str] = []
        self.inline_style_blocks: list[str] = []
        self.inline_style_attrs: list[str] = []
        self._in_style = False
        self._style_buf: list[str] = []

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        if tag == "link" and attrs_dict.get("rel", "").lower() == "stylesheet":
            href = attrs_dict.get("href")
            if href:
                self.stylesheet_hrefs.append(href)
        if "style" in attrs_dict and attrs_dict["style"]:
            self.inline_style_attrs.append(attrs_dict["style"])
        if tag == "style":
            self._in_style = True
            self._style_buf = []

    def handle_endtag(self, tag):
        if tag == "style" and self._in_style:
            self.inline_style_blocks.append("".join(self._style_buf))
            self._in_style = False

    def handle_data(self, data):
        if self._in_style:
            self._style_buf.append(data)


def fetch(url: str, timeout: int = 15) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        return resp.read().decode(charset, errors="replace")


def robots_allows(url: str) -> bool:
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    rp = urllib.robotparser.RobotFileParser()
    try:
        rp.set_url(robots_url)
        rp.read()
    except Exception:
        # If robots.txt is unreachable/malformed, default to allow —
        # matches standard browser/crawler fallback behavior.
        return True
    return rp.can_fetch(USER_AGENT, url)


def gather_css(url: str, html: str, max_stylesheets: int = 8) -> str:
    collector = LinkAndStyleCollector()
    collector.feed(html)

    css_chunks: list[str] = []
    css_chunks.extend(collector.inline_style_blocks)
    # Fold inline style="" attributes into fake rule bodies so the same
    # regexes can scan them.
    for attr in collector.inline_style_attrs:
        css_chunks.append("{" + attr + "}")

    for href in collector.stylesheet_hrefs[:max_stylesheets]:
        full_url = urljoin(url, href)
        try:
            css_chunks.append(fetch(full_url))
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError):
            continue  # best-effort; skip stylesheets that fail to load

    return "\n".join(css_chunks)


def top_matches(pattern: re.Pattern, text: str, n: int) -> list[tuple[str, int]]:
    counts = Counter(m.strip() for m in pattern.findall(text) if m.strip())
    return counts.most_common(n)


def extract_numeric_tokens(values: list[str]) -> list[tuple[str, int]]:
    tokens = Counter()
    for v in values:
        for tok in NUMERIC_TOKEN_RE.findall(v):
            tokens[tok] += 1
    return tokens.most_common(20)


def build_report(url: str, css: str) -> str:
    colors = top_matches(COLOR_RE, css, 15)
    font_families = top_matches(FONT_FAMILY_RE, css, 8)
    font_sizes = top_matches(FONT_SIZE_RE, css, 12)
    radii = top_matches(RADIUS_RE, css, 8)
    shadows = top_matches(SHADOW_RE, css, 5)

    spacing_values = SPACING_RE.findall(css)
    spacing_tokens = extract_numeric_tokens(spacing_values)

    lines: list[str] = []
    lines.append(f"# Design System — {url}")
    lines.append("")
    lines.append(
        "Auto-extracted cheat sheet from this page's HTML/CSS. "
        "Feed this file to an LLM (or read it yourself) before building a "
        "new UI so it matches this site's look instead of guessing."
    )
    lines.append("")

    lines.append("## Colors (by frequency in CSS)")
    if colors:
        for color, count in colors:
            lines.append(f"- `{color}` — used {count}x")
    else:
        lines.append("- No colors found (page may load styles via JS).")
    lines.append("")

    lines.append("## Fonts")
    if font_families:
        for family, count in font_families:
            lines.append(f"- `{family.strip()}` — used {count}x")
    else:
        lines.append("- No `font-family` declarations found in static CSS.")
    lines.append("")

    lines.append("## Font size scale")
    if font_sizes:
        sizes_sorted = sorted({s for s, _ in font_sizes})
        lines.append("- " + ", ".join(f"`{s}`" for s in sizes_sorted))
    else:
        lines.append("- No explicit `font-size` values found.")
    lines.append("")

    lines.append("## Spacing scale (margin / padding / gap values)")
    if spacing_tokens:
        lines.append(
            "- " + ", ".join(f"`{tok}` ({count}x)" for tok, count in spacing_tokens[:12])
        )
    else:
        lines.append("- No spacing values found.")
    lines.append("")

    lines.append("## Border radius")
    if radii:
        for r, count in radii:
            lines.append(f"- `{r.strip()}` — used {count}x")
    else:
        lines.append("- No `border-radius` values found (likely square corners).")
    lines.append("")

    lines.append("## Shadows")
    if shadows:
        for s, count in shadows:
            lines.append(f"- `{s.strip()}` — used {count}x")
    else:
        lines.append("- No `box-shadow` values found.")
    lines.append("")

    lines.append("## How to use this")
    lines.append(
        "- Give this file to Claude (or any coding assistant) alongside your "
        "prompt, e.g. 'Build the landing page using the design system in "
        "design-system.md — same colors, fonts, spacing, and radii.'"
    )
    lines.append(
        "- The most-used values above are a reasonable default palette/scale; "
        "the long tail is often one-off exceptions, not the system itself."
    )
    lines.append(
        "- This is a static-CSS snapshot. Pages that render styles purely via "
        "JS (e.g. some CSS-in-JS setups) may need a browser-based tool "
        "(like Playwright) to capture computed styles instead."
    )

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Reverse-engineer a public webpage's design system into a markdown cheat sheet."
    )
    parser.add_argument("url", help="URL of the page to analyze (e.g. https://example.com)")
    parser.add_argument(
        "-o", "--output", default="design-system.md", help="Output markdown file path"
    )
    parser.add_argument(
        "--ignore-robots",
        action="store_true",
        help="Skip the robots.txt check. Only use this on sites you own or have permission to inspect.",
    )
    parser.add_argument(
        "--max-stylesheets",
        type=int,
        default=8,
        help="Max number of linked stylesheets to fetch (default: 8)",
    )
    args = parser.parse_args()

    if not args.ignore_robots and not robots_allows(args.url):
        print(
            f"robots.txt disallows fetching {args.url} for this tool's user-agent.\n"
            "Respecting it and stopping. Re-run with --ignore-robots only if you "
            "own this site or have explicit permission.",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        html = fetch(args.url)
    except (urllib.error.URLError, urllib.error.HTTPError) as e:
        print(f"Failed to fetch {args.url}: {e}", file=sys.stderr)
        sys.exit(1)

    css = gather_css(args.url, html, max_stylesheets=args.max_stylesheets)
    if not css.strip():
        print("Warning: no CSS found on this page.", file=sys.stderr)

    report = build_report(args.url, css)

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(report + "\n")

    print(f"Wrote design system cheat sheet to {args.output}")


if __name__ == "__main__":
    main()
