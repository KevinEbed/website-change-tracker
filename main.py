import streamlit as st
import requests
import hashlib
import os
import smtplib
import threading
import time
import tempfile
from datetime import datetime
from email.mime.text import MIMEText
from dotenv import load_dotenv
from sqlalchemy import create_engine, Column, Integer, String, Boolean
from sqlalchemy.orm import sessionmaker, declarative_base

# ---------------- Setup ----------------
load_dotenv()

EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

Base = declarative_base()

# ✅ Use temp directory for Streamlit Cloud (read-only root fix)
db_path = os.path.join(tempfile.gettempdir(), "urls.db")
engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
Session = sessionmaker(bind=engine)


# ---------------- Database Model ----------------
class URL(Base):
    __tablename__ = "urls"
    id = Column(Integer, primary_key=True)
    link = Column(String(500), nullable=False)
    monitoring = Column(Boolean, default=False)
    interval = Column(Integer, default=60)


# ✅ Create tables AFTER defining the model
Base.metadata.create_all(engine)


# ---------------- Helpers ----------------
def send_email(subject, body):
    if not EMAIL_SENDER or not EMAIL_PASSWORD or not EMAIL_RECEIVER:
        print("[WARN] Email credentials missing.")
        return
    try:
        msg = MIMEText(body)
        msg["From"] = EMAIL_SENDER
        msg["To"] = EMAIL_RECEIVER
        msg["Subject"] = subject
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.send_message(msg)
        print("[INFO] Email sent successfully.")
    except Exception as e:
        print(f"[ERROR] Email failed: {e}")


def send_telegram(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("[WARN] Telegram credentials missing.")
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": message})
        print("[INFO] Telegram message sent.")
    except Exception as e:
        print(f"[ERROR] Telegram failed: {e}")


def monitor_website(url, url_id, interval):
    """Runs in a background thread."""
    print(f"👀 Monitoring {url}")
    try:
        response = requests.get(url, timeout=10)
        old_hash = hashlib.md5(response.content).hexdigest()
    except Exception as e:
        print(f"[ERROR] Initial fetch failed for {url}: {e}")
        return

    while True:
        session = Session()
        url_obj = session.get(URL, url_id)
        if not url_obj or not url_obj.monitoring:
            print(f"[INFO] Monitoring stopped for {url}")
            session.close()
            break

        try:
            time.sleep(interval)
            response = requests.get(url, timeout=10)
            current_hash = hashlib.md5(response.content).hexdigest()

            if current_hash != old_hash:
                print(f"[CHANGE] {url} changed at {datetime.now()}")
                message = f"🔔 Change detected on: {url}\nTime: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                send_email("Website Content Changed", message)
                send_telegram(message)
                old_hash = current_hash
            else:
                print(f"[DEBUG] No change for {url} at {datetime.now()}")
        except Exception as e:
            print(f"[ERROR] During monitoring of {url}: {e}")
        finally:
            session.close()


# ---------------- Ping Endpoint ----------------
def serve_ping():
    """Simple endpoint to confirm app is alive."""
    st.set_page_config(page_title="Ping")
    st.write("✅ Pong! The app is alive.")
    st.stop()


# ---------------- Streamlit UI ----------------
if st.query_params.get("ping") == "1":
    serve_ping()

st.set_page_config(page_title="Website Change Monitor", layout="centered")
st.title("🔍 Website Change Monitor")

session = Session()

# Add new URL form
with st.form("add_url_form"):
    link = st.text_input("Enter URL")
    interval = st.number_input("Check every (seconds)", min_value=10, value=60)
    submitted = st.form_submit_button("➕ Add URL")
    if submitted and link:
        existing = session.query(URL).filter_by(link=link).first()
        if existing:
            st.warning("URL already exists.")
        else:
            new_url = URL(link=link, interval=interval)
            session.add(new_url)
            session.commit()
            st.success(f"Added {link} with interval {interval}s")
            st.rerun()

urls = session.query(URL).all()
st.subheader("Tracked URLs")

if not urls:
    st.info("No URLs being tracked yet. Add one above.")
else:
    for url in urls:
        cols = st.columns([4, 1, 1, 1])
        status = "🟢 Monitoring" if url.monitoring else "⚪ Idle"
        cols[0].markdown(f"**{url.link}** ({url.interval}s) — {status}")

        if cols[1].button("▶️ Start", key=f"start_{url.id}"):
            if not url.monitoring:
                url.monitoring = True
                session.commit()
                t = threading.Thread(
                    target=monitor_website,
                    args=(url.link, url.id, url.interval),
                    daemon=True,
                )
                t.start()
                st.success(f"Started monitoring {url.link}")
                st.rerun()

        if cols[2].button("⛔ Stop", key=f"stop_{url.id}"):
            url.monitoring = False
            session.commit()
            st.info(f"Stopped monitoring {url.link}")
            st.rerun()

        if cols[3].button("🗑 Delete", key=f"delete_{url.id}"):
            url.monitoring = False
            session.delete(url)
            session.commit()
            st.warning(f"Deleted {url.link}")
            st.rerun()

session.close()
