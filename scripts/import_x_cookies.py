import os
import json
from dotenv import load_dotenv

def import_cookies():
    load_dotenv()
    cookies_str = os.getenv("X_COOKIES", "")
    if not cookies_str:
        print("No X_COOKIES found in .env")
        return
        
    cookie_parts = cookies_str.split(";")
    cookies = []
    
    for part in cookie_parts:
        if "=" not in part:
            continue
        name, value = part.strip().split("=", 1)
        # Add to both .x.com and .twitter.com to ensure compatibility
        for domain in [".x.com", ".twitter.com"]:
            cookies.append({
                "name": name,
                "value": value,
                "domain": domain,
                "path": "/",
                "expires": 2147483647,  # far future
                "httpOnly": name == "auth_token",
                "secure": True,
                "sameSite": "Lax" if name == "ct0" else "None"
            })
            
    state = {
        "cookies": cookies,
        "origins": []
    }
    
    os.makedirs(os.path.join("data", "x"), exist_ok=True)
    state_file = os.path.join("data", "x", "playwright_state.json")
    
    with open(state_file, "w") as f:
        json.dump(state, f, indent=2)
        
    print(f"Successfully converted X_COOKIES from .env to {state_file}!")

if __name__ == "__main__":
    import_cookies()
