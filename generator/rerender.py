"""
Re-render the site from a cached concepts.json — no API calls.

Use this when you only want to apply template/CSS changes to an already-generated
exhibition. Reads content/<month>/concepts.json, then runs the same rendering
pipeline as run_monthly.py but skips theme/artworks/poster/image generation.

Usage:
    python -m generator.rerender 2026-05
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

from . import run_monthly as rm


def main(month_key: str) -> int:
    content_dir = rm.CONTENT / month_key
    concepts_path = content_dir / "concepts.json"
    if not concepts_path.exists():
        print(f"❌ {concepts_path} not found")
        return 1

    data = json.loads(concepts_path.read_text(encoding="utf-8"))
    theme = rm.Theme(**data["theme"])
    artworks = [rm.Artwork(**a) for a in data["artworks"]]
    # Fill in image_filenames (poster.png + 01..24.png) based on what's on disk
    images_dir = content_dir / "images"
    for art in artworks:
        # Strip artist for the rerender — we no longer display fake author names
        art.artist = ""
        # Drop any stale MindAR target filename — we don't use MindAR anymore
        art.target_filename = ""
        # Image filename was set during generation; verify it exists
        if not art.image_filename:
            art.image_filename = f"{art.id:02d}.png"

    year_n = int(month_key.split("-")[0])
    month_n = int(month_key.split("-")[1])
    exhibition = rm.Exhibition(
        month_key=month_key,
        month_lt=rm.MONTHS_LT[month_n],
        year=year_n,
        theme=theme,
        artworks=artworks,
        poster_prompt=data.get("poster_prompt", ""),
        social_caption_lt=data.get("social_caption_lt", ""),
    )
    exhibition.poster_filename = "poster.png"

    rm.render_site(exhibition, content_dir)
    print(f"✅ Re-rendered site from {concepts_path}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python -m generator.rerender YYYY-MM")
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
