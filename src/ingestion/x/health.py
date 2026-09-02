import os
import json
import logging
from datetime import datetime, timedelta

HEALTH_FILE = os.path.join("data", "x", "health.json")
WINDOW_MINUTES = 15

class XHealthState:
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DISABLED = "disabled"

def load_health():
    if not os.path.exists(HEALTH_FILE):
        return {"state": XHealthState.HEALTHY, "failures": []}
    try:
        with open(HEALTH_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {"state": XHealthState.HEALTHY, "failures": []}

def save_health(data):
    os.makedirs(os.path.dirname(HEALTH_FILE), exist_ok=True)
    with open(HEALTH_FILE, "w") as f:
        json.dump(data, f, indent=2)

def _clean_old_failures(failures):
    cutoff = datetime.now() - timedelta(minutes=WINDOW_MINUTES)
    return [f for f in failures if datetime.fromisoformat(f["time"]) > cutoff]

def record_failure(account: str):
    data = load_health()
    now = datetime.now()
    
    data["failures"] = _clean_old_failures(data["failures"])
    data["failures"].append({"account": account, "time": now.isoformat()})
    
    failed_accounts = {f["account"] for f in data["failures"]}
    fail_count = len(data["failures"])
    
    if fail_count >= 3 and len(failed_accounts) >= 2:
        logging.warning("3+ cross-account failures within 15 minutes. Marking X as DISABLED.")
        data["state"] = XHealthState.DISABLED
    elif fail_count >= 2:
        logging.warning("2 failures within 15 minutes. Marking X as DEGRADED.")
        data["state"] = XHealthState.DEGRADED
    else:
        logging.warning(f"1 failure recorded for {account}. Retrying normally.")
        
    save_health(data)
    return data["state"]

def record_success():
    data = load_health()
    if data["state"] != XHealthState.HEALTHY or data["failures"]:
        data["state"] = XHealthState.HEALTHY
        data["failures"] = []
        save_health(data)

def check_health_status():
    data = load_health()
    old_len = len(data["failures"])
    data["failures"] = _clean_old_failures(data["failures"])
    
    # Auto-recover if failures aged out of the 15-min window
    if len(data["failures"]) < old_len:
        if len(data["failures"]) == 0:
            data["state"] = XHealthState.HEALTHY
        elif len(data["failures"]) < 3 and data["state"] == XHealthState.DISABLED:
            data["state"] = XHealthState.DEGRADED
        save_health(data)
        
    return data["state"]
