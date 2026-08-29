#!/usr/bin/env python3
"""Validate the local Glaze Shift privacy page without third-party packages."""

from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parent
PAGE = ROOT / "index.html"
SITE_INDEX = ROOT.parent / "index.html"


class PolicyParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tags: list[tuple[str, dict[str, str]]] = []
        self.text_parts: list[str] = []
        self.h1_count = 0
        self.h2_text: list[str] = []
        self._heading: str | None = None
        self._heading_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        normalized = {key: value or "" for key, value in attrs}
        self.tags.append((tag, normalized))
        if tag == "h1":
            self.h1_count += 1
        if tag in {"h1", "h2"}:
            self._heading = tag
            self._heading_parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag == self._heading:
            if tag == "h2":
                self.h2_text.append(" ".join(self._heading_parts).strip())
            self._heading = None
            self._heading_parts = []

    def handle_data(self, data: str) -> None:
        stripped = " ".join(data.split())
        if not stripped:
            return
        self.text_parts.append(stripped)
        if self._heading is not None:
            self._heading_parts.append(stripped)


def fail(message: str) -> None:
    raise AssertionError(message)


def main() -> int:
    source = PAGE.read_text(encoding="utf-8")
    if not source.lower().startswith("<!doctype html>"):
        fail("missing HTML5 doctype")

    parser = PolicyParser()
    parser.feed(source)
    parser.close()
    text = re.sub(r"\s+", " ", " ".join(parser.text_parts)).strip()

    if parser.h1_count != 1:
        fail(f"expected one h1, found {parser.h1_count}")

    required_headings = {
        "Scope and current status",
        "Game progress and preferences",
        "SDK-free standalone, itch.io, Telegram, and Android editions",
        "Portal editions and official platform SDKs",
        "What a portal may process",
        "Advertising and purchases",
        "Retention, deletion, and choices",
        "Children's privacy",
        "Security and policy changes",
        "Contact",
    }
    missing_headings = sorted(required_headings.difference(parser.h2_text))
    if missing_headings:
        fail(f"missing headings: {missing_headings}")

    required_phrases = (
        "SDK-free itch.io edition was publicly released on August 29, 2026",
        "Other editions remain local candidates or external-platform drafts",
        "progress and preferences stay in browser or app-private storage",
        "does not send gameplay or save data to Extenup",
        "current signed Android 0.1.0 candidate contains only bundled game files",
        "requests no Internet access, advertising ID",
        "current local target uses Playgama Bridge",
        "only after both three completed levels and 180 seconds",
        "Startup ad preload, rewarded ads, banners, and advanced banners are disabled",
        "CrazyGames targets do",
        "Data Module for progress",
        "no final GameDistribution build exists",
        "current Yandex and Poki targets keep progress in browser-local storage",
        "current Playgama and Yandex local targets space level-end ad opportunities",
        "has no in-game purchases or external payment system",
        "under its own privacy policy",
        "does not add a separate Extenup analytics SDK",
        "SDK-free editions contain no advertising or purchases",
        "Game publisher: Extenup",
        "extenup@gmail.com",
    )
    for phrase in required_phrases:
        if phrase not in text:
            fail(f"missing required privacy distinction: {phrase!r}")

    forbidden_markers = (
        "TODO",
        "PLACEHOLDER",
        "we collect no data from any platform",
    )
    for marker in forbidden_markers:
        if marker.lower() in source.lower():
            fail(f"forbidden or unresolved claim: {marker!r}")

    links = [attrs.get("href", "") for tag, attrs in parser.tags if tag in {"a", "link"}]
    if "../styles.css" not in links:
        fail("shared site stylesheet is not linked")
    if "mailto:extenup@gmail.com" not in links:
        fail("privacy contact link is missing")
    if any(re.match(r"https?://", link) for link in links):
        fail("privacy page must not introduce an external web URL")

    external_loaders = [
        (tag, attrs)
        for tag, attrs in parser.tags
        if tag in {"script", "iframe", "img", "video", "audio"}
        and any(re.match(r"https?://", attrs.get(key, "")) for key in ("src", "href"))
    ]
    if external_loaders:
        fail(f"unexpected external loader: {external_loaders}")

    stylesheet = (ROOT / "../styles.css").resolve()
    if not stylesheet.is_file():
        fail("shared stylesheet does not resolve locally")

    site_source = SITE_INDEX.read_text(encoding="utf-8")
    site_parser = PolicyParser()
    site_parser.feed(site_source)
    site_parser.close()
    site_links = [
        attrs.get("href", "")
        for tag, attrs in site_parser.tags
        if tag == "a"
    ]
    if "glaze-shift/" not in site_links:
        fail("root privacy index does not link to Glaze Shift")
    site_text = re.sub(r"\s+", " ", " ".join(site_parser.text_parts)).strip()
    if "SDK-free Android game editions" not in site_text:
        fail("root privacy index does not scope its no-ads summary to SDK-free Android editions")

    print(
        f"PASS: {PAGE} ({len(source.encode('utf-8'))} bytes), "
        "root index linked, no external loaders"
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (AssertionError, OSError, UnicodeError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        sys.exit(1)
