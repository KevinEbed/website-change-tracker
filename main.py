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

# Initialize session state variables
if "prev_hash" not in st.session_state:
    st.session_state.prev_hash = None
if "refresh_count" not in st.session_state:
    st.session_state.refresh_count = 0

# Auto-refresh every 5 minutes
st_autorefresh(interval=300000, key="refresh")  # 5 minutes = 300,000 ms
st.session_state.refresh_count += 1

# App UI
st.title("🌐 Website Change Tracker")
now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
heartbeat = random.choice(["🟢", "🟡", "🟣", "🔵", "🟠"])
st.markdown(f"### {heartbeat} Monitoring every 5 minutes")
st.markdown(f"🕒 **Last checked:** `{now}`")
st.markdown(f"🔁 **Refresh count:** `{st.session_state.refresh_count}`")

# Check for changes with loading spinner
with st.spinner("🔍 Checking website for changes..."):
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
            send_email("Website Change Detected", f"A change was detected at {now}.\n\nURL: {URL}")
        else:
            st.info("✅ No change detected.")
    except Exception as e:
        st.error(f"❌ Error occurred: {e}")

# Final status
st.markdown("💓 *This app is running and will check the website every 5 minutes automatically.*")
