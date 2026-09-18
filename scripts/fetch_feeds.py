#!/usr/bin/env python3
"""
Pulls every feed listed in feeds.json, merges new items into data/articles.json,
and keeps only articles published in the last 24 hours. Designed to run
unattended on a schedule (see .github/workflows/update-feeds.yml).

Usage: python3 scripts/fetch_feeds.py
"""
import json
import hashlib
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from email.utils import parsedate_to_datetime

import feedparser

ROOT = Path(__file__).resolve().parent.parent
FEEDS_FILE = ROOT / "feeds.json"
DATA_FILE = ROOT / "data" / "articles.json"
FRESHNESS_HOURS = 24   # anything older than this is dropped every run
SAFETY_CAP = 500       # hard ceiling in case a burst of items comes in


def clean_html(raw: str) -> str:
    """Strip tags and collapse whitespace so summaries render as plain text."""
    if not raw:
        return ""
    text = re.sub(r"<[^>]+>", " ", raw)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:280]


def parse_date(entry) -> str:
    """Return an ISO-8601 UTC timestamp, falling back to now() if a feed omits one."""
    for key in ("published", "updated"):
        value = entry.get(key)
        if value:
            try:
                dt = parsedate_to_datetime(value)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(timezone.utc).isoformat()
            except (TypeError, ValueError):
                pass
    return datetime.now(timezone.utc).isoformat()


def article_id(link: str) -> str:
    return hashlib.sha1(link.encode("utf-8")).hexdigest()[:16]


def load_existing() -> dict:
    if DATA_FILE.exists():
        existing = json.loads(DATA_FILE.read_text())
        return {a["id"]: a for a in existing.get("articles", [])}
    return {}


def main():
    feeds = json.loads(FEEDS_FILE.read_text())
    by_id = load_existing()
    added, seen_sources = 0, []

    for feed in feeds:
        source, url = feed["source"], feed["url"]
        parsed = feedparser.parse(url)
        if parsed.bozo and not parsed.entries:
            print(f"  [skip] {source}: could not parse feed ({parsed.bozo_exception})")
            continue

        seen_sources.append(source)
        for entry in parsed.entries:
            link = entry.get("link", "").strip()
            title = entry.get("title", "").strip()
            if not link or not title:
                continue

            aid = article_id(link)
            if aid in by_id:
                continue  # already have it, bot only adds new items

            by_id[aid] = {
                "id": aid,
                "title": title,
                "link": link,
                "source": source,
                "summary": clean_html(entry.get("summary", "")),
                "published": parse_date(entry),
            }
            added += 1

    # Prune anything older than the freshness window - this runs every time,
    # so old items (from this run OR earlier runs) always get dropped.
    cutoff = datetime.now(timezone.utc) - timedelta(hours=FRESHNESS_HOURS)
    fresh = [a for a in by_id.values() if datetime.fromisoformat(a["published"]) >= cutoff]
    dropped = len(by_id) - len(fresh)

    articles = sorted(fresh, key=lambda a: a["published"], reverse=True)[:SAFETY_CAP]

    DATA_FILE.parent.mkdir(exist_ok=True)
    DATA_FILE.write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sources_polled": seen_sources,
        "articles": articles,
    }, indent=2))

    print(f"Polled {len(seen_sources)}/{len(feeds)} feeds, added {added} new item(s), "
          f"dropped {dropped} item(s) older than {FRESHNESS_HOURS}h, "
          f"{len(articles)} total stored.")


if __name__ == "__main__":
    main()
