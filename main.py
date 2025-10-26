import streamlit as st
import sqlite3
import requests
import hashlib
import time
import threading
from datetime import datetime

# =========================================================
# ✅ CONFIGURATION
# =========================================================
DB_PATH = "websites.db"
CHECK_INTERVAL = 5  # seconds between monitoring cycles (global)

# =========================================================
# ✅ DATABASE FUNCTIONS
# =========================================================
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS websites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT,
            interval INTEGER,
            monitoring INTEGER,
            last_hash TEXT,
            last_checked TEXT
        )
    """)
    conn.commit()
    conn.close()

def get_websites():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM websites")
    rows = c.fetchall()
    conn.close()
    return rows

def add_website(url, interval):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO websites (url, interval, monitoring, last_hash, last_checked) VALUES (?, ?, 1, '', '')",
              (url, interval))
    conn.commit()
    conn.close()

def update_website(site_id, new_hash):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "UPDATE websites SET last_hash=?, last_checked=? WHERE id=?",
        (new_hash, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), site_id)
    )
    conn.commit()
    conn.close()

def toggle_monitoring(site_id, status):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE websites SET monitoring=? WHERE id=?", (1 if status else 0, site_id))
    conn.commit()
    conn.close()

# =========================================================
# ✅ WEB SCRAPING AND HASHING
# =========================================================
def get_hash(url):
    try:
        r = requests.get(url, timeout=15, verify=True)
        return hashlib.md5(r.text.encode("utf-8")).hexdigest()
    except Exception as e:
        print(f"[ERROR] Failed to fetch {url}: {e}")
        return None

# =========================================================
# ✅ MONITORING LOOP
# =========================================================
def monitor_loop():
    while st.session_state.get("monitoring_active", False):
        sites = get_websites()
        for site in sites:
            site_id, url, interval, monitoring, last_hash, last_checked = site
            if monitoring:
                new_hash = get_hash(url)
                if new_hash:
                    if last_hash and new_hash != last_hash:
                        st.session_state["logs"].append(
                            f"🔄 Change detected on {url} at {datetime.now().strftime('%H:%M:%S')}"
                        )
                    update_website(site_id, new_hash)
                time.sleep(interval)
        time.sleep(CHECK_INTERVAL)

# =========================================================
# ✅ STREAMLIT UI
# =========================================================
st.set_page_config(page_title="Website Change Tracker", page_icon="🌐", layout="centered")
st.title("🌐 Website Change Tracker")
st.write("Monitor any webpage for content changes automatically.")

init_db()

# Session state setup
if "logs" not in st.session_state:
    st.session_state["logs"] = []
if "monitoring_active" not in st.session_state:
    st.session_state["monitoring_active"] = False
if "thread_running" not in st.session_state:
    st.session_state["thread_running"] = False

# ---------------------------------------------------------
# Add website
st.subheader("➕ Add a Website to Monitor")
url = st.text_input("Enter website URL")
interval = st.number_input("Check interval (seconds)", 10, 3600, 60)
if st.button("Add Website"):
    if url:
        add_website(url, interval)
        st.success(f"✅ Added {url} (every {interval}s)")
    else:
        st.error("⚠️ Please enter a valid URL.")

# ---------------------------------------------------------
# Start / Stop monitoring buttons
st.subheader("🧠 Monitoring Controls")
col1, col2 = st.columns(2)

with col1:
    if st.button("▶️ Start Monitoring"):
        if not st.session_state["monitoring_active"]:
            st.session_state["monitoring_active"] = True
            if not st.session_state["thread_running"]:
                threading.Thread(target=monitor_loop, daemon=True).start()
                st.session_state["thread_running"] = True
            st.success("Monitoring started ✅")

with col2:
    if st.button("⏹️ Stop Monitoring"):
        st.session_state["monitoring_active"] = False
        st.warning("Monitoring stopped ⏸️")

# ---------------------------------------------------------
# Display monitored sites
st.subheader("📋 Tracked Websites")
sites = get_websites()
if sites:
    for site in sites:
        site_id, url, interval, monitoring, last_hash, last_checked = site
        st.write(
            f"🌍 {url} | Every {interval}s | {'🟢 Active' if monitoring else '🔴 Paused'}"
        )
        colA, colB = st.columns(2)
        with colA:
            if st.button(f"Pause {site_id}", key=f"pause_{site_id}"):
                toggle_monitoring(site_id, False)
                st.experimental_rerun()
        with colB:
            if st.button(f"Resume {site_id}", key=f"resume_{site_id}"):
                toggle_monitoring(site_id, True)
                st.experimental_rerun()
else:
    st.info("No websites being monitored yet. Add one above to get started!")

# ---------------------------------------------------------
# Logs
st.subheader("📜 Activity Log")
if st.session_state["logs"]:
    for log in st.session_state["logs"][-10:][::-1]:
        st.write(log)
else:
    st.write("🕓 Waiting for updates...")

# =========================================================
# ✅ AUTO-START MONITORING ON LAUNCH
# =========================================================
if not st.session_state["thread_running"]:
    st.session_state["monitoring_active"] = True
    threading.Thread(target=monitor_loop, daemon=True).start()
    st.session_state["thread_running"] = True
