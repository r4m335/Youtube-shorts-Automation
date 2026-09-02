import os
import json
import time

STATE_FILE = os.path.join("data", "x", "playwright_state.json")

def load_env_cookies():
    env_path = ".env"
    if not os.path.exists(env_path):
        print("No .env file found!")
        return None
        
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("X_COOKIES="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None

def inject_cookies():
    cookie_str = load_env_cookies()
    if not cookie_str:
        print("No X_COOKIES found in .env!")
        return

    cookies = []
    # Arbitrary future expiry (1 year from now)
    expires = time.time() + (365 * 24 * 60 * 60)
    
    for item in cookie_str.split(";"):
        if "=" in item:
            name, value = item.strip().split("=", 1)
            cookies.append({
                "name": name,
                "value": value,
                "domain": ".x.com",
                "path": "/",
                "expires": expires,
                "httpOnly": name == "auth_token",
                "secure": True,
                "sameSite": "Lax"
            })
            cookies.append({
                "name": name,
                "value": value,
                "domain": ".twitter.com",
                "path": "/",
                "expires": expires,
                "httpOnly": name == "auth_token",
                "secure": True,
                "sameSite": "Lax"
            })

    state = {
        "cookies": cookies,
        "origins": []
    }

    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)

    print(f"Successfully injected {len(cookies)//2} cookies from .env into Playwright state!")
    print(f"Saved to: {STATE_FILE}")

if __name__ == "__main__":
    inject_cookies()
