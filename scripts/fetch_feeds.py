#!/usr/bin/env python3
"""
Pulls every feed listed in feeds.json, merges new items into data/articles.json,
keeps only articles published in the last 24 hours, and also writes feed.xml -
an RSS 2.0 feed of the curated results so others can subscribe to this site.

Usage: python3 scripts/fetch_feeds.py
"""
import json
import hashlib
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from email.utils import parsedate_to_datetime, format_datetime
from xml.sax.saxutils import escape

import feedparser

ROOT = Path(__file__).resolve().parent.parent
FEEDS_FILE = ROOT / "feeds.json"
DATA_FILE = ROOT / "data" / "articles.json"
RSS_FILE = ROOT / "feed.xml"
SITE_URL = "https://thillairaj.github.io/Agentic-Engineering-feed-/"
FRESHNESS_HOURS = 24
SAFETY_CAP = 500
RSS_ITEM_LIMIT = 60

AGENT_KEYWORDS = re.compile(
    r"\b(agent|agentic|multi-agent|multiagent|tool.?use|tool.?calling|"
    r"autonomous|orchestrat|llm agent|reasoning agent|agent harness|"
    r"agent workflow|agent framework)\w*",
    re.IGNORECASE,
)

QUANTUM_KEYWORDS = re.compile(
    r"\b(quantum comput|qubit|quantum algorithm|quantum circuit|"
    r"quantum error correction|quantum hardware|quantum advantage|"
    r"quantum supremacy|quantum processor|quantum chip|quantum software|"
    r"quantum gate|quantum annealing)\w*",
    re.IGNORECASE,
)


def clean_html(raw: str) -> str:
    if not raw:
        return ""
    text = re.sub(r"<[^>]+>", " ", raw)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:280]


def parse_date(entry) -> str:
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


def is_relevant(source: str, category: str, title: str, summary: str) -> bool:
    if not source.lower().startswith("arxiv"):
        return True
    pattern = QUANTUM_KEYWORDS if category == "Quantum" else AGENT_KEYWORDS
    return bool(pattern.search(title) or pattern.search(summary))


def build_rss(articles) -> str:
    items = []
    for a in articles[:RSS_ITEM_LIMIT]:
        try:
            pub_dt = datetime.fromisoformat(a["published"])
        except ValueError:
            pub_dt = datetime.now(timezone.utc)
        items.append(f"""    <item>
      <title>{escape(a['title'])}</title>
      <link>{escape(a['link'])}</link>
      <guid isPermaLink="false">{a['id']}</guid>
      <description>{escape(a['summary'])}</description>
      <category>{escape(a['source'])}</category>
      <pubDate>{format_datetime(pub_dt)}</pubDate>
    </item>""")
    items_xml = "\n".join(items)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>AI Signal</title>
    <link>{SITE_URL}</link>
    <description>A self-updating feed of AI and quantum computing news, research and releases.</description>
    <lastBuildDate>{format_datetime(datetime.now(timezone.utc))}</lastBuildDate>
{items_xml}
  </channel>
</rss>
"""


def main():
    feeds = json.loads(FEEDS_FILE.read_text())
    by_id = load_existing()
    added, skipped_offtopic, seen_sources = 0, 0, []

    for feed in feeds:
        source = feed["source"]
        url = feed["url"]
        category = feed.get("category", "AI")
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
                continue

            summary = clean_html(entry.get("summary", ""))
            if not is_relevant(source, category, title, summary):
                skipped_offtopic += 1
                continue

            by_id[aid] = {
                "id": aid,
                "title": title,
                "link": link,
                "source": source,
                "category": category,
                "summary": summary,
                "published": parse_date(entry),
            }
            added += 1

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

    RSS_FILE.write_text(build_rss(articles), encoding="utf-8")

    print(f"Polled {len(seen_sources)}/{len(feeds)} feeds, added {added} new item(s) "
          f"(skipped {skipped_offtopic} off-topic), dropped {dropped} item(s) older than "
          f"{FRESHNESS_HOURS}h, {len(articles)} total stored, feed.xml written.")


if __name__ == "__main__":
    main()
