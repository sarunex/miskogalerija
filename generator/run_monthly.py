"""
Monthly exhibition generator for miskogalerija.lt

Run via GitHub Actions on the 1st of each month, or manually with:
    python -m generator.run_monthly

Pipeline:
  1. Generate theme (Claude)
  2. Generate 24 artwork concepts + statements (Claude)
  3. Generate poster prompt (Claude)
  4. Generate 25 images in parallel (OpenAI gpt-image-1)
  5. Compile MindAR .mind tracking files (one per artwork, used as marker)
  6. Render static site (Jinja2): index.html + 24 qr/N.html pages
  7. Write manifest.json + archive previous exhibition
"""
from __future__ import annotations

import base64
import concurrent.futures
import json
import logging
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import anthropic
from jinja2 import Environment, FileSystemLoader, select_autoescape
from openai import OpenAI

# ─────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
PROMPTS = Path(__file__).resolve().parent / "prompts"
TEMPLATES = ROOT / "site" / "_templates"
SITE = ROOT / "site"
CONTENT = ROOT / "content"

NUM_ARTWORKS = 24
CLAUDE_MODEL = "claude-opus-4-5"  # adjust per current docs
IMAGE_MODEL = "gpt-image-1"
IMAGE_SIZE = "1024x1024"

MONTHS_LT = {
    1: "sausio",  2: "vasario", 3: "kovo",     4: "balandžio",
    5: "gegužės", 6: "birželio",7: "liepos",   8: "rugpjūčio",
    9: "rugsėjo", 10: "spalio", 11: "lapkričio",12: "gruodžio",
}
SEASONS_LT = {
    12: "žiemos", 1: "žiemos", 2: "žiemos",
    3: "pavasario", 4: "pavasario", 5: "pavasario",
    6: "vasaros", 7: "vasaros", 8: "vasaros",
    9: "rudens", 10: "rudens", 11: "rudens",
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
)
log = logging.getLogger("miskogalerija")


# ─────────────────────────────────────────────────────────────────────
# Data
# ─────────────────────────────────────────────────────────────────────
@dataclass
class Theme:
    title: str
    subtitle: str
    essay: str
    visual_direction: str
    palette_hint: str


@dataclass
class Artwork:
    id: int
    artist: str
    title_lt: str
    year: str
    medium_lt: str
    statement_lt: str
    image_prompt: str
    image_filename: str = ""
    target_filename: str = ""  # MindAR .mind file


@dataclass
class Exhibition:
    month_key: str               # "2026-05"
    month_lt: str                # "gegužės"
    year: int
    theme: Theme
    artworks: list[Artwork]
    poster_prompt: str
    poster_filename: str = ""
    social_caption_lt: str = ""
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ─────────────────────────────────────────────────────────────────────
# Claude calls
# ─────────────────────────────────────────────────────────────────────
def _claude() -> anthropic.Anthropic:
    return anthropic.Anthropic()


