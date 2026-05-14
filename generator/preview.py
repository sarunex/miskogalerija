"""
Local preview generator — renders the site with placeholder Lithuanian content
and pretty colored gradient images, so you can preview the layout/UX immediately
without spending API credit.

Usage:
    python -m generator.preview
    cd site && python -m http.server 8000
"""
from __future__ import annotations
import json
import random
import shutil
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from generator.run_monthly import (
    Theme, Artwork, Exhibition,
    SITE, CONTENT, MONTHS_LT, SEASONS_LT,
    render_site,
)

random.seed(42)

# Fixture content (good enough to feel real)
FIXTURE_THEME = Theme(
    title="Miško Sapnai",
    subtitle="Dvidešimt keturios pavasario nakties vizijos, surinktos iš medžių pasąmonės.",
    essay=(
        "Šio mėnesio paroda gimsta iš paprasto klausimo: jeigu medžiai sapnuotų, "
        "ką jie matytų? Kuratoriaus pasirinkimas — ne ekologinė tema ir ne "
        "tradicinė miško mitologija, bet tarpinė erdvė tarp sąmonės ir "
        "neorganinio buvimo, kurioje pavasario šaltis dar neatlęidžia, o "
        "saulės šviesa jau pasiekia paklotę.\n\n"
        "Dvidešimt keturi menininkai — vieni išgalvoti, kiti realistiškai "
        "tikėtini — pateikia savo atsakymus. Vieni renkasi figūratyvinį kelią "
        "ir piešia pamatuotus fotografinius kadrus, kiti gilinasi į abstrakciją, "
        "kur formos virsta pajutimais. Kviečiame nepraeiti pro šalį. "
        "Sustokite. Pažiūrėkite per kameros lęšį."
    ),
    visual_direction=(
        "Muted earth-tone palette dominated by moss green, birch white, and "
        "pre-dawn blue. Mix of digital painting, photographic collage, and "
        "abstract gestures. Atmospheric, slightly melancholic, gallery-grade."
    ),
    palette_hint="moss green, birch white, pre-dawn blue, rust",
)

LT_FIRST_NAMES = ["Aušra", "Tomas", "Eglė", "Kęstutis", "Rūta", "Mantas", "Indrė", "Vytautas", "Žygimantas", "Dovilė"]
LT_LAST_NAMES = ["Petraitis", "Kazlauskas", "Bružaitė", "Mickevičius", "Raulinaitis", "Dambrauskaitė", "Gajauskas", "Žukauskas", "Vilkaitė", "Burokas"]
INTL_NAMES = ["Mira Jansson", "Henrik Vogel", "Aino Saarinen", "Joost van der Berg", "Lena Kowalski", "Tomáš Hradil"]

TITLES = [
    "Pirmas šaltis", "Žiemos paskutinis šnabždesys", "Beržo balso forma",
    "Naktis tarp šakų", "Sapno paklotė", "Drebulių chronika",
    "Atminties medis", "Poryčio švytėjimas", "Šaknų kalba",
    "Vandens stiklas", "Tylos archeologija", "Pavasario kontūras",
    "Spygliuotos pieva", "Septintas rytas", "Po žemei",
    "Kvėpavimas tarpukaryje", "Pelkės akys", "Dovana iš ąžuolo",
    "Šerkšno raidynas", "Dūmas virš laukymės", "Vienatvės topografija",
    "Mažas mažas šaltis", "Kelionės pradžia", "Galas ir ne galas",
]

MEDIA = [
    "Skaitmeninė tapyba", "Fotomontažas", "Mišri technika",
    "Generatyvinė grafika", "Kolažas ir tekstūra", "Skaitmeninė akvarelė",
    "Fotografinė rekonstrukcija", "Vektorinė kompozicija",
]

