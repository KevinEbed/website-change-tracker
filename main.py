import streamlit as st
import requests
import sqlite3
import hashlib
import threading
import time
from datetime import datetime

# ---------------------------
# CONFIGURATION
# ---------------------------
st.set_page_config(page_title="Website Change Tracker", layout="wide")
DB_FILE = "tracker.db"

# ---------------------------
# DATABASE SETUP
# ---------------------------
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS websites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT UNIQUE,
            interval INTEGER DEFAULT 60,
            monitoring INTEGER DEFAULT 0,
            last_hash TEXT,
            last_checked TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

# ---------------------------
# DATABASE HELPERS
# ---------------------------
def get_websites():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT * FROM websites")
    data = c.fetchall()
    conn.close()
    return data

def add_website(url, interval):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO websites (url, interval, monitoring, last_hash, last_checked) VALUES (?, ?, 0, '', 'Never')",
              (url, interval))
    conn.commit()
    conn.close()

def update_monitoring(url, status):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE websites SET monitoring=? WHERE url=?", (status, url))
    conn.commit()
    conn.close()

def update_website(url, new_hash):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE websites SET last_hash=?, last_checked=? WHERE url=?",
              (new_hash, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), url))
    conn.commit()
    conn.close()

def delete_website(url):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM websites WHERE url=?", (url,))
    conn.commit()
    conn.close()

# ---------------------------
# WEBSITE MONITORING
# ---------------------------
def get_website_hash(url):
    try:
        response = requests.get(url, timeout=10, verify=False)
        response.raise_for_status()
        return hashlib.md5(response.text.encode('utf-8')).hexdigest()
    except Exception as e:
        print(f"[ERROR] Failed to fetch {url}: {e}")
        return None

def monitor_website(url, interval):
    print(f"🔍 Started monitoring {url} every {interval}s")
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT last_hash FROM websites WHERE url=?", (url,))
    old_hash = c.fetchone()[0]
    conn.close()

    while True:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT monitoring FROM websites WHERE url=?", (url,))
        monitoring = c.fetchone()[0]
        conn.close()

        if not monitoring:
            print(f"⏹️ Stopped monitoring {url}")
            break

        current_hash = get_website_hash(url)
        if current_hash and current_hash != old_hash:
            print(f"⚡ Change detected on {url} at {datetime.now()}")
            update_website(url, current_hash)
            old_hash = current_hash

        time.sleep(interval)

# ---------------------------
# PING ENDPOINT
# ---------------------------
params = st.query_params
if "ping" in params:
    st.write("✅ Pong! The app is alive.")
    st.stop()

# ---------------------------
# MAIN UI
# ---------------------------
st.title("🌐 Website Change Tracker")
st.write("Automatically monitor websites for any content changes.")

# Add new website
with st.form("add_site_form"):
    new_url = st.text_input("Enter website URL")
    new_interval = st.number_input("Check interval (seconds)", min_value=10, value=60)
    add_btn = st.form_submit_button("➕ Add Website")

    if add_btn and new_url.strip():
        add_website(new_url.strip(), new_interval)
        st.success(f"✅ Added {new_url}")
        time.sleep(1)
        st.rerun()

# Display tracked sites
st.subheader("📋 Tracked Websites")
sites = get_websites()

if not sites:
    st.info("No websites are being tracked yet.")
else:
    for site in sites:
        site_id, url, interval, monitoring, last_hash, last_checked = site
        cols = st.columns([4, 2, 1, 1, 1])
        with cols[0]:
            st.markdown(f"**{url}**")
            st.caption(f"Last checked: {last_checked}")
        with cols[1]:
            st.write(f"⏱️ {interval}s")
        with cols[2]:
            if not monitoring:
                if st.button("▶️ Start", key=f"start_{url}"):
                    update_monitoring(url, 1)
                    threading.Thread(target=monitor_website, args=(url, interval), daemon=True).start()
                    st.success(f"Started monitoring {url}")
                    time.sleep(1)
                    st.rerun()
            else:
                if st.button("⏹ Stop", key=f"stop_{url}"):
                    update_monitoring(url, 0)
                    st.info(f"Stopped monitoring {url}")
                    time.sleep(1)
                    st.rerun()
        with cols[3]:
            if st.button("🗑 Delete", key=f"del_{url}"):
                update_monitoring(url, 0)
                delete_website(url)
                st.warning(f"Deleted {url}")
                time.sleep(1)
                st.rerun()

# Footer
st.markdown("---")
st.caption("🧠 Built with ❤️ using Streamlit, SQLite & background threads.")
