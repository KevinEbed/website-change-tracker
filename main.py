import os
import hashlib
import requests
import smtplib
import streamlit as st
from bs4 import BeautifulSoup
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
from streamlit_autorefresh import st_autorefresh
from datetime import datetime
import datetime
import random

# Load environment variables from .env
load_dotenv()

# Credentials from environment
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER")

# Website to monitor
URL = "https://www.stwdo.de/wohnen/aktuelle-wohnangebote"

# Scrape website content
def get_website_content(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.content, "html.parser")
    return soup.prettify()

# Hash the website content
def hash_content(content):
    return hashlib.sha256(content.encode("utf-8")).hexdigest()

# Send message to Telegram
def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    requests.post(url, data=data)

# Send email
def send_email(subject, message):
    msg = MIMEMultipart()
    msg["From"] = EMAIL_SENDER
    msg["To"] = EMAIL_RECEIVER
    msg["Subject"] = subject
    msg.attach(MIMEText(message, "plain"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.send_message(msg)

# Auto-refresh every 5 minutes
st_autorefresh(interval=300000, key="refresh")  # 5 minutes = 300,000 ms

st.title("🌐 Website Change Tracker")
st.caption(f"⏱️ Last checked: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
heartbeat = random.choice(["🟢", "🟡", "🟣", "🔵", "🟠"])
st.markdown(f"### Status: {heartbeat} Monitoring every 5 minutes...")
st.write(f"🔁 Refresh count: {st.session_state.refresh_count}")

# Show current timestamp
now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
st.markdown(f"🕒 Last checked: `{now}`")

# Store previous hash in session
if "prev_hash" not in st.session_state:
    st.session_state.prev_hash = None

# Visual loading spinner
with st.spinner("Checking website for changes..."):
    try:
        content = get_website_content(URL)
        current_hash = hash_content(content)

        if st.session_state.prev_hash is None:
            st.session_state.prev_hash = current_hash
            st.success("✅ First load done. Hash saved.")
        elif current_hash != st.session_state.prev_hash:
            st.warning("⚠️ Change Detected!")
            st.session_state.prev_hash = current_hash
            send_telegram_message("⚠️ Change detected on the website!")
            send_email("Website Change Detected", "A change was detected on the monitored website.")
        else:
            st.info("✅ No change detected.")
    except Exception as e:
        st.error(f"❌ Error: {e}")

# Visual heartbeat indicator
st.markdown("💓 *App is running and refreshing automatically.*")