def _ask_json(prompt: str, max_tokens: int = 8192) -> dict | list:
    """Send a prompt to Claude expecting strict JSON back. Retries once on parse failure."""
    client = _claude()
    last_err = None
    for attempt in (1, 2):
        msg = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        text = msg.content[0].text.strip()
        # Strip accidental fences
        if text.startswith("```"):
            text = text.split("```", 2)[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip("` \n")
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            last_err = e
            log.warning("JSON parse failed on attempt %d: %s", attempt, e)
            prompt += "\n\nSVARBU: tavo ankstesnis atsakymas nebuvo teisingas JSON. Atsakyk TIK teisingu JSON, be markdown."
    raise RuntimeError(f"Claude failed to return valid JSON after 2 attempts: {last_err}")


def generate_theme(month_lt: str, season_lt: str, year: int, theme_hint: str) -> Theme:
    log.info("Generating theme for %s %d (%s sezonas)", month_lt, year, season_lt)
    template = (PROMPTS / "theme.txt").read_text(encoding="utf-8")
    hint_section = (
        f'Vartotojo užuomina apie temą: „{theme_hint}". Atsižvelk į ją, bet kuruok pats.'
        if theme_hint else
        'Tema renkama tavo nuožiūra.'
    )
    prompt = template.format(
        month_lt=month_lt, year=year, season_lt=season_lt,
        theme_hint_section=hint_section,
    )
    data = _ask_json(prompt, max_tokens=2000)
    theme = Theme(**data)
    log.info("Theme: %s — %s", theme.title, theme.subtitle)
    return theme


def generate_artworks(theme: Theme, year: int) -> list[Artwork]:
    log.info("Generating %d artwork concepts", NUM_ARTWORKS)
    template = (PROMPTS / "artworks.txt").read_text(encoding="utf-8")
    prompt = template.format(
        title=theme.title, subtitle=theme.subtitle,
        visual_direction=theme.visual_direction,
        palette_hint=theme.palette_hint, year=year,
    )
    data = _ask_json(prompt, max_tokens=16000)
    if not isinstance(data, list) or len(data) != NUM_ARTWORKS:
        raise RuntimeError(f"Expected list of {NUM_ARTWORKS}, got {type(data).__name__} of len {len(data) if isinstance(data, list) else '?'}")
    artworks = [Artwork(**a) for a in data]
    log.info('First artwork: #%d %s — „%s"', artworks[0].id, artworks[0].artist, artworks[0].title_lt)
    return artworks


def generate_poster_meta(theme: Theme) -> tuple[str, str]:
    log.info("Generating poster prompt + social caption")
    template = (PROMPTS / "poster.txt").read_text(encoding="utf-8")
    prompt = template.format(
        title=theme.title, subtitle=theme.subtitle,
        visual_direction=theme.visual_direction, palette_hint=theme.palette_hint,
    )
    data = _ask_json(prompt, max_tokens=1500)
    return data["image_prompt"], data["social_caption_lt"]


# ─────────────────────────────────────────────────────────────────────
# Image generation
# ─────────────────────────────────────────────────────────────────────
def generate_image(prompt: str, out_path: Path, openai_client: OpenAI) -> None:
    """Generate one image with gpt-image-1 and save as PNG."""
    log.info("→ %s (%d chars prompt)", out_path.name, len(prompt))
    resp = openai_client.images.generate(
        model=IMAGE_MODEL,
        prompt=prompt,
        size=IMAGE_SIZE,
        n=1,
    )
    b64 = resp.data[0].b64_json
    out_path.write_bytes(base64.b64decode(b64))


def generate_all_images(exhibition: Exhibition, images_dir: Path) -> None:
    images_dir.mkdir(parents=True, exist_ok=True)
    client = OpenAI()

    tasks: list[tuple[str, Path]] = []
    # Poster
    poster_path = images_dir / "poster.png"
    tasks.append((exhibition.poster_prompt, poster_path))
    exhibition.poster_filename = poster_path.name
    # Artworks
    for art in exhibition.artworks:
        path = images_dir / f"{art.id:02d}.png"
        art.image_filename = path.name
        tasks.append((art.image_prompt, path))

    # gpt-image-1 doesn't love 25 concurrent requests. 4 at a time is safe.
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        futures = [ex.submit(generate_image, p, path, client) for p, path in tasks]
        for f in concurrent.futures.as_completed(futures):
            f.result()  # raise if any failed

    log.info("All %d images generated", len(tasks))


# ─────────────────────────────────────────────────────────────────────
# MindAR target compilation
# ─────────────────────────────────────────────────────────────────────
def compile_mindar_targets(images_dir: Path, targets_dir: Path, artworks: list[Artwork]) -> None:
    """
    Compile a .mind tracking file for each artwork.

    Strategy: each artwork's own image is its AR marker. When the visitor scans
    the QR at plate N, the page loads with target N's .mind file, then asks the
    user to point at the plate. We use the artwork image as marker so tracking
    is rich and unique (NOT the QR pattern, which is poor for image tracking).

    For this to work in production, the printed plate alongside the QR should
    feature a small reproduction of the artwork. Since artworks change monthly,
    the plate would need to be re-stickered monthly OR the plate features a
    fixed unique pattern (one per location) that we use as the marker instead.

    For the prototype: we compile each artwork as its own marker. Swap to a
    fixed-marker strategy by replacing the input image here with a per-plate
    unique reference image.
    """
    targets_dir.mkdir(parents=True, exist_ok=True)
    log.info("Compiling MindAR targets")

    # Try to use mind-ar-cli if installed; otherwise skip with a warning
    if not shutil.which("mind-ar-cli") and not shutil.which("npx"):
        log.warning("mind-ar-cli not found — skipping target compilation. Pages will use markerless fallback.")
        return

    for art in artworks:
        in_img = images_dir / art.image_filename
        out_mind = targets_dir / f"{art.id:02d}.mind"
        try:
            # mind-ar-cli signature: input <files> -o <output_dir>
            # Falls back to npx invocation if global isn't installed
            cmd = ["mind-ar-cli", "compile", "-i", str(in_img), "-o", str(targets_dir)]
            subprocess.run(cmd, check=True, capture_output=True, timeout=120)
            # Library writes targets.mind; rename to per-id
            generated = targets_dir / "targets.mind"
            if generated.exists():
                generated.rename(out_mind)
            art.target_filename = out_mind.name
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as e:
            log.warning("MindAR compile failed for #%d: %s — page will fallback", art.id, e)
            art.target_filename = ""


# ─────────────────────────────────────────────────────────────────────
# Site rendering
# ─────────────────────────────────────────────────────────────────────
def render_site(exhibition: Exhibition, exhibition_dir: Path) -> None:
    log.info("Rendering site")
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES)),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )

    # Base path for assets (relative to /site/, so just "/<month>/...")
    assets_base = f"/exhibitions/{exhibition.month_key}"

    # Copy this month's content into the site so it's served
    site_exhibition = SITE / "exhibitions" / exhibition.month_key
    if site_exhibition.exists():
        shutil.rmtree(site_exhibition)
    shutil.copytree(exhibition_dir, site_exhibition)

    # Index page
    index_html = env.get_template("index.html.j2").render(
        exhibition=exhibition,
        assets_base=assets_base,
    )
    (SITE / "index.html").write_text(index_html, encoding="utf-8")

    # Map page (uses /locations.json + /manifest.json at runtime)
    map_html = env.get_template("map.html.j2").render(
        exhibition=exhibition,
        assets_base=assets_base,
    )
    (SITE / "zemelapis.html").write_text(map_html, encoding="utf-8")

    # 24 per-QR pages
    qr_dir = SITE / "qr"
    qr_dir.mkdir(exist_ok=True)
    for art in exhibition.artworks:
        html = env.get_template("artwork.html.j2").render(
            exhibition=exhibition, art=art, assets_base=assets_base,
        )
        (qr_dir / f"{art.id}.html").write_text(html, encoding="utf-8")

    # Manifest (machine-readable, useful for Instagram bot etc.)
    manifest = {
        "month": exhibition.month_key,
        "generated_at": exhibition.generated_at,
        "theme": exhibition.theme.__dict__,
        "poster": f"{assets_base}/images/{exhibition.poster_filename}",
        "social_caption_lt": exhibition.social_caption_lt,
        "artworks": [
            {
                "id": a.id,
                "artist": a.artist,
                "title_lt": a.title_lt,
                "url": f"https://miskogalerija.lt/qr/{a.id}.html",
                "image": f"{assets_base}/images/{a.image_filename}",
                "target": f"{assets_base}/targets/{a.target_filename}" if a.target_filename else None,
            }
            for a in exhibition.artworks
        ],
    }
    (SITE / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("Site rendered")


# ─────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────
def main() -> int:
    now = datetime.now(timezone.utc)
    month_key = now.strftime("%Y-%m")
    month_lt = MONTHS_LT[now.month]
    season_lt = SEASONS_LT[now.month]
    year = now.year
    theme_hint = os.environ.get("THEME_HINT", "").strip()

    log.info("════════════════════════════════════════════════════════════")
    log.info("  MIŠKO GALERIJA — generating exhibition for %s", month_key)
    log.info("════════════════════════════════════════════════════════════")

    exhibition_dir = CONTENT / month_key
    images_dir = exhibition_dir / "images"
    targets_dir = exhibition_dir / "targets"

    # 1. Theme
    theme = generate_theme(month_lt, season_lt, year, theme_hint)

    # 2. Artworks
    artworks = generate_artworks(theme, year)

    # 3. Poster
    poster_prompt, social_caption = generate_poster_meta(theme)

    exhibition = Exhibition(
        month_key=month_key, month_lt=month_lt, year=year,
        theme=theme, artworks=artworks,
        poster_prompt=poster_prompt, social_caption_lt=social_caption,
    )

    # Save concepts before image generation (cheap insurance)
    exhibition_dir.mkdir(parents=True, exist_ok=True)
    (exhibition_dir / "concepts.json").write_text(
        json.dumps({
            "theme": theme.__dict__,
            "artworks": [a.__dict__ for a in artworks],
            "poster_prompt": poster_prompt,
            "social_caption_lt": social_caption,
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # 4. Images
    generate_all_images(exhibition, images_dir)

    # 5. MindAR targets
    compile_mindar_targets(images_dir, targets_dir, exhibition.artworks)

    # 6. Render site
    render_site(exhibition, exhibition_dir)

    log.info("✓ Exhibition %s ready.", month_key)
    return 0


if __name__ == "__main__":
    sys.exit(main())
