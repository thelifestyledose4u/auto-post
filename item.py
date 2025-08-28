import requests
import feedparser
from g4f.client import Client
import os
# ---------------- RSS Feed ----------------
rss_url = "https://feeds-api.dotdashmeredith.com/v1/rss/google/79365970-e87d-4fb6-966a-1c657b08f44f"
feed = feedparser.parse(rss_url)
first_url = ""
if feed.entries:
    first_url = feed.entries[0].link

# ---------------- AI Content ----------------
article_text = ""
if first_url:
    client = Client()
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{
            "role": "user",
            "content": (
                f"Write a unique, SEO-optimized blog article (500 words) based on this source: {first_url}\n"
                "The article must:\n"
                "- Be in American English\n"
                "- Use <h2> and <h3> for headings\n"
                "- Use short paragraphs wrapped in <p>\n"
                "- Include practical tips & links to Wikipedia, IMDb, or official sites\n"
                "- End with a call to action\n"
                "- Suggest one relevant image URL with proper credit\n"
                "- Generate a good blog post title\n"
                "Do not leave the article incomplete."
            )
        }],
        web_search=False
    )
    article_text = response.choices[0].message.content.strip()

# ---------------- Blogger API Config ----------------
CLIENT_ID = "1060084192434-mv8j60pcnh0l9trcrn3rs926gkd0bceg.apps.googleusercontent.com" 
CLIENT_SECRET = os.getenv("CLIENT_SECRET") 
REFRESH_TOKEN = os.getenv("GOOGLE_REFRESH_TOKEN")
BLOG_ID = "2976457714246879517"

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

def format_content(content: str):
    """Extract title and clean body without images"""
    lines = [ln.strip() for ln in content.splitlines() if ln.strip()]
    if not lines:
        raise ValueError("AI returned empty content")

    # --- Extract title safely ---
    raw_title = lines[0]
    if raw_title.startswith(("## ", "### ")):
        title = raw_title.lstrip("# ").strip()
    else:
        title = raw_title.strip()

    # --- Everything after first line is body ---
    body_lines = lines[1:]
    if not body_lines:
        raise ValueError("AI returned only a title, no body")

    # --- Format paragraphs/headings ---
    formatted_parts = []
    for line in body_lines:
        if line.startswith("### "):
            formatted_parts.append(f"<h3>{line[4:].strip()}</h3>")
        elif line.startswith("## "):
            formatted_parts.append(f"<h2>{line[3:].strip()}</h2>")
        else:
            formatted_parts.append(f"<p>{line}</p>")

    return title, "\n".join(formatted_parts)

def post_to_blogger(title, content, draft=True):
    access_token = get_access_token()
    url = f"https://www.googleapis.com/blogger/v3/blogs/{BLOG_ID}/posts/"
    params = {"isDraft": "true"} if draft else {}
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    body = {
        "kind": "blogger#post",
        "title": title,
        "content": content
    }
    resp = requests.post(url, headers=headers, json=body, params=params)
    print("Response:", resp.text)
    resp.raise_for_status()
    return resp.json()

# ---------------- Run Auto Posting ----------------
if article_text:
    title, formatted_html = format_content(article_text)
    post_to_blogger(title, formatted_html, draft=True)
else:
    print("⚠️ No content generated from AI.")
