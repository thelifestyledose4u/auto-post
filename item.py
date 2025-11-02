import os
import random
import requests
import feedparser
import base64
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from g4f.client import Client
from dotenv import load_dotenv
import hmac
import hashlib
from g4f.Provider import MetaAI
import re


load_dotenv()

CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REFRESH_TOKEN = os.getenv("GOOGLE_REFRESH_TOKEN")
if not CLIENT_SECRET or not REFRESH_TOKEN:
    raise RuntimeError("Missing CLIENT_SECRET or GOOGLE_REFRESH_TOKEN in environment. Please check your .env file.")

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
BLOG_ID = '2976457714246879517'

if not CLIENT_SECRET or not REFRESH_TOKEN:
    raise RuntimeError("Missing CLIENT_SECRET or GOOGLE_REFRESH_TOKEN in environment. Please check your .env file.")

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

def get_source_domain(url):
    try:
        domain = urlparse(url).netloc
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except:
        return "Original Source"

def format_content(content, image_url=None, source_domain=None):
    def strip_wrapped_bold(s: str) -> str:
        # Remove wrapping ** ... ** only when they surround the entire line
        return re.sub(r'^\*\*\s*(.*?)\s*\*\*$', r'\1', s)

    def remove_inline_bold(s: str) -> str:
        # Remove **...** anywhere in the line (keeps inner text)
        return re.sub(r'\*\*(.*?)\*\*', r'\1', s)

    lines = [ln.rstrip() for ln in content.splitlines() if ln.strip()]
    title = lines[0].lstrip("# ").strip() if lines else "Untitled Post"
    title = strip_wrapped_bold(title)
    title = remove_inline_bold(title)
    body_lines = lines[1:]
    formatted_parts = []
    in_list = False

    for raw_line in body_lines:
        line = raw_line.strip()
        # remove any inline bold markers so list items and headings lose ** markers
        line = remove_inline_bold(line)

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
        elif line.startswith("- ") or line.startswith("* "):
            if not in_list:
                formatted_parts.append("<ul>")
                in_list = True
            item_text = line[2:].strip()
            formatted_parts.append(f"<li>{item_text}</li>")
        else:
            if in_list:
                formatted_parts.append("</ul>")
                in_list = False
            formatted_parts.append(f"<p>{line}</p>")

    if in_list:
        formatted_parts.append("</ul>")

    body_html = "\n".join(formatted_parts)

    # ✅ Keep direct image (better for FB previews)
    if image_url:
        image_html = f'<img src="{image_url}" alt="Featured Image" style="max-width:100%;height:auto;" />'
        credit = source_domain if source_domain else "Original Source"
        body_html = f"{image_html}\n\n{body_html}\n\n<p><em>Image Credit: {credit}</em></p>"

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

def post_to_blogger(title, body, label, draft=False):
    access_token = get_access_token()
    # Remove HTML tags from title safely
    import re
    title = re.sub(r'<[^>]+>', '', title).strip()

    url = f"https://www.googleapis.com/blogger/v3/blogs/{BLOG_ID}/posts/"
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    params = {"isDraft": "true"} if draft else {}
    
    data = {
        "kind": "blogger#post",
        "blog": {"id": BLOG_ID},
        "title": title,
        "content": body,
        "labels": [label] if label else []
    }

    if body:
        resp = requests.post(url, headers=headers, json=data, params=params)

        # ✅ Skip failed publishes
        if resp.status_code == 502:
            print(f"⚠️ Blogger 502 error. Skipping: {title}")
            return None

        resp.raise_for_status()
        post_url = resp.json().get("url")

        if post_url:
            share_to_facebook_pages(post_url, title)

        return resp.json()

# ---------------- Facebook ----------------
def generate_appsecret_proof(access_token, app_secret):
    return hmac.new(
        app_secret.encode('utf-8'),
        msg=access_token.encode('utf-8'),
        digestmod=hashlib.sha256
    ).hexdigest()

def get_page_access_tokens(user_token: str):
    app_secret = os.getenv("FB_APP_SECRET")
    proof = generate_appsecret_proof(user_token, app_secret)

    url = "https://graph.facebook.com/v20.0/me/accounts"
    params = {
        "access_token": user_token,
        "appsecret_proof": proof,
        "fields": "id,name,access_token"
    }
    response = requests.get(url, params=params)
    response.raise_for_status()

    data = response.json()
    return [
        {"page_name": page["name"], "page_id": page["id"], "access_token": page["access_token"]}
        for page in data.get("data", [])
        if "id" in page and "access_token" in page
    ]

