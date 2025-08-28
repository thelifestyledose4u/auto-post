import requests

CLIENT_ID = "YOUR_CLIENT_ID"
CLIENT_SECRET = "YOUR_CLIENT_SECRET"
REFRESH_TOKEN = "YOUR_REFRESH_TOKEN"
BLOG_ID = "YOUR_BLOG_ID"

# Get new access token
def get_access_token():
    token_url = "https://oauth2.googleapis.com/token"
    payload = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "refresh_token": REFRESH_TOKEN,
        "grant_type": "refresh_token"
    }
    r = requests.post(token_url, data=payload)
    r.raise_for_status()
    return r.json()["access_token"]

# Post to Blogger
def post_to_blogger(title, content):
    access_token = get_access_token()
    url = f"https://www.googleapis.com/blogger/v3/blogs/{BLOG_ID}/posts/"
    headers = {"Authorization": f"Bearer {access_token}",
               "Content-Type": "application/json"}
    body = {
        "kind": "blogger#post",
        "title": title,
        "content": content
    }
    r = requests.post(url, headers=headers, json=body)
    r.raise_for_status()
    return r.json()

if __name__ == "__main__":
    post = post_to_blogger(
        "Auto Post Title",
        "<p>This is an auto-posted article using pure REST API 🚀</p>"
    )
    print("✅ Published:", post["url"])