STATEMENTS = [
    "Šį kūrinį pradėjau kaip užrašą — bandymą prisiminti, kaip atrodo pirmasis kovo šaltis ant beržo žievės. Ilgai dirbau su sluoksniais; kiekvienas jų buvo paneigtas kito. Galutinė kompozicija yra ne tai, ką mačiau, bet tai, kas liko po visų atmetimų.",
    "Mano praktika sukasi apie nematomas medžiagas: garsą, kvėpavimą, lūkesčius. Šiame darbe siekiau sustabdyti vieną sekundę, kurioje miškas dar nepasijunta esąs stebimas. Ar pavyko — sprendžia žiūrovas.",
    "Norėjau sukurti vaizdą, kuris nepasiduoda greitam skaitymui. Žiūrovui reikia šiek tiek pastovėti, kad spalvos pradėtų judėti. Tai mažas testas kantrybei — ir miškui, ir mums.",
    "Ši kompozicija atsirado iš senos nuotraukos, kurią mama padarė 1987 metais. Aš jos nepamenu, bet vaizdas atrodė pažįstamas. Skaitmeninėmis priemonėmis pratęsiau tai, ko ten nebuvo.",
    "Nuolat grįžtu prie idėjos, kad medžiai turi savo vidinę architektūrą — ne biologinę, bet semiotinę. Šis darbas yra schema medžiui, kurio dar nėra. Galbūt jis ateina.",
]

def make_gradient_image(out: Path, idx: int, label: str) -> None:
    """Make a paper-textured gradient image as a placeholder artwork."""
    palette = [
        ((42, 59, 31),  (122, 58, 26)),   # moss → rust
        ((232, 226, 212),(74, 70, 57)),   # paper → ink-soft
        ((61, 79, 92), (232, 226, 212)),  # blue-grey → paper
        ((92, 76, 47), (43, 49, 31)),     # umber → dark olive
    ]
    a, b = palette[idx % len(palette)]
    img = Image.new("RGB", (1024, 1024), a)
    draw = ImageDraw.Draw(img)
    # diagonal gradient
    for y in range(1024):
        t = y / 1024
        r = int(a[0] + (b[0]-a[0])*t)
        g = int(a[1] + (b[1]-a[1])*t)
        bl = int(a[2] + (b[2]-a[2])*t)
        draw.line([(0, y), (1024, y)], fill=(r, g, bl))
    # add some painterly noise
    noise = Image.effect_noise((1024, 1024), 32).convert("L")
    img = Image.composite(img, Image.new("RGB", img.size, (0,0,0)), noise.point(lambda v: 200 if v>128 else 240))
    img = img.filter(ImageFilter.GaussianBlur(radius=3))
    # subtle index marker
    draw = ImageDraw.Draw(img)
    draw.text((40, 40), f"#{idx:02d}", fill=(255, 255, 255, 120))
    draw.text((40, 980), label[:24], fill=(255, 255, 255, 80))
    img.save(out, "PNG")


def main() -> None:
    now = datetime.now(timezone.utc)
    month_key = now.strftime("%Y-%m")
    month_lt = MONTHS_LT[now.month]

    artworks = []
    for i in range(1, 25):
        name = (
            random.choice(INTL_NAMES) if i % 5 == 0 else
            f"{random.choice(LT_FIRST_NAMES)} {random.choice(LT_LAST_NAMES)}"
        )
        artworks.append(Artwork(
            id=i,
            artist=name,
            title_lt=TITLES[i-1],
            year=str(now.year),
            medium_lt=random.choice(MEDIA),
            statement_lt=random.choice(STATEMENTS),
            image_prompt="(fixture)",
            image_filename=f"{i:02d}.png",
            target_filename="",  # no AR for fixture
        ))

    exhibition = Exhibition(
        month_key=month_key, month_lt=month_lt, year=now.year,
        theme=FIXTURE_THEME, artworks=artworks,
        poster_prompt="(fixture)",
        poster_filename="poster.png",
        social_caption_lt='Naujoji „Miško sapnų" paroda — 24 vizijos, 24 QR kodai, vienas miškas. Lankyti dabar.',
    )

    exhibition_dir = CONTENT / month_key
    images_dir = exhibition_dir / "images"
    if images_dir.exists():
        shutil.rmtree(exhibition_dir)
    images_dir.mkdir(parents=True)

    print(f"Generating fixture images in {images_dir}")
    make_gradient_image(images_dir / "poster.png", 0, "POSTER — MIŠKO SAPNAI")
    for art in artworks:
        make_gradient_image(images_dir / art.image_filename, art.id, art.title_lt)

    render_site(exhibition, exhibition_dir)
    print(f"\n✓ Preview ready. Run:")
    print(f"    cd {SITE} && python3 -m http.server 8000")
    print(f"  then open  http://localhost:8000/")
    print(f"  artwork:   http://localhost:8000/qr/7.html")


if __name__ == "__main__":
    main()
