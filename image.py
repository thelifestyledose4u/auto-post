import os
import io
import requests
import gspread
from google.oauth2.service_account import Credentials as SA_Credentials
from google.oauth2.credentials import Credentials as OAuthCredentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from PIL import Image, ImageDraw, ImageFont
from dotenv import load_dotenv
import hmac
import hashlib
import textwrap

from g4f.client import service

load_dotenv()

# ---------------- Blogger / Drive OAuth ----------------
CLIENT_ID = "1060084192434-mv8j60pcnh0l9trcrn3rs926gkd0bceg.apps.googleusercontent.com"
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REFRESH_TOKEN = os.getenv("GOOGLE_REFRESH_TOKEN")  # Must have both Blogger + Drive scopes
BLOG_ID = "2976457714246879517"

# ---------------- Google Sheet Config ----------------
SERVICE_ACCOUNT_FILE = "service_account.json"  # for reading sheet only
SPREADSHEET_ID = os.getenv("SHEET_ID")
WORKSHEET_NAME = "Quotes"

# ---------------- Facebook ----------------
FB_USER_ACCESS_TOKEN = os.getenv("FB_USER_ACCESS_TOKEN")
FB_APP_SECRET = os.getenv("FB_APP_SECRET")

# ---------------- OAuth Helper ----------------
def get_oauth_credentials():
    scopes = [
        "https://www.googleapis.com/auth/blogger",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = OAuthCredentials(
        token=None,
        refresh_token=REFRESH_TOKEN,
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        token_uri="https://oauth2.googleapis.com/token",
        scopes=scopes
    )
    return creds

# ---------------- Drive Upload ----------------
def upload_to_freeimagehost(image):
    """
    Uploads a Pillow Image to freeimage.host using your API key.
    Returns the direct image link.
    """
    api_key = os.getenv("FREEIMAGE_API_KEY")
    if not api_key:
        raise ValueError("FREEIMAGE_API_KEY not set in environment variables")

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)

    files = {
        'source': ('quote.png', buffer, 'image/png')
    }
    data = {
        'key': api_key,
        'action': 'upload'
    }

    resp = requests.post("https://freeimage.host/api/1/upload", data=data, files=files)
    resp.raise_for_status()

    data = resp.json()
    if data.get("status_code") != 200:
        raise RuntimeError(f"FreeImageHost upload failed: {data}")

    return data['image']['url']  # Direct hotlink-safe URL

# ---------------- Image Generation ----------------
from PIL import Image, ImageDraw, ImageFont
import textwrap
import os