def share_to_facebook_pages(url, title):
    USER_ACCESS_TOKEN = os.getenv("FB_USER_ACCESS_TOKEN")
    app_secret = os.getenv("FB_APP_SECRET")

    if not USER_ACCESS_TOKEN:
        print("⚠️ No Facebook user token. Skipping FB share.")
        return

    try:
        pages = get_page_access_tokens(USER_ACCESS_TOKEN)
        if not pages:
            print("⚠️ No Facebook pages found.")
            return

        for page in pages:
            post_url = f"https://graph.facebook.com/v20.0/{page['page_id']}/feed"
            proof = generate_appsecret_proof(page["access_token"], app_secret)

            payload = {
                "link": url,
                "message": f"📢 New blog post: {title}\nRead more: {url}",
                "access_token": page["access_token"],
                "appsecret_proof": proof,
            }

            # ✅ Force visibility public
            payload["privacy"] = '{"value":"EVERYONE"}'

            response = requests.post(post_url, data=payload)
            if response.status_code == 200:
                print(f"✅ Shared to Facebook page: {page['page_name']}")
            else:
                print(f"❌ FB share failed: {page['page_name']} → {response.text}")

    except Exception as e:
        print(f"⚠️ Facebook sharing error: {e}")

# ---------------- AI ----------------
def generate_article(getarticle_text, max_retries=3):
    if not getarticle_text or len(getarticle_text.strip()) < 100:
        return None

    for attempt in range(max_retries):
        try:
            client = Client(provider=MetaAI)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{
                    "role": "user",
                    "content": (
                        "You are a professional blog writer.\n\n"
                        f"Here is some source text:\n\n{getarticle_text}\n\n"
                        "Write a **500-word original blog post** with <h2>/<h3> headings, <p> paragraphs, lists where needed, "
                        "2+ authoritative outbound links, American English, active voice, catchy title, and strong call-to-action."
                    )
                }]
            )

            content = response.choices[0].message.content.strip()
            if content and len(content.split()) > 100:
                return content

        except Exception as e:
            print(f"⚠️ Attempt {attempt+1} failed: {e}")
    
    print("⚠️ All attempts to generate article failed.")
    return None

def choose_label(article_text):
    client = Client(session_cookie="003032c13e-4e37-421d-8161-1181fed3caff")
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{
            "role": "user",
            "content": (
                f"Given this article:\n\n{article_text}\n\n"
                f"Choose ONLY ONE most relevant label from:\n{', '.join(LABELS)}\n"
                "Reply with the label text only."
            )
        }]
    )
    return response.choices[0].message.content.strip()

def extract_article_text(article_url, max_chars=3000):
    try:
        resp = requests.get(article_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        for tag in soup(["script", "style", "aside", "footer", "header", "nav"]):
            tag.decompose()

        paragraphs = soup.find_all("p")
        text = "\n".join(p.get_text(" ", strip=True) for p in paragraphs if p.get_text(strip=True))
        return text[:max_chars] if text else None
    except Exception as e:
        print(f"⚠️ Could not extract article text: {e}")
        return None

# ---------------- Main Flow ----------------
MAX_TRIES = 5
success = False

for attempt in range(MAX_TRIES):
    print(f"🔄 Attempt {attempt + 1}/{MAX_TRIES}...")

    article_url, image_url = get_random_article()
    if not article_url:
        print("⚠️ No articles found in RSS feeds.")
        continue

    getarticle_text = extract_article_text(article_url)
    if not getarticle_text:
        print("⚠️ No article text extracted. Skipping...")
        continue

    try:
        article_text = generate_article(getarticle_text)
    except Exception as e:
        print(f"⚠️ AI failed to generate article: {e}")
        continue

    # ✅ Validation step (avoid “error code: 502” posts)
    if not article_text or "error code" in article_text.lower() or len(article_text.strip()) < 200:
        print("⚠️ Invalid article generated. Skipping...")
        continue

    label = choose_label(article_text)
    source_domain = get_source_domain(article_url)
    title, body = format_content(article_text, image_url, source_domain)

    # double-check title
    if not title or "error code" in title.lower():
        print("⚠️ Invalid title generated. Skipping...")
        continue

    # ✅ Publish to Blogger
    post_to_blogger(title, body, label)
    print(f"✅ Blog post published: {title} | Label: {label} | Image credit: {source_domain}")
    success = True
    break  # stop after first successful publish

if not success:
    print("❌ Failed to publish after several attempts.")
