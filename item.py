import os
import random
import requests
import feedparser
import base64
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from g4f.client import Client
# from dotenv import load_dotenv

# load_dotenv()

# ---------------- Config ----------------
RSS_FEEDS = [
    "https://feeds-api.dotdashmeredith.com/v1/rss/google/6bb3396f-8157-4dc5-8fcf-c1bd9d415be8",
    "https://feeds-api.dotdashmeredith.com/v1/rss/google/d5b7c39f-d8c6-4c04-994a-d4499e60b2a8",
    "https://feeds-api.dotdashmeredith.com/v1/rss/google/33159e60-7268-41c6-8368-437af4f8f3e8",
    "https://feeds-api.dotdashmeredith.com/v1/rss/google/85fdec1d-95a2-4e50-8641-5e2d0ef816a7",
    "https://www.theguardian.com/world/rss",
    "https://www.theguardian.com/uk/lifeandstyle/rss",
    "https://www.theguardian.com/uk/environment/rss",
    "https://www.theguardian.com/uk/travel/rss",
    "https://www.theguardian.com/lifeandstyle/health-and-wellbeing/rss"
]


LABELS = [
    "Celebrity Gossip",
    "Health and Fitness",
    "Invest & Grow",
    "Lifestyle",
    "News",
    "Travel"
]

CLIENT_ID = "1060084192434-mv8j60pcnh0l9trcrn3rs926gkd0bceg.apps.googleusercontent.com"
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REFRESH_TOKEN = os.getenv("GOOGLE_REFRESH_TOKEN")
BLOG_ID = "2976457714246879517"
# ---------------- Helpers ----------------
def get_random_article():
    all_entries = []
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            if feed.entries:
                all_entries.extend(feed.entries)
        except:
            pass
    if not all_entries:
        return None, None
    entry = random.choice(all_entries)
    article_url = entry.link
    image_url = get_best_image(entry, article_url)
    return article_url, image_url

def get_best_image(entry, article_url):
    if "media_content" in entry and entry.media_content:
        images = sorted(entry.media_content, key=lambda x: int(x.get("width", 0)), reverse=True)
        return images[0].get("url")
    elif "media_thumbnail" in entry and entry.media_thumbnail:
        thumbs = sorted(entry.media_thumbnail, key=lambda x: int(x.get("width", 0)), reverse=True)
        return thumbs[0].get("url")
    try:
        resp = requests.get(article_url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            og_img = soup.find("meta", property="og:image")
            if og_img and og_img.get("content"):
                return og_img["content"]
    except:
        pass
    return None

def download_image(url, filename="temp.jpg"):
    resp = requests.get(url, stream=True)
    resp.raise_for_status()
    with open(filename, "wb") as f:
        for chunk in resp.iter_content(1024):
            f.write(chunk)
    return filename

def embed_image_base64(filepath):
    with open(filepath, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")
    ext = filepath.split('.')[-1].lower()
    return f'<img src="data:image/{ext};base64,{encoded}" alt="Featured Image" />'

def get_source_domain(url):
    try:
        domain = urlparse(url).netloc
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except:
        return "Original Source"

def format_content(content, image_url=None, source_domain=None):
    lines = [ln.strip() for ln in content.splitlines() if ln.strip()]
    title = lines[0].lstrip("# ").strip() if lines else "Untitled Post"
    body_lines = lines[1:]
    formatted_parts = []
    in_list = False

    for line in body_lines:
        if line.lower().startswith("image:") or "unsplash" in line.lower():
            continue
        if line.startswith("### "):
            if in_list:
                formatted_parts.append("</ul>")
                in_list = False
            formatted_parts.append(f"<h3>{line[4:].strip()}</h3>")
        elif line.startswith("## "):
            if in_list:
                formatted_parts.append("</ul>")
                in_list = False
            formatted_parts.append(f"<h2>{line[3:].strip()}</h2>")
        elif line.startswith("- "):
            if not in_list:
                formatted_parts.append("<ul>")
                in_list = True
            formatted_parts.append(f"<li>{line[2:].strip()}</li>")
        else:
            if in_list:
                formatted_parts.append("</ul>")
                in_list = False
            formatted_parts.append(f"<p>{line}</p>")

    if in_list:
        formatted_parts.append("</ul>")

    body_html = "\n".join(formatted_parts)

    if image_url:
        # Try to download image; fallback to direct URL if fails
        local_file = None
        try:
            local_file = download_image(image_url)
            image_html = embed_image_base64(local_file)
        except Exception as e:
            print(f"⚠️ Could not download image ({e}), using direct URL instead.")
            image_html = f'<img src="{image_url}" alt="Featured Image" />'

        credit = source_domain if source_domain else "Original Source"
        body_html = f"{image_html}\n<p><em>Image credit: {credit}</em></p>\n{body_html}"

    return title, body_html

def get_access_token():
    url = "https://oauth2.googleapis.com/token"
    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "refresh_token": REFRESH_TOKEN,
        "grant_type": "refresh_token"
    }
    resp = requests.post(url, data=data)
    resp.raise_for_status()
    return resp.json()["access_token"]

def post_to_blogger(title, body, label, draft=True):
    access_token = get_access_token()
    url = f"https://www.googleapis.com/blogger/v3/blogs/{BLOG_ID}/posts/"
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    params = {"isDraft": "true"} if draft else {}
    data = {
        "kind": "blogger#post",
        "blog": {"id": BLOG_ID},
        "title": title,
        "content": body,
        "labels": [label]
    }
    resp = requests.post(url, headers=headers, json=data, params=params)
    resp.raise_for_status()
    return resp.json()

# ---------------- AI ----------------
def generate_article(article_url):
    client = Client()  # procedural version like your old working code
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{
            "role": "user",
            "content": (
                f"Write a 500-word, unique, SEO-optimized blog article based on this source: {article_url}.\n\n"
                "Requirements:\n"
                "1. Must be American English, clear, engaging, active voice.\n"
                "2. Use <h2>/<h3>, wrap paragraphs in <p>, include lists where needed.\n"
                "3. Add at least 2 authoritative outbound links (Wikipedia, IMDb, official site).\n"
                "4. No 'image suggestions'.\n"
                "5. Generate an engaging blog post title.\n"
            )
        }],
        web_search=False
    )
    return response.choices[0].message.content.strip()

def choose_label(article_text):
    client = Client()
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{
            "role": "user",
            "content": (
                f"Given this article:\n\n{article_text}\n\n"
                f"Choose ONLY ONE most relevant label from this list:\n{', '.join(LABELS)}\n"
                "Just reply with the label text, nothing else."
            )
        }]
    )
    return response.choices[0].message.content.strip()

# ---------------- Main Flow ----------------
article_url, image_url = get_random_article()
if not article_url:
    print("⚠️ No articles found in RSS feeds.")
    exit()

article_text = generate_article(article_url)
label = choose_label(article_text)
source_domain = get_source_domain(article_url)
title, body = format_content(article_text, image_url, source_domain)
post_to_blogger(title, body, label)
print(f"✅ Blog post published: {title} | Label: {label} | Image credit: {source_domain}")
