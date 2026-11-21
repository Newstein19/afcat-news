"""Fetches today's news, picks AFCAT-relevant stories, writes news.json.
Run daily:  python fetch_news.py
Optional:   pip install anthropic   and set ANTHROPIC_API_KEY for short bullet summaries.
"""
import os, re, json, hashlib, html, urllib.request
import xml.etree.ElementTree as ET

FEEDS = {
    "National": ["https://www.thehindu.com/news/national/feeder/default.rss"],
    "International": ["https://www.thehindu.com/news/international/feeder/default.rss"],
    "Economy": ["https://www.thehindu.com/business/Economy/feeder/default.rss"],
    "Sci-Tech": ["https://www.thehindu.com/sci-tech/feeder/default.rss"],
    "Sports": ["https://www.thehindu.com/sport/feeder/default.rss"],
    "Defence": ["https://news.google.com/rss/search?q=indian+army+OR+navy+OR+%22air+force%22+OR+defence+when:1d&hl=en-IN&gl=IN&ceid=IN:en"],
}
PER_CATEGORY = 5

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return urllib.request.urlopen(req, timeout=20).read()

def items(url):
    try:
        root = ET.fromstring(fetch(url))
    except Exception as e:
        print("Skipped feed:", url, e)
        return
    for it in root.iter("item"):
        title = html.unescape((it.findtext("title") or "").strip())
        link = (it.findtext("link") or "").strip()
        desc = re.sub(r"<[^>]+>", "", html.unescape(it.findtext("description") or "")).strip()
        if title and link:
            yield title, link, desc

def bullets(title, desc):
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=key)
            msg = client.messages.create(
                model="claude-sonnet-5-5", max_tokens=300,
                messages=[{"role": "user", "content":
                    "Write 3 short bullet points in simple English, in your own words, "
                    "that an AFCAT aspirant should remember from this news (who, what, where, numbers). "
                    "One bullet per line, no symbols.\n\nHeadline: %s\nDetails: %s" % (title, desc)}])
            lines = [l.strip(" -•*") for l in msg.content[0].text.splitlines() if l.strip()]
            return lines[:3]
        except Exception as e:
            print("Summary failed:", e)
    return [desc[:220]] if desc else []

def main():
    out, seen = [], set()
    for cat, urls in FEEDS.items():
        count = 0
        for url in urls:
            for title, link, desc in items(url):
                if link in seen or count >= PER_CATEGORY:
                    continue
                seen.add(link)
                count += 1
                out.append({
                    "id": hashlib.md5(link.encode()).hexdigest()[:10],
                    "cat": cat, "title": title,
                    "points": bullets(title, desc),
                    "src": "Read full story", "link": link,
                })
    with open("news.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("Saved", len(out), "stories to news.json")

main()
