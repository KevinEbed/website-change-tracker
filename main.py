import streamlit as st
from flask_sqlalchemy import SQLAlchemy
import requests
import hashlib
import os
import smtplib
import threading
import time
from datetime import datetime
from email.mime.text import MIMEText
from dotenv import load_dotenv
from sqlalchemy import create_engine, Column, Integer, String, Boolean
from sqlalchemy.orm import sessionmaker, declarative_base

# ---------------- Load environment variables ----------------
load_dotenv()
EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# ---------------- Database setup ----------------
Base = declarative_base()
engine = create_engine("sqlite:///urls.db")
Session = sessionmaker(bind=engine)
db_session = Session()

class URL(Base):
    __tablename__ = "urls"
    id = Column(Integer, primary_key=True)
    link = Column(String(500), nullable=False)
    monitoring = Column(Boolean, default=False)
    interval = Column(Integer, default=60)

Base.metadata.create_all(engine)

# ---------------- Global data ----------------
monitoring_threads = {}

# ---------------- Notification functions ----------------
def send_email(subject, body):
    msg = MIMEText(body)
    msg['From'] = EMAIL_SENDER
    msg['To'] = EMAIL_RECEIVER
    msg['Subject'] = subject
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.send_message(msg)
        print("[INFO] Email sent.")
    except Exception as e:
        print(f"[ERROR] Failed to send email: {e}")

def send_telegram(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message
        }
        requests.post(url, data=payload)
        print("[INFO] Telegram message sent.")
    except Exception as e:
        print(f"[ERROR] Failed to send Telegram message: {e}")

# ---------------- Monitoring function ----------------
def monitor_website(url, url_id, interval):
    print(f"👀 Monitoring {url}")
    try:
        response = requests.get(url)
        old_hash = hashlib.md5(response.content).hexdigest()
    except Exception as e:
        print(f"[ERROR] Failed to fetch initial content: {e}")
        return

    while True:
        session = Session()
        url_obj = session.query(URL).get(url_id)
        if not url_obj or not url_obj.monitoring:
            print(f"[INFO] Monitoring stopped for {url}")
            session.close()
            break

        try:
            time.sleep(interval)
            response = requests.get(url)
            current_hash = hashlib.md5(response.content).hexdigest()
            if current_hash != old_hash:
                print(f"[INFO] Change detected on {url} at {datetime.now()}")
                message = f"🔔 Change detected on: {url} at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                send_email("Website Content Changed", message)
                send_telegram(message)
                old_hash = current_hash
            else:
                print(f"[DEBUG] No change at {datetime.now()}")
        except Exception as e:
            print(f"[ERROR] Error during monitoring: {e}")

# ---------------- Streamlit App ----------------
st.set_page_config(page_title="Website Change Monitor", layout="centered")

# --- PING/PONG handler ---
query_params = st.query_params
if "ping" in query_params:
    st.write("pong")
    st.stop()  # Stop execution after responding

st.title("🔍 Website Change Monitor")

# Auto-resume monitoring on app restart
for url in db_session.query(URL).filter_by(monitoring=True).all():
    if url.id not in monitoring_threads:
        thread = threading.Thread(target=monitor_website, args=(url.link, url.id, url.interval), daemon=True)
        monitoring_threads[url.id] = thread
        thread.start()
        print(f"[AUTO] Resumed monitoring for {url.link}")

# ---------------- Add URL Form ----------------
with st.form("add_url_form"):
    link = st.text_input("Enter URL")
    interval = st.number_input("Check every (seconds)", min_value=10, value=60)
    submitted = st.form_submit_button("➕ Add URL")
    if submitted and link:
        new_url = URL(link=link, interval=interval)
        db_session.add(new_url)
        db_session.commit()
        st.success(f"Added {link} with interval {interval}s")

# ---------------- Display URLs ----------------
urls = db_session.query(URL).all()
st.subheader("Tracked URLs")

for url in urls:
    cols = st.columns([4, 1, 1, 1])
    cols[0].write(f"**{url.link}** ({url.interval}s)")
    if url.monitoring:
        cols[0].markdown('<span style="color:green;">Monitoring</span>', unsafe_allow_html=True)
    else:
        cols[0].markdown('<span style="color:gray;">Idle</span>', unsafe_allow_html=True)

    if cols[1].button("▶️ Start", key=f"start_{url.id}"):
        if not url.monitoring:
            url.monitoring = True
            db_session.commit()
            thread = threading.Thread(target=monitor_website, args=(url.link, url.id, url.interval), daemon=True)
            monitoring_threads[url.id] = thread
            thread.start()
            st.rerun()

    if cols[2].button("⛔ Stop", key=f"stop_{url.id}"):
        url.monitoring = False
        db_session.commit()
        st.rerun()

    if cols[3].button("🗑 Delete", key=f"delete_{url.id}"):
        url.monitoring = False
        db_session.delete(url)
        db_session.commit()
        st.rerun()
