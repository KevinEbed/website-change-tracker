import streamlit as st
import requests
import sqlite3
import hashlib
import time
import os
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
    """Create the SQLite database and table if not already existing."""
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

# ✅ Initialize database immediately
init_db()

def get_websites():
    """Fetch all tracked websites from the database."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT * FROM websites")
    data = c.fetchall()
    conn.close()
    return data

def add_website(url):
    """Add a new website to track."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO websites (url, last_hash, last_checked) VALUES (?, ?, ?)",
              (url, "", "Never"))
    conn.commit()
    conn.close()

def update_website(url, new_hash):
    """Update website hash and timestamp."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE websites SET last_hash=?, last_checked=? WHERE url=?",
              (new_hash, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), url))
    conn.commit()
    conn.close()

def delete_website(url):
    """Remove a website from tracking."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM websites WHERE url=?", (url,))
    conn.commit()
    conn.close()

# ---------------------------
# WEBSITE CHECKING
# ---------------------------
def get_website_hash(url):
    """Fetch website content and generate a hash."""
    try:
        response = requests.get(url, timeout=10, verify=False)  # Skip SSL verification
        response.raise_for_status()
        return hashlib.md5(response.text.encode('utf-8')).hexdigest()
    except Exception as e:
        st.error(f"❌ Error fetching {url}: {e}")
        return None

def check_for_changes():
    """Compare stored hash with current one and return changed sites."""
    websites = get_websites()
    changed_sites = []
    for _, url, last_hash, _ in websites:
        current_hash = get_website_hash(url)
        if not current_hash:
            continue
        if current_hash != last_hash:
            changed_sites.append(url)
            update_website(url, current_hash)
    return changed_sites

# ---------------------------
# PING ENDPOINT (for uptime checks)
# ---------------------------
query_params = st.query_params
if "ping" in query_params:
    st.write("✅ Pong! The app is alive.")
    st.stop()

# ---------------------------
# MAIN UI
# ---------------------------
st.title("🌐 Website Change Tracker")
st.write("Monitor websites for any content changes and get notified instantly.")

# Sidebar actions
with st.sidebar:
    st.header("⚙️ Controls")

    url = st.text_input("Enter website URL")
    if st.button("➕ Add Website"):
        if url.strip():
            add_website(url.strip())
            st.success(f"✅ Added {url}")
            time.sleep(1)
            st.rerun()
        else:
            st.warning("Please enter a valid URL before adding.")

    if st.button("🔁 Check for Changes"):
        changed = check_for_changes()
        if changed:
            st.success(f"🔔 Change detected on:\n" + "\n".join(changed))
        else:
            st.info("No changes detected.")
        time.sleep(2)
        st.rerun()

# Display all tracked websites
st.subheader("📋 Tracked Websites")
websites = get_websites()

if not websites:
    st.info("No websites are being tracked yet. Add one from the sidebar.")
else:
    for _, url, last_hash, last_checked in websites:
        cols = st.columns([5, 2])
        with cols[0]:
            st.markdown(f"**🔗 {url}**")
            st.caption(f"Last checked: {last_checked}")
        with cols[1]:
            if st.button("🗑 Delete", key=url):
                delete_website(url)
                st.warning(f"Deleted {url}")
                time.sleep(1)
                st.rerun()

# Footer
st.markdown("---")
st.caption("🧠 Built with ❤️ using Streamlit and SQLite — simple, safe, and serverless.")
