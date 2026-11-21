"""Fetches today's news, saves it to news.json AND to archive/<date>.json,
and (with an API key) makes daily, weekly and monthly quizzes in quiz/.
Run daily:  python fetch_news.py
Free summaries + quizzes use Google Gemini (free key from aistudio.google.com/apikey).
Set the key as the GEMINI_API_KEY environment variable. No extra install needed.
"""
import os, re, json, random, hashlib, html, datetime, urllib.request
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
MODEL = "gemini-2.5-flash"  # if you get a model error, pick a current free model in Google AI Studio
TODAY = datetime.date.today()

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

def ask(prompt, tokens=8000):
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        return None
    try:
        url = "https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent" % MODEL
        body = json.dumps({"contents": [{"parts": [{"text": prompt}]}],
                           "generationConfig": {"responseMimeType": "application/json",
                                                "maxOutputTokens": tokens}}).encode()
        req = urllib.request.Request(url, data=body, headers={
            "Content-Type": "application/json", "x-goog-api-key": key})
        data = json.loads(urllib.request.urlopen(req, timeout=120).read())
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        print("AI call failed:", e)
        return None

def add_bullets(stories):
    """One AI call for all stories (keeps us inside free limits)."""
    for s in stories:
        s["points"] = [s["desc"][:220]] if s["desc"] else []
    text = "\n".join("%d. %s | %s" % (i, s["title"], s["desc"][:300]) for i, s in enumerate(stories))
    reply = ask("For each numbered news item, write 3 short bullet points in simple English, in your own words, "
                "that an AFCAT aspirant should remember (who, what, where, numbers). "
                "Reply with JSON only: a list with one list of 3 strings per item, in the same order.\n\n" + text)
    try:
        result = json.loads(reply)
        for s, pts in zip(stories, result):
            if pts:
                s["points"] = [str(p) for p in pts[:3]]
    except Exception:
        print("Summaries skipped; using short snippets")

def save(path, obj):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)

def recent(days):
    out = []
    for i in range(days):
        d = (TODAY - datetime.timedelta(days=i)).isoformat()
        try:
            with open("archive/%s.json" % d, encoding="utf-8") as f:
                out += json.load(f)
        except Exception:
            pass
    return out

def make_quiz(name, days, n):
    stories = recent(days)
    if not stories or not os.environ.get("GEMINI_API_KEY"):
        print("Skipped %s quiz (no stories or no API key)" % name)
        return
    stories = random.sample(stories, min(len(stories), 120))
    text = "\n".join("- %s. %s" % (s["title"], " ".join(s.get("points", [])[:1])) for s in stories)[:15000]
    reply = ask("Make %d multiple-choice questions for AFCAT current affairs from these news items. "
                "Use simple English and your own words. Reply with JSON only: a list of objects with keys "
                "q, options (4 strings), answer (index 0 to 3), why (one short line).\n\n%s" % (n, text), 8000)
    try:
        quiz = json.loads(re.search(r"\[.*\]", reply, re.S).group(0))
        save("quiz/%s.json" % name, quiz)
        print("Saved", len(quiz), name, "questions")
    except Exception as e:
        print("Quiz failed:", name, e)

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
                out.append({"id": hashlib.md5(link.encode()).hexdigest()[:10],
                            "cat": cat, "title": title, "desc": desc,
                            "src": "Read full story", "link": link, "date": TODAY.isoformat()})
    add_bullets(out)
    for s in out:
        s.pop("desc", None)
    save("news.json", out)
    save("archive/%s.json" % TODAY, out)
    dates = sorted((f[:-5] for f in os.listdir("archive")
                    if re.fullmatch(r"\d{4}-\d{2}-\d{2}\.json", f)), reverse=True)
    save("archive/index.json", dates)
    print("Saved", len(out), "stories;", len(dates), "days in archive")
    make_quiz("daily", 1, 5)
    if TODAY.weekday() == 6 or not os.path.exists("quiz/weekly.json"):
        make_quiz("weekly", 7, 10)
    if TODAY.day == 1 or not os.path.exists("quiz/monthly.json"):
        make_quiz("monthly", 30, 20)

if __name__ == "__main__":
    main()
