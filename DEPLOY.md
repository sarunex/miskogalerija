# Deploy Miško Galerija to Hostinger

This guide walks you through getting the autonomous gallery live on
`miskogalerija.lt`, hosted on your Hostinger plan, with GitHub Actions
generating new exhibitions each month.

**Total time: ~20 minutes** (one-time setup; after this it's hands-off forever).

You'll need:
- A Hostinger account where `miskogalerija.lt` is hosted
- A GitHub account (free is fine)
- An Anthropic API key (https://console.anthropic.com)
- An OpenAI API key (https://platform.openai.com)

---

## Step 1 — Get your Hostinger FTP credentials

1. Log in to **hPanel** at hostinger.com.
2. Go to **Websites → Dashboard** for `miskogalerija.lt`.
3. In the left sidebar, find **FTP Accounts** (under "Files"). Click it.
4. You'll see your FTP details. Note these three values:

   - **FTP Host / Hostname** — looks like `ftp.miskogalerija.lt` or an IP address
   - **FTP Username** — looks like `u123456789` or `username@miskogalerija.lt`
   - **FTP Port** — usually `21`

5. **The password is not shown.** Click **Change FTP Password**, set a new one,
   and save it somewhere safe (password manager). You'll paste it into GitHub
   in Step 4.

> **Important — clean out `public_html` first.** If your domain currently shows a
> Hostinger placeholder page, the FTP deploy will sit alongside it. Use hPanel's
> File Manager to delete the contents of `public_html/` before your first deploy
> (don't delete the folder itself). If you have other files there you want to
> keep, the deploy will leave them — it only modifies files it tracks. But the
> default `index.html` placeholder will conflict with our `index.html`.

---

## Step 2 — Create the GitHub repository

1. Go to https://github.com/new.
2. Repository name: `miskogalerija` (or any name you like; private is fine).
3. Don't add a README, .gitignore, or license — we have those already.
4. Click **Create repository**.
5. GitHub will show you commands to push existing code. Keep that page open.

---

## Step 3 — Push the starter code to GitHub

On your local computer, in a terminal:

```bash
unzip miskogalerija-starter.zip
cd miskogalerija

git init
git add .
git commit -m "Initial commit"
git branch -M main

# Replace YOUR_USERNAME with your GitHub username
git remote add origin https://github.com/YOUR_USERNAME/miskogalerija.git
git push -u origin main
```

If you've never used git before, install it from https://git-scm.com first.

---

## Step 4 — Add secrets to the GitHub repository

The workflow needs five secrets to run. To add them:

1. In your GitHub repo, click **Settings** (top tab).
2. Left sidebar: **Secrets and variables → Actions**.
3. Click **New repository secret** for each of the five below:

| Secret name             | Value                                                   |
|-------------------------|---------------------------------------------------------|
| `ANTHROPIC_API_KEY`     | Your Anthropic API key (starts with `sk-ant-...`)       |
| `OPENAI_API_KEY`        | Your OpenAI API key (starts with `sk-...`)              |
| `HOSTINGER_FTP_HOST`    | The FTP host from Step 1 (e.g. `ftp.miskogalerija.lt`) |
| `HOSTINGER_FTP_USER`    | The FTP username from Step 1                           |
| `HOSTINGER_FTP_PASSWORD`| The FTP password you set in Step 1                     |

---

## Step 5 — Run the workflow once manually (first exhibition)

1. In your GitHub repo, click the **Actions** tab.
2. If GitHub shows a yellow banner asking to enable workflows, click **Enable**.
3. Left sidebar: click **Monthly Exhibition**.
4. Click **Run workflow** (top right of the workflow run list).
5. Leave inputs blank, click the green **Run workflow** button.
6. Wait ~5–8 minutes. The job will:
   - Generate the theme + 24 artwork concepts (~30s)
   - Generate 25 images via OpenAI (~3–5 min)
   - Compile MindAR target files (~30s)
   - Build the static site (~5s)
   - Upload everything to your Hostinger via FTP (~1–2 min)

7. When the run finishes (green checkmark), open `https://miskogalerija.lt`.
   You should see this month's exhibition live.

---

## Step 6 — Verify the QR codes work

1. Pick any artwork QR code from your printed plates.
2. Scan it with your phone.
3. The page should load at `https://miskogalerija.lt/qr/N.html`.
4. You'll see the launcher screen with a "Žiūrėti per kamerą" button.

---

## What happens automatically every month

- On the 1st of each month at 04:00 UTC (07:00 Lithuania time), the workflow
  triggers itself via cron.
- The new exhibition is generated, uploaded, and live within ~10 minutes.
- The previous month's exhibition stays accessible at
  `https://miskogalerija.lt/exhibitions/2026-04/...` (auto-archived).

You don't have to do anything. You'll get a GitHub email if any run fails.

---

## Costs you'll see

- **Anthropic + OpenAI:** ~$5–7/month total for both, billed by API usage.
- **Hostinger:** unchanged — you already pay for the plan.
- **GitHub:** $0 (public or private repo doesn't matter; Actions free tier
  is 2,000 minutes/month, you'll use ~10 min/month).

---

## Operating the gallery

### Update the gallery map with real GPS coordinates

The map at `miskogalerija.lt/zemelapis.html` reads from `site/locations.json`.
Edit that file once with your real coordinates — they don't change month to
month, only artwork content does.

```json
{
  "_center": { "lat": 55.1623, "lng": 26.0134, "zoom": 16 },
  "plates": [
    { "id": 1, "lat": 55.16234, "lng": 26.01340, "name_lt": "Pradžia" },
    { "id": 2, "lat": 55.16245, "lng": 26.01365, "name_lt": "" },
    ...
  ]
}
```

To get coordinates: open Google Maps, right-click the spot in the forest, click
the lat/lng at the top of the popup to copy. Or walk the trail with your phone
and read GPS from your camera/maps app.

After editing, commit and push:

```bash
git add site/locations.json
git commit -m "Update plate GPS coordinates"
git push
```

The next workflow run (manual or monthly) will FTP the updated map to
Hostinger. If you want it live faster, trigger the workflow manually from the
Actions tab — it'll deploy in ~6 minutes.

> **Tip:** the `_trail.points` array (in `locations.json`) draws an optional
> dashed walking path through the forest. Add a sequence of `[lat, lng]` pairs
> to draw the recommended visitor route between plates.

### Manually trigger a new exhibition early
Go to **Actions → Monthly Exhibition → Run workflow**. Optionally type a theme
hint in Lithuanian (e.g. *"Senųjų ąžuolų atmintys"*) — Claude will work with it.

### Skip a month / pause
Comment out the `schedule:` block in `.github/workflows/monthly.yml` and push.

### Inspect a generated exhibition without deploying
Run the workflow with **skip_deploy** checked. The build is uploaded as a
GitHub Actions artifact you can download and inspect.

### Roll back to a previous exhibition
Each month is committed to the repo under `content/YYYY-MM/`. To revert:

```bash
git revert <commit-sha-of-bad-exhibition>
git push
```

The next FTP sync will undo the bad upload.

---

## Troubleshooting

**"FTP login failed" in the Actions log**
Re-check `HOSTINGER_FTP_HOST`, `_USER`, and `_PASSWORD` secrets exactly. If the
password contains special characters, GitHub stores it correctly; the issue is
usually the host. Try the IP address shown in hPanel instead of the hostname.

**Try `protocol: ftps` if Hostinger requires it.**
Edit `.github/workflows/monthly.yml`, uncomment the `protocol: ftps` line, push.

**Workflow times out / images fail**
Re-run the workflow. OpenAI image generation occasionally rate-limits; the
pipeline retries internally but can hit GitHub's 30-min timeout. If consistent,
reduce `max_workers` from 4 to 2 in `generator/run_monthly.py`.

**Lithuanian characters look broken on the live site**
Open browser dev tools, check the response `Content-Type` header for the HTML
page. It should say `text/html; charset=UTF-8`. The `.htaccess` we ship handles
this with `AddDefaultCharset UTF-8`. If it's missing, hPanel may have its own
override — contact Hostinger support.

**The site shows a Hostinger placeholder instead of our index.html**
You forgot Step 1's note about cleaning `public_html/`. Open hPanel File
Manager, delete `public_html/index.html` (or `default.html`), re-run the
GitHub workflow.

**AR camera doesn't track the QR plate**
Expected. As discussed in chat, MindAR struggles with QR codes as image
markers — they all look statistically similar. The page falls back to a
beautiful static view after 8 seconds. If you want real AR tracking, we need
to add a unique image alongside each QR on the printed plates. Ask in the
next chat to wire that up.
