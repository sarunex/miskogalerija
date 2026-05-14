# Miško Galerija — Autonomous AR Forest Art Gallery

A self-running monthly art exhibition embedded in a Lithuanian forest.
Twenty-four QR-coded plates lead visitors to AI-generated artworks on
`miskogalerija.lt`. Every month, GitHub Actions generates a new theme,
24 new artworks, new statements, new poster — then uploads everything to
your Hostinger hosting via FTP. Zero manual work.

## How it runs

```
GitHub Actions (cron: 1st of each month, 04:00 UTC)
        │
        ├─ Claude API ──► theme + 24 concepts + 24 artist statements + poster copy
        ├─ OpenAI gpt-image-1 ──► 24 artwork PNGs + 1 poster
        ├─ MindAR compiler ──► 24 .mind tracking files
        └─ Jinja2 ──► /qr/N.html, /index.html, manifest.json
        │
        ▼
FTP upload to Hostinger /public_html/  (incremental — only changed files)
        │
        ▼
miskogalerija.lt  ← new exhibition live in ~5 minutes
```

## Cost (recurring monthly)

| Item                                 | Estimate      |
|--------------------------------------|---------------|
| Claude API (concepts + statements)   | $0.30–0.80    |
| OpenAI gpt-image-1 (25 images)       | $4–6          |
| Hostinger hosting                    | (already paid)|
| GitHub Actions compute               | $0 (free tier)|
| **Total new spend**                  | **~$5–7/mo**  |

## Visitor experience

1. Visitor walks through the forest, finds a 120×120 mm white plate with a QR.
2. Scans QR with phone → browser opens `miskogalerija.lt/qr/7.html`.
3. Page asks for camera permission. Visitor points at the QR plate.
4. The plate becomes a tracked marker; AI-generated artwork appears anchored to it.
5. If tracking fails (8 second timeout), page auto-falls-back to a beautiful
   full-screen artwork view with the same artist statement.
6. Tap "Apie kūrinį" → expanding sheet with full Lithuanian artist statement.

## Repo layout

```
.
├── .github/workflows/monthly.yml    # cron + manual trigger + FTP deploy
├── generator/
│   ├── run_monthly.py               # main pipeline (Python)
│   ├── preview.py                   # local preview, no API needed
│   ├── prompts/                     # Claude prompt templates (Lithuanian)
│   └── requirements.txt
├── content/                         # generated each month, kept in repo for archive
│   └── 2026-05/
│       ├── concepts.json            # snapshot before image generation
│       ├── images/                  # 24 artworks + poster
│       └── targets/                 # MindAR .mind files
├── site/                            # static site, uploaded to Hostinger /public_html/
│   ├── .htaccess                    # clean URLs, caching, gzip, security headers
│   ├── index.html                   # current exhibition landing page
│   ├── zemelapis.html               # interactive forest map with all 24 plates
│   ├── locations.json               # ★ edit this with real GPS coordinates ★
│   ├── manifest.json                # machine-readable exhibition data
│   ├── qr/N.html                    # 24 per-artwork pages
│   ├── exhibitions/2026-05/         # this month's images + targets
│   └── assets/css|js|vendor/leaflet
└── DEPLOY.md                        # step-by-step deploy guide
```

## Local preview (no API keys needed)

```bash
pip install -r generator/requirements.txt
python -m generator.preview
cd site && python3 -m http.server 8000
# open http://localhost:8000/
# scan a QR mock at http://localhost:8000/qr/7.html
```

## To deploy

See **DEPLOY.md** for the full step-by-step guide.
