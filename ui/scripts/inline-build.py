"""Inline the Vite production assets into dist/index.html."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
INDEX = DIST / "index.html"


def main() -> int:
    html = INDEX.read_text(encoding="utf-8")

    def inline_script(match: re.Match[str]) -> str:
        attributes, source = match.groups()
        path = DIST / source.lstrip("/")
        script = path.read_text(encoding="utf-8")
        return f"<script{attributes}>{script}</script>"

    def inline_style(match: re.Match[str]) -> str:
        source = match.group(1)
        path = DIST / source.lstrip("/")
        return f"<style>{path.read_text(encoding='utf-8')}</style>"

    html = re.sub(
        r'<script([^>]*)\s+src="([^"]+)"[^>]*></script>',
        inline_script,
        html,
    )
    html = re.sub(
        r'<link[^>]+rel="stylesheet"[^>]+href="([^"]+)"[^>]*>',
        inline_style,
        html,
    )
    INDEX.write_text(html, encoding="utf-8")

    remaining = re.findall(
        r'<(?:script|link|img)\b[^>]+(?:src|href)="(?!data:|#)([^"]+)"',
        html,
        flags=re.IGNORECASE,
    )
    if remaining:
        raise RuntimeError(f"Production HTML still has external assets: {remaining}")

    for path in (DIST / "assets").glob("*"):
        path.unlink()
    assets = DIST / "assets"
    if assets.exists():
        assets.rmdir()

    print(f"Created self-contained {INDEX} ({INDEX.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
