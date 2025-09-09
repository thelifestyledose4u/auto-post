from http import client
import os
import random
import requests
import feedparser
import base64
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from g4f.client import Client
from dotenv import load_dotenv

load_dotenv()

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

    # ✅ Use direct image URL (better for FB previews)
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
    url = f"https://www.googleapis.com/blogger/v3/blogs/{BLOG_ID}/posts/"
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    params = {"isDraft": "true"} if draft else {}
    data = {
        "kind": "blogger#post",
        "blog": {"id": BLOG_ID},
        "title": title.replace("<h2>", "").replace("</h2>", ""),
        "content": body,
        "labels": [label]
    }

    if body: 
        resp = requests.post(url, headers=headers, json=data, params=params)
        resp.raise_for_status()
        post_url = resp.json().get("url")
        if post_url:
            share_to_facebook_pages(post_url)
        return resp.json()

def get_page_access_tokens(user_token: str):
    """
    Fetch all page access tokens for pages the user manages.
    Requires appsecret_proof when called from a server.
    """
    app_secret = os.getenv("FB_APP_SECRET")  # Make sure you add this to your .env
    proof = generate_appsecret_proof(user_token, app_secret)

    url = "https://graph.facebook.com/v20.0/me/accounts"
    params = {
        "access_token": user_token,
        "appsecret_proof": proof,
        "fields": "id,name,access_token"
    }
    response = requests.get(url, params=params)

    if response.status_code != 200:
        raise Exception(f"Error fetching pages: {response.status_code} - {response.text}")

    data = response.json()

    if "data" not in data:
        raise Exception(f"Unexpected response: {data}")

    pages = []
    for page in data["data"]:
        page_id = page.get("id")
        page_name = page.get("name")
        page_token = page.get("access_token")

        if not page_id or not page_token:
            print(f"⚠️ Skipping entry, missing id/token: {page}")
            continue

        pages.append({
            "page_name": page_name,
            "page_id": page_id,
            "access_token": page_token
        })

    return pages

import hmac
import hashlib

def generate_appsecret_proof(access_token, app_secret):
    return hmac.new(
        app_secret.encode('utf-8'),
        msg=access_token.encode('utf-8'),
        digestmod=hashlib.sha256
    ).hexdigest()

def share_to_facebook_pages(url):
    """
    Share the given blog post URL to all managed Facebook pages.
    """
    USER_ACCESS_TOKEN = os.getenv("FB_USER_ACCESS_TOKEN")

    if not USER_ACCESS_TOKEN:
        print("⚠️ No Facebook user access token found. Skipping Facebook share.")
        return

    try:
        pages = get_page_access_tokens(USER_ACCESS_TOKEN)
        if not pages:
            print("⚠️ No Facebook pages found for this account.")
            return

        results = {}
        app_secret = os.getenv("FB_APP_SECRET")

        for page in pages:
            post_url = f"https://graph.facebook.com/v20.0/{page['page_id']}/feed"

            # add appsecret_proof for security
            proof = generate_appsecret_proof(page["access_token"], app_secret)

            payload = {
                "link": url,
                "access_token": page["access_token"],
                "appsecret_proof": proof
            }

            response = requests.post(post_url, data=payload)

            if response.status_code == 200:
                print(f"✅ Shared to Facebook page: {page['page_name']}")
                results[page["page_name"]] = {"success": True, "response": response.json()}
            else:
                print(f"❌ Failed to share on {page['page_name']}")
                print(f"   Status: {response.status_code}")
                print(f"   Raw Response: {response.text}")
                results[page["page_name"]] = {
                    "success": False,
                    "error": response.text,
                    "status": response.status_code
                }

        return results

    except Exception as e:
        print(f"⚠️ Facebook sharing error: {e}")
        return None
    
# ---------------- AI ----------------
def generate_article(getarticle_text):
    client = Client()
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{
                "role": "user",
            "content": (
                "You are a professional blog writer.\n\n"
                f"Here is some source text:\n\n{getarticle_text}\n\n"
                "Your task:\n"
                "- Write a **500-word original blog post** based on the ideas and facts from the source text.\n"
                "- Do **NOT copy any sentences** or wording directly; fully rewrite in your own words.\n"
                "- Use **American English**, engaging and clear, in an **active voice**.\n"
                "- Structure with <h2> and <h3> headings.\n"
                "- Wrap paragraphs in <p> tags.\n"
                "- Use lists (<ul>/<li>) where relevant.\n"
                "- Add at least 2 authoritative outbound links (e.g., Wikipedia, IMDb, official websites).\n"
                "- Do NOT suggest images.\n"
                "- Create a catchy blog title.\n"
                "- End with a strong call-to-action that encourages readers to comment, share, or read more."
            )
        }],
        web_search=False
    )
    return response.choices[0].message.content.strip()

def create_image(title):
    client = Client()
    response = client.images.generate(
        model="flux",
        prompt=f"Featured blog illustration for: {title}",
        size="1024x1024",
        response_format="url"
    )

    image_url = response.data[0].url
    return image_url

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

def extract_article_text(article_url, max_chars=3000):
    """
    Fetch and extract readable text from an article page.
    Trims to max_chars to avoid huge prompts.
    """
    try:
        resp = requests.get(article_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Remove scripts, styles, ads
        for tag in soup(["script", "style", "aside", "footer", "header", "nav"]):
            tag.decompose()

        # Collect paragraph text
        paragraphs = soup.find_all("p")
        text = "\n".join(p.get_text(" ", strip=True) for p in paragraphs if p.get_text(strip=True))

        if not text:
            return None  # nothing extracted

        return text[:max_chars]
    except Exception as e:
        print(f"⚠️ Could not extract article text: {e}")
        return None

# ---------------- Main Flow ----------------
article_url, image_url = get_random_article()
if not article_url:
    print("⚠️ No articles found in RSS feeds.")
    exit()

getarticle_text = extract_article_text(article_url)
if not getarticle_text:
    print("⚠️ No articles found in RSS feeds.")
    exit()
    
article_text = generate_article(getarticle_text)
label = choose_label(article_text)
source_domain = get_source_domain(article_url)
title, body = format_content(article_text, image_url, source_domain)
post_to_blogger(title, body, label)
print(f"✅ Blog post published: {title} | Label: {label} | Image credit: {source_domain}")
