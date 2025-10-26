import streamlit as st
import requests
import sqlite3
import hashlib
import difflib
import time
import os
from datetime import datetime

# ---------------------------
# CONFIG
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
            last_hash TEXT,
            last_checked TEXT
        )
    """)
    conn.commit()
    conn.close()

def get_websites():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT * FROM websites")
    data = c.fetchall()
    conn.close()
    return data

def add_website(url):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO websites (url, last_hash, last_checked) VALUES (?, ?, ?)",
              (url, "", "Never"))
    conn.commit()
    conn.close()

def update_website(url, new_hash):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE websites SET last_hash=?, last_checked=? WHERE url=?",
              (new_hash, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), url))
    conn.commit()
    conn.close()

# ---------------------------
# WEBSITE MONITORING
# ---------------------------
def get_website_hash(url):
    try:
        response = requests.get(url, timeout=10, verify=False)  # Ignore SSL issues
        response.raise_for_status()
        return hashlib.md5(response.text.encode('utf-8')).hexdigest()
    except Exception as e:
        st.error(f"❌ Error fetching {url}: {e}")
        return None

def check_for_changes():
    websites = get_websites()
    changed_sites = []
    for _, url, last_hash, _ in websites:
        current_hash = get_website_hash(url)
        if current_hash and current_hash != last_hash:
            changed_sites.append(url)
            update_website(url, current_hash)
    return changed_sites

# ---------------------------
# PING ENDPOINT
# ---------------------------
query_params = st.query_params

if "ping" in query_params:
    st.write("pong ✅")
    st.stop()  # Stops Streamlit from rendering the rest of the app

# ---------------------------
# MAIN APP
# ---------------------------
st.title("🌐 Website Change Tracker")
st.write("Monitor web pages for content updates automatically.")

# Sidebar
with st.sidebar:
    st.header("Add Website to Track")
    url = st.text_input("Enter website URL")
    if st.button("Add Website"):
        if url.strip():
            add_website(url.strip())
            st.success(f"✅ Added {url}")
            time.sleep(1)
            st.rerun()
        else:
            st.warning("Please enter a valid URL.")

    if st.button("Check Now"):
        changed = check_for_changes()
        if changed:
            st.success(f"🔔 Changes detected on: {', '.join(changed)}")
        else:
            st.info("No changes detected.")
        st.rerun()

# Display tracked websites
st.subheader("Tracked Websites")
data = get_websites()
if not data:
    st.info("No websites being tracked yet.")
else:
    for _, url, last_hash, last_checked in data:
        st.markdown(f"**🔗 {url}**")
        st.caption(f"Last checked: {last_checked}")

# ---------------------------
# INIT
# ---------------------------
if not os.path.exists(DB_FILE):
    init_db()
