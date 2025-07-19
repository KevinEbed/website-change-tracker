import streamlit as st
import requests
import hashlib
import time
import os
from dotenv import load_dotenv
import smtplib
from email.mime.text import MIMEText

# Load environment variables
load_dotenv()
EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

st.set_page_config(page_title="Website Change Detector", layout="centered")
st.title("🌐 Website Change Detector")

url = st.text_input("Enter the URL to monitor:", value="", placeholder="https://example.com")

refresh_interval = st.number_input("Check every (seconds)", min_value=10, max_value=3600, value=60)

def send_email_notification(url):
    subject = "🔔 Website Change Detected"
    body = f"The content at {url} has changed."
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = EMAIL_SENDER
    msg["To"] = EMAIL_RECEIVER

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.send_message(msg)
        st.success("📧 Email notification sent!")
    except Exception as e:
        st.error(f"❌ Email failed: {e}")

def send_telegram_notification(url):
    message = f"🔔 Change detected at {url}"
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data={"chat_id": TELEGRAM_CHAT_ID, "text": message}
        )
        if response.status_code == 200:
            st.success("📩 Telegram notification sent!")
        else:
            st.warning("⚠️ Telegram message failed to send.")
    except Exception as e:
        st.error(f"❌ Telegram error: {e}")

if url.strip() != "":
    placeholder = st.empty()
    prev_hash = None
    refresh_count = 0

    while True:
        try:
            response = requests.get(url, timeout=10)
            content = response.text
            current_hash = hashlib.md5(content.encode()).hexdigest()

            if prev_hash is None:
                prev_hash = current_hash
                placeholder.success("✅ Monitoring started. Waiting for changes...")

            elif current_hash != prev_hash:
                st.error("🚨 Change Detected!")
                send_email_notification(url)
                send_telegram_notification(url)
                prev_hash = current_hash
            else:
                placeholder.info(f"🔁 Refresh count: {refresh_count + 1}")

            refresh_count += 1
            time.sleep(refresh_interval)

        except Exception as e:
            st.error(f"❌ Error while checking the website: {e}")
            break
else:
    st.info("ℹ️ Please enter a URL above to begin monitoring.")
