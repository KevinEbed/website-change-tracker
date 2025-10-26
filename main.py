import streamlit as st
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

# ---------------- Setup ----------------
load_dotenv()

EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

Base = declarative_base()
engine = create_engine("sqlite:///urls.db", connect_args={"check_same_thread": False})
Session = sessionmaker(bind=engine)
Base.metadata.create_all(engine)


class URL(Base):
    __tablename__ = "urls"
    id = Column(Integer, primary_key=True)
    link = Column(String(500), nullable=False)
    monitoring = Column(Boolean, default=False)
    interval = Column(Integer, default=60)
    last_hash = Column(String(64), nullable=True)
    last_checked = Column(String(64), nullable=True)


# ---------------- Helpers ----------------
def send_email(subject, body):
    """Send email notification."""
    if not EMAIL_SENDER or not EMAIL_PASSWORD or not EMAIL_RECEIVER:
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
        print("[INFO] Email sent successfully.")
    except Exception as e:
        print(f"[ERROR] Email failed: {e}")


def send_telegram(message):
    """Send Telegram message."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("[WARN] Telegram credentials missing.")
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": message})
        print("[INFO] Telegram sent.")
    except Exception as e:
        print(f"[ERROR] Telegram failed: {e}")


def get_page_hash(url):
    """Safely fetch a webpage and return its hash."""
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        return hashlib.md5(response.content).hexdigest()
    except Exception as e:
        print(f"[ERROR] Could not fetch {url}: {e}")
        return None


def monitor_website(url_obj):
    """Monitor a single website in a background thread."""
    print(f"👀 Starting monitor for {url_obj.link}")
    session = Session()

    # Fetch initial hash
    old_hash = get_page_hash(url_obj.link)
    if not old_hash:
        session.close()
        return

    url_obj.last_hash = old_hash
    url_obj.last_checked = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    session.commit()

    while True:
        # Re-check database state
        db_obj = session.query(URL).get(url_obj.id)
        if not db_obj or not db_obj.monitoring:
            print(f"[STOP] Monitoring stopped for {url_obj.link}")
            session.close()
            break

        time.sleep(db_obj.interval)
        current_hash = get_page_hash(url_obj.link)
        if not current_hash:
            continue

        if db_obj.last_hash != current_hash:
            print(f"[CHANGE] Detected on {db_obj.link} at {datetime.now()}")
            message = f"🔔 Change detected on: {db_obj.link}\nTime: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            send_email("Website Changed", message)
            send_telegram(message)
            db_obj.last_hash = current_hash

        db_obj.last_checked = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        session.commit()


# ---------------- Keep Streamlit awake ----------------
def keep_alive():
    """Ping the app periodically to keep it alive."""
    while True:
        try:
            requests.get("https://website-change-tracker.streamlit.app", timeout=10)
            print("[PING] App kept alive.")
        except Exception as e:
            print(f"[WARN] Keep-alive failed: {e}")
        time.sleep(300)  # every 5 minutes


# ---------------- Streamlit UI ----------------
st.set_page_config(page_title="Website Change Monitor", layout="centered")
st.title("🔍 Website Change Monitor")

# Start keep-alive thread (only once)
if "keep_alive_thread" not in st.session_state:
    t = threading.Thread(target=keep_alive, daemon=True)
    t.start()
    st.session_state["keep_alive_thread"] = t

# Store threads globally to prevent duplicates
if "threads" not in st.session_state:
    st.session_state["threads"] = {}

# DB session
session = Session()

# Add new URL
with st.form("add_url_form"):
    link = st.text_input("Enter URL")
    interval = st.number_input("Check every (seconds)", min_value=10, value=60)
    submitted = st.form_submit_button("➕ Add URL")
    if submitted and link:
        new_url = URL(link=link, interval=interval, monitoring=True)
        session.add(new_url)
        session.commit()
        st.success(f"✅ Added {link} (every {interval}s)")
        st.rerun()

# Display URLs
urls = session.query(URL).all()
st.subheader("Tracked URLs")

if not urls:
    st.info("No URLs added yet. Add one above.")
else:
    for url in urls:
        cols = st.columns([4, 1, 1, 1])
        status = "🟢 Monitoring" if url.monitoring else "⚪ Idle"
        last_check = f"⏱️ Last: {url.last_checked}" if url.last_checked else ""
        cols[0].markdown(f"**{url.link}** ({url.interval}s) — {status}  \n{last_check}")

        # Start button
        if cols[1].button("▶️ Start", key=f"start_{url.id}"):
            if not url.monitoring:
                url.monitoring = True
                session.commit()
            if url.id not in st.session_state["threads"]:
                t = threading.Thread(target=monitor_website, args=(url,), daemon=True)
                t.start()
                st.session_state["threads"][url.id] = t
            st.success(f"Started monitoring {url.link}")
            st.rerun()

        # Stop button
        if cols[2].button("⛔ Stop", key=f"stop_{url.id}"):
            url.monitoring = False
            session.commit()
            st.warning(f"Stopped monitoring {url.link}")
            st.rerun()

        # Delete button
        if cols[3].button("🗑 Delete", key=f"delete_{url.id}"):
            url.monitoring = False
            session.delete(url)
            session.commit()
            if url.id in st.session_state["threads"]:
                del st.session_state["threads"][url.id]
            st.warning(f"Deleted {url.link}")
            st.rerun()

session.close()

# Auto-start any URLs that were already active
active_urls = Session().query(URL).filter_by(monitoring=True).all()
for u in active_urls:
    if u.id not in st.session_state["threads"]:
        t = threading.Thread(target=monitor_website, args=(u,), daemon=True)
        t.start()
        st.session_state["threads"][u.id] = t
