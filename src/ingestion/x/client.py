import os
import logging
import asyncio
from dotenv import load_dotenv
from twscrape import API

load_dotenv()

# Singleton API instance
_api_instance = None
_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "data", "accounts.db")


def get_client():
    """Returns the singleton twscrape API instance, creating it if needed."""
    global _api_instance
    if _api_instance is None:
        os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)
        _api_instance = API(_DB_PATH)
        logging.info(f"twscrape API initialized (db: {_DB_PATH}).")
    return _api_instance


async def setup_account():
    """
    Reads X credentials from .env and adds the account to the twscrape pool
    if not already present. Supports both cookie-based and credential-based auth.
    
    Returns True if an account is available, False otherwise.
    """
    username = os.getenv("X_USERNAME", "").strip()
    password = os.getenv("X_PASSWORD", "").strip()
    email = os.getenv("X_EMAIL", "").strip()
    email_password = os.getenv("X_EMAIL_PASSWORD", "").strip()
    cookies = os.getenv("X_COOKIES", "").strip()

    if not username:
        logging.warning("X_USERNAME not set in .env — X scraping disabled.")
        return False

    api = get_client()

    # Check if account already exists in the pool
    accounts = await api.pool.accounts_info()
    user_info = next((a for a in accounts if (a.get("username") if isinstance(a, dict) else a.username) == username), None)

    try:
        if not user_info:
            if cookies:
                logging.info(f"Adding X account '{username}' via cookies...")
                await api.pool.add_account(username, password, email, email_password, cookies=cookies)
            else:
                if not password or not email:
                    logging.warning("X_PASSWORD and X_EMAIL required for credential-based auth.")
                    return False
                logging.info(f"Adding X account '{username}' via credentials...")
                await api.pool.add_account(username, password, email, email_password)

            accounts = await api.pool.accounts_info()
            user_info = next((a for a in accounts if (a.get("username") if isinstance(a, dict) else a.username) == username), None)

        if not user_info:
            logging.error(f"Failed to find X account '{username}' in pool.")
            return False

        is_active = user_info.get("active", False) if isinstance(user_info, dict) else getattr(user_info, "active", False)
        is_logged = user_info.get("logged_in", False) if isinstance(user_info, dict) else getattr(user_info, "logged_in", False)

        if is_active or is_logged:
            logging.info(f"X account '{username}' is ready (active={is_active}, logged_in={is_logged}).")
            return True

        # Try logging in if not active/logged
        logging.info(f"Logging in X account '{username}'...")
        await api.pool.login_all()

        accounts_final = await api.pool.accounts_info()
        user_final = next((a for a in accounts_final if (a.get("username") if isinstance(a, dict) else a.username) == username), None)
        if user_final:
            final_active = user_final.get("active", False) if isinstance(user_final, dict) else getattr(user_final, "active", False)
            final_logged = user_final.get("logged_in", False) if isinstance(user_final, dict) else getattr(user_final, "logged_in", False)
            if final_active or final_logged:
                logging.info(f"X account '{username}' logged in successfully.")
                return True

        err_msg = user_final.get("error_msg", "Unknown error") if user_final and isinstance(user_final, dict) else "Unknown error"
        logging.error(f"X account '{username}' setup/login failed: {err_msg}")
        return False
    except Exception as e:
        logging.error(f"Failed to setup X account '{username}': {e}")
        return False
