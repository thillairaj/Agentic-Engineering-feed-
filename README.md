# The Signal — AI & Quantum 

A self-updating website: a bot polls RSS feeds on a schedule, writes the results
to `data/articles.json`, and the static site reads that file. No server, no
database, no manual posting.

## How it works

```
.github/workflows/update-feeds.yml   ← runs scripts/fetch_feeds.py on a schedule
scripts/fetch_feeds.py               ← polls feeds.json, updates data/articles.json
feeds.json                           ← list of RSS sources (edit this to add/remove sources)
data/articles.json                   ← the bot's output; the site reads this
index.html / style.css / app.js      ← the site itself (static, no build step)
```

Every run: the bot fetches each feed, adds any articles it hasn't seen before
(deduplicated by link), keeps the newest 300, and commits the updated file.
GitHub Pages redeploys automatically whenever the repo changes — so the whole
loop runs with zero manual steps once it's set up.

## One-time setup (10 minutes)

1. **Create a GitHub repo** and push these files to it:
   ```bash
   cd agentic-engineering-feed
   git init
   git add .
   git commit -m "Initial site"
   git branch -M main
   git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
   git push -u origin main
   ```

2. **Allow the bot to push.** In your repo: Settings → Actions → General →
   Workflow permissions → select **"Read and write permissions"** → Save.
   (Without this the scheduled job can fetch articles but can't commit them.)

3. **Turn on GitHub Pages.** Settings → Pages → Source → **Deploy from a
   branch** → Branch: `main`, folder `/ (root)` → Save. GitHub gives you a URL
   like `https://YOUR_USERNAME.github.io/YOUR_REPO/`.

4. **Run the bot once manually** so the site isn't empty while you wait for
   the schedule: Actions tab → "Update feed data" → Run workflow. After it
   finishes (~30 seconds), refresh your Pages URL.

That's it — from here it updates itself on the schedule in
`.github/workflows/update-feeds.yml` (every 6 hours by default).

## Customizing

- **Change sources:** edit `feeds.json`. Any valid RSS or Atom URL works.
- **Change frequency:** edit the `cron` line in
  `.github/workflows/update-feeds.yml`. `"0 * * * *"` = hourly,
  `"0 0,6,12,18 * * *"` = 4x/day (current default), `"0 0 * * *"` = daily.
- **Change how much history is kept:** `MAX_ARTICLES` in
  `scripts/fetch_feeds.py`.
- **Test locally before pushing:**
  ```bash
  pip install -r requirements.txt
  python3 scripts/fetch_feeds.py
  python3 -m http.server 8000   # then open localhost:8000
  ```

## Notes

- If a feed URL goes stale (site restructures, feed moves), the script logs a
  `[skip]` line for it in the Action's run log and continues with the rest —
  one broken source won't stop the others from updating.
- This uses the free tiers of GitHub Actions and GitHub Pages — no hosting
  cost for a feed this size.
