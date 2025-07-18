import os
import hashlib
import requests
import smtplib
import streamlit as st
import chromedriver_autoinstaller
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options as ChromeOptions

chromedriver_autoinstaller.install()

# Load environment variables
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER")

URL = "https://www.stwdo.de/wohnen/aktuelle-wohnangebote"
EDGE_DRIVER_PATH = "msedgedriver.exe"

def get_website_content(url):
    options = ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    service = ChromeService()
    driver = webdriver.Chrome(service=service, options=options)
    driver.get(url)
    content = driver.page_source
    driver.quit()
    return content


def hash_content(content):
    return hashlib.sha256(content.encode("utf-8")).hexdigest()

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    requests.post(url, data=data)

def send_email(subject, message):
    msg = MIMEMultipart()
    msg["From"] = EMAIL_SENDER
    msg["To"] = EMAIL_RECEIVER
    msg["Subject"] = subject
    msg.attach(MIMEText(message, "plain"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.send_message(msg)

# Streamlit UI
st.title("🌐 Website Change Tracker")
if "prev_hash" not in st.session_state:
    st.session_state.prev_hash = None

if st.button("Check Website for Changes"):
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
