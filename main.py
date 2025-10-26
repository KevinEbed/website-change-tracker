import streamlit as st
import requests
import hashlib
import json
import os
import smtplib
import threading
import time
import certifi
from datetime import datetime
from email.mime.text import MIMEText
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from dotenv import load_dotenv

# ---------------- Ping Handler ----------------
if st.query_params.get("ping") == ["1"]:
    st.write("✅ Pong! The app is alive.")
    st.stop()  # Stop the rest of the app from running


# ---------------- Setup ----------------
st.set_page_config(page_title="Website Change Tracker", layout="centered")

load_dotenv()

EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

DATA_FILE = "urls.json"
if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, "w") as f:
        json.dump([], f)


# ---------------- Helpers ----------------
def send_email(subject, body):
    """Send an email notification."""
    if not EMAIL_SENDER or not EMAIL_PASSWORD:
        print("[WARN] Missing email credentials.")
        return
    try:
        msg = MIMEText(body)
        msg["From"] = EMAIL_SENDER
        msg["To"] = EMAIL_RECEIVER
        msg["Subject"] = subject

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.send_message(msg)
        print("[INFO] Email sent.")
    except Exception as e:
        print(f"[ERROR] Failed to send email: {e}")


def send_telegram(message):
    """Send a Telegram message."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("[WARN] Missing Telegram credentials.")
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": message})
        print("[INFO] Telegram message sent.")
    except Exception as e:
        print(f"[ERROR] Telegram failed: {e}")


def load_urls():
    """Load URLs from the JSON file."""
    with open(DATA_FILE, "r") as f:
        return json.load(f)


def save_urls(data):
    """Save URLs to the JSON file."""
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)


def get_page_hash(url):
    """Fetch a URL and return its content hash using safe SSL and retries."""
    session = requests.Session()
    retry = Retry(connect=3, backoff_factor=2)
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    try:
        response = session.get(url, timeout=15, verify=certifi.where())
        response.raise_for_status()
        return hashlib.sha256(response.text.encode("utf-8")).hexdigest()
    except Exception as e:
        st.error(f"❌ Error fetching {url}: {e}")
        print(f"[ERROR] {url} fetch failed: {e}")
        return None


def monitor_website(url_entry):
    """Background thread to monitor a single URL."""
    url = url_entry["link"]
    interval = url_entry["interval"]
    print(f"👀 Monitoring {url}")

    old_hash = get_page_hash(url)
    if not old_hash:
        print(f"[ERROR] Could not fetch initial content for {url}.")
        return

    while url_entry["monitoring"]:
        time.sleep(interval)
        current_hash = get_page_hash(url)
        if not current_hash:
            continue

        if current_hash != old_hash:
            print(f"[CHANGE] {url} changed at {datetime.now()}")
            message = f"🔔 Change detected on:\n{url}\nTime: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            send_email("Website Content Changed", message)
            send_telegram(message)
            old_hash = current_hash

        urls = load_urls()
        for entry in urls:
            if entry["link"] == url:
                url_entry["monitoring"] = entry["monitoring"]
        save_urls(urls)

        if not url_entry["monitoring"]:
            print(f"[INFO] Stopped monitoring {url}")
            break


# ---------------- Streamlit UI ----------------
st.title("🔍 Website Change Tracker")

urls = load_urls()

# Add new URL form
with st.form("add_url_form"):
    link = st.text_input("Enter URL")
    interval = st.number_input("Check every (seconds)", min_value=10, value=60)
    submitted = st.form_submit_button("➕ Add URL")

    if submitted and link:
        new_entry = {"link": link, "interval": interval, "monitoring": False}
        urls.append(new_entry)
        save_urls(urls)
        st.success(f"✅ Added {link} with interval {interval}s")
        st.rerun()

# Display tracked URLs
st.subheader("Tracked URLs")

if not urls:
    st.info("No URLs are being tracked yet. Add one above.")
else:
    for i, entry in enumerate(urls):
        cols = st.columns([4, 1, 1, 1])
        status = "🟢 Monitoring" if entry["monitoring"] else "⚪ Idle"
        cols[0].markdown(f"**{entry['link']}** ({entry['interval']}s) — {status}")

        if cols[1].button("▶️ Start", key=f"start_{i}"):
            if not entry["monitoring"]:
                entry["monitoring"] = True
                save_urls(urls)
                threading.Thread(target=monitor_website, args=(entry,), daemon=True).start()
                st.success(f"Started monitoring {entry['link']}")
                st.rerun()

        if cols[2].button("⛔ Stop", key=f"stop_{i}"):
            entry["monitoring"] = False
            save_urls(urls)
            st.info(f"Stopped monitoring {entry['link']}")
            st.rerun()

        if cols[3].button("🗑 Delete", key=f"delete_{i}"):
            entry["monitoring"] = False
            del urls[i]
            save_urls(urls)
            st.warning(f"Deleted {entry['link']}")
            st.rerun()

# Footer
st.markdown("---")
st.caption("🧠 Built with ❤️ using Streamlit, Python, and Certifi for safe HTTPS handling.")
