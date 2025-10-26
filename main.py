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
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime
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
# If you deploy on Streamlit Cloud and see sqlite errors, consider using tempfile.gettempdir() path.
engine = create_engine("sqlite:///urls.db", connect_args={"check_same_thread": False})
Session = sessionmaker(bind=engine)
db_session = Session()

class URL(Base):
    __tablename__ = "urls"
    id = Column(Integer, primary_key=True)
    link = Column(String(500), nullable=False)
    monitoring = Column(Boolean, default=False)
    interval = Column(Integer, default=60)
    last_checked = Column(DateTime, nullable=True)

Base.metadata.create_all(engine)

# ---------------- Global data ----------------
monitoring_threads = {}

# ---------------- Notification functions ----------------
def send_email(subject, body):
    if not (EMAIL_SENDER and EMAIL_PASSWORD and EMAIL_RECEIVER):
        print("[WARN] Missing email credentials; skipping email.")
        return
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
    if not (TELEGRAM_TOKEN and TELEGRAM_CHAT_ID):
        print("[WARN] Missing Telegram credentials; skipping telegram.")
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
        requests.post(url, data=payload, timeout=10)
        print("[INFO] Telegram message sent.")
    except Exception as e:
        print(f"[ERROR] Failed to send Telegram message: {e}")

# ---------------- Monitoring function ----------------
def monitor_website(url, url_id, interval):
    """Background thread: monitor a single URL, update last_checked in DB."""
    print(f"👀 Monitoring {url} (every {interval}s)")
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        old_hash = hashlib.md5(r.content).hexdigest()
    except Exception as e:
        print(f"[ERROR] Initial fetch failed for {url}: {e}")
        return

    # Use a separate Session inside thread
    thread_session = Session()
    try:
        # Initialize last_checked for this run
        obj = thread_session.query(URL).get(url_id)
        if obj:
            obj.last_checked = datetime.utcnow()
            thread_session.commit()
    except Exception:
        pass

    while True:
        # Re-query to see whether monitoring is still on
        obj = thread_session.query(URL).get(url_id)
        if not obj or not obj.monitoring:
            print(f"[INFO] Monitoring stopped for {url}")
            break

        try:
            time.sleep(interval)
            r = requests.get(url, timeout=15)
            r.raise_for_status()
            current_hash = hashlib.md5(r.content).hexdigest()

            # Update last_checked timestamp in DB
            obj.last_checked = datetime.utcnow()
            thread_session.commit()

            if current_hash != old_hash:
                print(f"[CHANGE] {url} changed at {datetime.utcnow().isoformat()}")
                message = f"🔔 Change detected on: {url}\nTime (UTC): {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}"
                send_email("Website Content Changed", message)
                send_telegram(message)
                old_hash = current_hash
            else:
                print(f"[DEBUG] No change for {url} at {datetime.utcnow().isoformat()}")

        except Exception as e:
            print(f"[ERROR] During monitoring of {url}: {e}")

    thread_session.close()

# ---------------- Streamlit App ----------------
st.set_page_config(page_title="Website Change Monitor", layout="centered")

# --- PING/PONG handler ---
params = st.query_params
if "ping" in params and params["ping"] == ["1"]:
    st.write("pong")
    st.stop()

# Small HTML meta refresh so the page updates automatically every 30 seconds.
# This avoids relying on experimental Streamlit APIs.
st.markdown('<meta http-equiv="refresh" content="30">', unsafe_allow_html=True)

st.title("🔍 Website Change Monitor")
st.write("Add URLs, start monitoring — Last-checked timestamps update automatically every 30s.")

# ---------------- Auto-resume monitoring on app restart ----------------
# Start background threads for any URLs that have monitoring=True
for url_obj in db_session.query(URL).filter_by(monitoring=True).all():
    if url_obj.id not in monitoring_threads:
        t = threading.Thread(target=monitor_website, args=(url_obj.link, url_obj.id, url_obj.interval), daemon=True)
        t.start()
        monitoring_threads[url_obj.id] = t
        print(f"[AUTO] Resumed monitoring for {url_obj.link}")

# ---------------- Add URL Form ----------------
with st.form("add_url_form"):
    link = st.text_input("Enter URL")
    interval = st.number_input("Check every (seconds)", min_value=10, value=60)
    submitted = st.form_submit_button("➕ Add URL")
    if submitted and link:
        new_url = URL(link=link, interval=interval, monitoring=False)
        db_session.add(new_url)
        db_session.commit()
        st.success(f"Added {link} with interval {interval}s")
        # Do not auto-start; user can click Start to begin monitoring
        st.rerun()

# ---------------- Display URLs ----------------
urls = db_session.query(URL).all()
st.subheader("Tracked URLs")

for url in urls:
    cols = st.columns([4, 2, 1, 1, 1])
    last_checked = url.last_checked.strftime("%Y-%m-%d %H:%M:%S UTC") if url.last_checked else "Never"
    status = "🟢 Monitoring" if url.monitoring else "⚪ Idle"
    cols[0].markdown(f"**{url.link}** ({url.interval}s) — {status}")
    cols[1].write(f"🕒 Last checked: {last_checked}")

    if cols[2].button("▶️ Start", key=f"start_{url.id}"):
        if not url.monitoring:
            url.monitoring = True
            db_session.commit()
        if url.id not in monitoring_threads:
            t = threading.Thread(target=monitor_website, args=(url.link, url.id, url.interval), daemon=True)
            t.start()
            monitoring_threads[url.id] = t
        st.success(f"Started monitoring {url.link}")
        st.rerun()

    if cols[3].button("⛔ Stop", key=f"stop_{url.id}"):
        url.monitoring = False
        db_session.commit()
        st.info(f"Stopped monitoring {url.link}")
        st.rerun()

    if cols[4].button("🗑 Delete", key=f"delete_{url.id}"):
        url.monitoring = False
        # stop thread by removing monitoring flag; thread will exit on next loop
        db_session.delete(url)
        db_session.commit()
        if url.id in monitoring_threads:
            monitoring_threads.pop(url.id, None)
        st.warning(f"Deleted {url.link}")
        st.rerun()
