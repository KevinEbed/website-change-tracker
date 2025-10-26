import streamlit as st
import requests
import hashlib
import json
import os
import time
from datetime import datetime

# ---------------------------
# Configuration
# ---------------------------
DATA_FILE = "data.json"
CHECK_INTERVAL_MINUTES = 30  # how often to auto-check in minutes
ALERT_SOUND_URL = "https://actions.google.com/sounds/v1/alarms/beep_short.ogg"

# ---------------------------
# Utility functions
# ---------------------------

def load_data():
    """Load saved tracking data from JSON."""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"tracked_urls": []}


def save_data(data):
    """Save tracking data to JSON."""
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


def get_page_hash(url):
    """Fetch a URL and return its content hash."""
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        return hashlib.sha256(response.text.encode("utf-8")).hexdigest()
    except Exception as e:
        st.error(f"❌ Error fetching {url}: {e}")
        return None


def check_for_changes(entry):
    """Check if a website changed and return update status."""
    current_hash = get_page_hash(entry["url"])
    if current_hash:
        if current_hash != entry["last_hash"]:
            entry["status"] = "🟡 Updated!"
            entry["last_hash"] = current_hash
            entry["last_checked"] = str(datetime.now())
            save_data(data)
            st.success(f"✅ Change detected for: {entry['url']}")
            st.audio(ALERT_SOUND_URL)
        else:
            entry["status"] = "🟢 No Change"
            entry["last_checked"] = str(datetime.now())
            save_data(data)
            st.info(f"No changes found for: {entry['url']}")


# ---------------------------
# Streamlit UI setup
# ---------------------------

st.set_page_config(page_title="Website Change Tracker", layout="wide")

st.title("🔍 Website Change Tracker")
st.caption("Monitor any web page for updates — perfect for apartment listings, news, or offers.")

data = load_data()

# Sidebar for adding/removing URLs
st.sidebar.header("⚙️ Settings")

new_url = st.sidebar.text_input("Enter a URL to track:")

if st.sidebar.button("➕ Add URL"):
    if new_url.strip() == "":
        st.sidebar.warning("Please enter a valid URL.")
    elif any(u["url"] == new_url for u in data["tracked_urls"]):
        st.sidebar.info("That URL is already being tracked.")
    else:
        page_hash = get_page_hash(new_url)
        if page_hash:
            data["tracked_urls"].append({
                "url": new_url,
                "last_hash": page_hash,
                "last_checked": str(datetime.now()),
                "status": "🟢 No Change Yet"
            })
            save_data(data)
            st.sidebar.success("✅ URL added successfully!")

# Remove URLs
if data["tracked_urls"]:
    url_to_remove = st.sidebar.selectbox("Select URL to remove:", [u["url"] for u in data["tracked_urls"]])
    if st.sidebar.button("❌ Remove Selected"):
        data["tracked_urls"] = [u for u in data["tracked_urls"] if u["url"] != url_to_remove]
        save_data(data)
        st.sidebar.success("🗑️ URL removed successfully!")

# ---------------------------
# Main dashboard
# ---------------------------

st.subheader("📋 Tracked Websites")

if not data["tracked_urls"]:
    st.info("No URLs are being tracked yet. Add one from the sidebar.")
else:
    for entry in data["tracked_urls"]:
        col1, col2, col3, col4 = st.columns([4, 2, 2, 2])

        with col1:
            st.markdown(f"[{entry['url']}]({entry['url']})")

        with col2:
            st.write(entry["status"])

        with col3:
            st.write(entry["last_checked"].split(".")[0])

        with col4:
            if st.button("🔄 Check Now", key=entry["url"]):
                check_for_changes(entry)

# ---------------------------
# Automatic periodic checking
# ---------------------------

st.markdown("---")
st.subheader("⏱️ Auto Check Settings")

if "last_auto_check" not in st.session_state:
    st.session_state.last_auto_check = 0

time_since_last = (time.time() - st.session_state.last_auto_check) / 60

if st.button("🔁 Run Auto Check Now"):
    for entry in data["tracked_urls"]:
        check_for_changes(entry)
    st.session_state.last_auto_check = time.time()
    st.success("✅ Manual auto-check completed.")

# Auto-check logic
if time_since_last > CHECK_INTERVAL_MINUTES:
    st.session_state.last_auto_check = time.time()
    for entry in data["tracked_urls"]:
        check_for_changes(entry)
    st.info(f"⏱️ Auto check performed at {datetime.now().strftime('%H:%M:%S')}")

# ---------------------------
# Footer
# ---------------------------
st.markdown("---")
st.caption("💡 Tip: Leave this app open — it auto-checks your tracked websites every 30 minutes and alerts you when changes occur.")