def generate_image(text, width=800, height=600):
    img = Image.new("RGB", (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    # Gradient background
    for y in range(height):
        r = int(255 * (1 - y/height) + 100 * (y/height))
        g = int(50 * (1 - y/height) + 180 * (y/height))
        b = int(200 * (1 - y/height) + 255 * (y/height))
        draw.line([(0, y), (width, y)], fill=(r, g, b))

    # Load a scalable font (replace with your own .ttf path if needed)
    font_path = os.path.join("DejaVuSans-Bold.ttf")  # Or any .ttf you have
    if not os.path.exists(font_path):
        font_path = "DejaVuSans-Bold.ttf" 

    # Find the largest font size that fits
    max_width = int(width * 0.85)
    max_height = int(height * 0.85)
    font_size = 10
    while True:
        font = ImageFont.truetype(font_path, font_size)
        wrapped = "\n".join(textwrap.wrap(text, width=40))
        bbox = draw.multiline_textbbox((0, 0), wrapped, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        if text_w > max_width or text_h > max_height:
            font_size -= 1
            font = ImageFont.truetype(font_path, font_size)
            break
        font_size += 2

    # Center the text
    wrapped = "\n".join(textwrap.wrap(text, width=40))
    bbox = draw.multiline_textbbox((0, 0), wrapped, font=font, align="center")
    x = (width - (bbox[2] - bbox[0])) // 2
    y = (height - (bbox[3] - bbox[1])) // 2

    draw.multiline_text((x, y), wrapped, font=font, fill="white", align="center")
    return img
# ---------------- Blogger Post ----------------
def post_to_blogger(title, body, image_url, label="Puzzle/Motivation"):
    creds = get_oauth_credentials()
    from google.auth.transport.requests import Request
    creds.refresh(Request())  # ✅ fix here

    access_token = creds.token

    url = f"https://www.googleapis.com/blogger/v3/blogs/{BLOG_ID}/posts/"
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    content = f'<p>{body}</p><p><img src="{image_url}" alt="Motivation"></p>'
    data = {
        "kind": "blogger#post",
        "blog": {"id": BLOG_ID},
        "title": title,
        "content": content,
        "labels": [label]
    }
    resp = requests.post(url, headers=headers, json=data)
    resp.raise_for_status()
    return resp.json().get("url")

# ---------------- Facebook ----------------
def generate_appsecret_proof(access_token, app_secret):
    return hmac.new(app_secret.encode(), msg=access_token.encode(), digestmod=hashlib.sha256).hexdigest()

def get_page_access_tokens(user_token):
    proof = generate_appsecret_proof(user_token, FB_APP_SECRET)
    url = "https://graph.facebook.com/v20.0/me/accounts"
    params = {"access_token": user_token, "appsecret_proof": proof, "fields": "id,name,access_token"}
    resp = requests.get(url, params=params)
    resp.raise_for_status()
    return [
        {"page_name": p["name"], "page_id": p["id"], "access_token": p["access_token"]}
        for p in resp.json().get("data", [])
        if "id" in p and "access_token" in p
    ]

def share_to_facebook_pages(url, title):
    if not FB_USER_ACCESS_TOKEN:
        print("⚠️ No Facebook user token. Skipping FB share.")
        return
    try:
        pages = get_page_access_tokens(FB_USER_ACCESS_TOKEN)
        for page in pages:
            post_url = f"https://graph.facebook.com/v20.0/{page['page_id']}/feed"
            proof = generate_appsecret_proof(page["access_token"], FB_APP_SECRET)
            payload = {
                "link": url,
                "message": f"📢 New blog post: {title}\nRead more: {url}",
                "access_token": page["access_token"],
                "appsecret_proof": proof,
                "privacy": '{"value":"EVERYONE"}'
            }
            r = requests.post(post_url, data=payload)
            print(f"✅ Shared to {page['page_name']}" if r.status_code == 200 else f"❌ FB share failed: {r.text}")
    except Exception as e:
        print(f"⚠️ FB sharing error: {e}")

# ---------------- Main Logic ----------------
def main():
    try:
        sa_creds = SA_Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=["https://www.googleapis.com/auth/spreadsheets"])
        client = gspread.authorize(sa_creds)

        try:
            sheet = client.open_by_key(SPREADSHEET_ID).worksheet(WORKSHEET_NAME)
        except gspread.SpreadsheetNotFound:
            print(f"❌ Spreadsheet not found or not shared")
            return

        rows = sheet.get_all_records()
        for i, row in enumerate(rows, start=2):
            if row.get("Posted", "").lower() == "yes":
                continue

            post_text = row.get("Post Text", "")
            engagement = row.get("Engagement Prompt", "")
            content = f"{post_text}\n\n{engagement}"

            try:
                img = generate_image(post_text)
                img_url = upload_to_freeimagehost(img)
                url = post_to_blogger(title=post_text[:60], body=content, image_url=img_url)
                print(f"✅ Posted: {post_text[:50]} | URL: {url}")

                sheet.update_cell(i, sheet.find("Posted").col, "Yes")
                share_to_facebook_pages(url, post_text)
                break  # Only 1 post per run

            except Exception as e:
                print(f"❌ Failed to post row {i}: {e}")

    except Exception as e:
        print(f"⚠️ Main error: {e}")

if __name__ == "__main__":
    main()
