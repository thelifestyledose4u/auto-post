import os
import requests
from dotenv import load_dotenv

# Load .env variables
load_dotenv()

# --- Facebook App Config ---
APP_ID = os.getenv("FB_APP_ID")
APP_SECRET = os.getenv("FB_APP_SECRET")
USER_TOKEN = os.getenv("FB_USER_ACCESS_TOKEN") 


def refresh_fb_token():
    """Refresh Facebook long-lived user token and update .env"""
    url = "https://graph.facebook.com/v20.0/oauth/access_token"
    params = {
        "grant_type": "fb_exchange_token",
        "client_id": APP_ID,
        "client_secret": APP_SECRET,
        "fb_exchange_token": USER_TOKEN
    }

    # Request new token
    resp = requests.get(url, params=params)
    if resp.status_code != 200:
        raise Exception(f"❌ Error refreshing token: {resp.status_code} - {resp.text}")

    data = resp.json()
    new_token = data.get("access_token")
    expires_in = data.get("expires_in")  # seconds (~5184000 = 60 days)

    if not new_token:
        raise Exception("❌ No access_token returned in response.")

    days_left = expires_in / 86400
    print(f"✅ New FB token generated. Expires in {days_left:.1f} days.")

    # --- Update .env with new token ---
    env_path = ".env"
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            lines = f.readlines()
        with open(env_path, "w") as f:
            replaced = False
            for line in lines:
                if line.startswith("FB_USER_ACCESS_TOKEN="):
                    f.write(f"FB_USER_ACCESS_TOKEN={new_token}\n")
                    replaced = True
                else:
                    f.write(line)
            if not replaced:
                f.write(f"FB_USER_ACCESS_TOKEN={new_token}\n")
    else:
        with open(env_path, "w") as f:
            f.write(f"FB_USER_ACCESS_TOKEN={new_token}\n")

    return new_token


if __name__ == "__main__":
    try:
        new_token = refresh_fb_token()
        print("🔑 Updated .env with new token.")
    except Exception as e:
        print(str(e))
