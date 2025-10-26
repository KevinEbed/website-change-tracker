import streamlit as st
import requests
import hashlib
import os
import json
import tempfile
import threading
import time
from datetime import datetime
from email.mime.text import MIMEText
import smtplib
from dotenv import load_dotenv
from pathlib import Path

# ---------------- Setup & config ----------------
load_dotenv()

EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Use system tempdir so Streamlit Cloud is happy
DB_FILENAME = "website_monitor_store.json"
DB_PATH = os.path.join(tempfile.gettempdir(), DB_FILENAME)

# In-memory thread registry and lock for JSON store access
_store_lock = threading.Lock()
_threads = {}  # mapping id -> Thread
_threads_lock = threading.Lock()

# Defaults
DEFAULT_INTERVAL = 60  # seconds
HTTP_TIMEOUT = 10  # seconds
REQUEST_HEADERS = {"User-Agent": "WebsiteChangeMonitor/1.0 (+https://example.com)"}


# ---------------- Persistence helpers ----------------
def _atomic_write(path: str, data: str):
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def load_store():
    """Return dict of {id: item}"""
    with _store_lock:
        if not os.path.exists(DB_PATH):
            return {}
        try:
            with open(DB_PATH, "r", encoding="utf-8") as f:
                raw = json.load(f)
            # Ensure key types are ints (store keys as strings in JSON)
            return {int(k): v for k, v in raw.items()}
        except Exception as e:
            print(f"[WARN] Failed to read store: {e}")
            return {}


def save_store(store: dict):
    """Persist store atomically. store keys should be ints."""
    with _store_lock:
        try:
            serializable = {str(k): v for k, v in store.items()}
            _atomic_write(DB_PATH, json.dumps(serializable, indent=2, ensure_ascii=False))
        except Exception as e:
            print(f"[ERROR] Failed to write store: {e}")


def next_id(store: dict):
    if not store:
        return 1
    return max(store.keys()) + 1


# ---------------- Notification helpers ----------------
def send_email(subject: str, body: str):
    if not (EMAIL_SENDER and EMAIL_PASSWORD and EMAIL_RECEIVER):
        print("[INFO] Email not configured — skipping.")
        return
    try:
        msg = MIMEText(body)
        msg["From"] = EMAIL_SENDER
        msg["To"] = EMAIL_RECEIVER
        msg["Subject"] = subject
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.send_message(msg)
        print("[INFO] Email sent.")
    except Exception as e:
        print(f"[ERROR] Email send failed: {e}")


def send_telegram(message: str):
    if not (TELEGRAM_TOKEN and TELEGRAM_CHAT_ID):
        print("[INFO] Telegram not configured — skipping.")
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": message}, timeout=HTTP_TIMEOUT)
        print("[INFO] Telegram sent.")
    except Exception as e:
        print(f"[ERROR] Telegram send failed: {e}")


# ---------------- Monitoring worker ----------------
def _fetch_content_hash(url: str) -> (str, str):
    """
    Returns (hash, text-snippet) or (None, error-message) on failure.
    Only a short snippet is returned for logs to avoid massive storage.
    """
    try:
        r = requests.get(url, headers=REQUEST_HEADERS, timeout=HTTP_TIMEOUT, allow_redirects=True)
        r.raise_for_status()
        content = r.content
        h = hashlib.md5(content).hexdigest()
        snippet = r.text[:800] if r.encoding or len(r.text) else ""
        return h, snippet
    except Exception as exc:
        return None, f"fetch-error: {exc}"


def monitor_loop(item_id: int):
    """
    Runs in its own thread. Reads the store to check whether it should stop.
    Updates last_hash / last_checked / logs in the store.
    """
    print(f"[THREAD] Starting monitor for id={item_id}")
    # Initial load of store and initial hash
    store = load_store()
    item = store.get(item_id)
    if not item:
        print(f"[THREAD] Item {item_id} missing — exiting")
        return

    url = item["url"]
    interval = int(item.get("interval", DEFAULT_INTERVAL)) or DEFAULT_INTERVAL

    # Get initial hash (if none stored yet)
    h, info = _fetch_content_hash(url)
    if h is None:
        # initial fetch failed; record an error and continue loop (so we can retry)
        with _store_lock:
            store = load_store()
            it = store.get(item_id)
            if not it:
                return
            it.setdefault("logs", []).insert(0, {"time": datetime.utcnow().isoformat(), "msg": f"initial fetch failed: {info}"})
            it["last_checked"] = datetime.utcnow().isoformat()
            save_store(store)
        # We'll set old_hash to None and continue to retry
        old_hash = None
    else:
        old_hash = h
        with _store_lock:
            store = load_store()
            it = store.get(item_id)
            if not it:
                return
            it["last_hash"] = old_hash
            it["last_checked"] = datetime.utcnow().isoformat()
            it.setdefault("logs", []).insert(0, {"time": datetime.utcnow().isoformat(), "msg": "initial fetch OK"})
            save_store(store)

    while True:
        # Respect any updates to interval or stop flag by reading store
        time.sleep(interval)
        store = load_store()
        item = store.get(item_id)
        if not item:
            print(f"[THREAD] Item {item_id} deleted — stopping thread.")
            break
        if not item.get("monitoring", False):
            print(f"[THREAD] Item {item_id} set to stop monitoring.")
            break

        # Allow interval update mid-run
        interval = int(item.get("interval", interval)) or DEFAULT_INTERVAL

        h, info = _fetch_content_hash(url)
        now = datetime.utcnow().isoformat()
        if h is None:
            # fetch error — log and continue
            with _store_lock:
                store = load_store()
                it = store.get(item_id)
                if not it:
                    break
                it.setdefault("logs", []).insert(0, {"time": now, "msg": f"fetch failed: {info}"})
                it["last_checked"] = now
                save_store(store)
            continue

        if old_hash is None:
            old_hash = h
            with _store_lock:
                store = load_store()
                it = store.get(item_id)
                if not it:
                    break
                it["last_hash"] = h
                it["last_checked"] = now
                it.setdefault("logs", []).insert(0, {"time": now, "msg": "set initial hash after earlier fail"})
                save_store(store)
            continue

        if h != old_hash:
            # Change detected
            msg = f"Change detected for {url} at {now}"
            print(f"[ALERT] {msg}")
            # Update store: last_hash, last_checked, logs
            with _store_lock:
                store = load_store()
                it = store.get(item_id)
                if not it:
                    break
                it["last_hash"] = h
                it["last_checked"] = now
                it.setdefault("logs", []).insert(0, {"time": now, "msg": "change detected"})
                save_store(store)

            # Send notifications
            friendly = f"🔔 {msg}"
            send_telegram(friendly)
            send_email("Website Change Detected", friendly)
            # update old_hash
            old_hash = h
        else:
            # No change, update last_checked and a debug log occasionally
            with _store_lock:
                store = load_store()
                it = store.get(item_id)
                if not it:
                    break
                it["last_checked"] = now
                # Keep logs bounded: store only last 50 entries
                logs = it.setdefault("logs", [])
                if not logs or (len(logs) and ("checked" not in logs[0].get("msg", ""))):
                    logs.insert(0, {"time": now, "msg": "checked — no change"})
                it["logs"] = logs[:50]
                save_store(store)
            print(f"[DEBUG] No change for {url} at {now}")

    # Thread ending cleanup
    with _threads_lock:
        _threads.pop(item_id, None)
    print(f"[THREAD] Monitor for id={item_id} stopped.")


# ---------------- Streamlit UI ----------------
def serve_ping():
    st.set_page_config(page_title="Ping")
    st.write("✅ Pong! The app is alive.")
    st.stop()


if st.query_params.get("ping") == ["1"] or st.query_params.get("ping") == "1":
    serve_ping()

st.set_page_config(page_title="Website Change Monitor", layout="centered")
st.title("🔍 Website Change Monitor (JSON-backed)")

# Load current store
store = load_store()

# Add new URL form
with st.form("add_url_form"):
    link = st.text_input("Enter URL")
    interval = st.number_input("Check every (seconds)", min_value=10, value=DEFAULT_INTERVAL)
    submitted = st.form_submit_button("➕ Add URL")
    if submitted:
        if not link:
            st.error("Please enter a URL.")
        else:
            # Avoid duplicates by exact match
            if any(item.get("url") == link for item in store.values()):
                st.warning("That URL is already being tracked.")
            else:
                new_id = next_id(store)
                store[new_id] = {
                    "url": link,
                    "monitoring": False,
                    "interval": int(interval),
                    "last_hash": None,
                    "last_checked": None,
                    "logs": [{"time": datetime.utcnow().isoformat(), "msg": "added"}],
                }
                save_store(store)
                st.success(f"Added {link} (id={new_id}). Click ▶️ Start to begin monitoring.")
                st.experimental_rerun()

# Refresh store to get most recent data (in case threads updated it)
store = load_store()
if not store:
    st.info("No URLs tracked yet. Add one above.")
else:
    st.subheader("Tracked URLs")

    for item_id, item in sorted(store.items()):
        cols = st.columns([4, 1, 1, 1, 2])
        status = "🟢 Monitoring" if item.get("monitoring") else "⚪ Idle"
        url_md = f"**{item.get('url')}** — {status}\n\n- Interval: {item.get('interval', DEFAULT_INTERVAL)}s\n- Last checked: {item.get('last_checked') or 'never'}"
        cols[0].markdown(url_md)

        # Start button
        if cols[1].button("▶️ Start", key=f"start_{item_id}"):
            # Update store to set monitoring True
            store = load_store()
            it = store.get(item_id)
            if it and not it.get("monitoring"):
                it["monitoring"] = True
                it.setdefault("logs", []).insert(0, {"time": datetime.utcnow().isoformat(), "msg": "monitoring started"})
                save_store(store)

                # Start thread if not already running
                with _threads_lock:
                    if item_id not in _threads:
                        t = threading.Thread(target=monitor_loop, args=(item_id,), daemon=True)
                        _threads[item_id] = t
                        t.start()
                st.success(f"Started monitoring {it.get('url')}")
                st.experimental_rerun()

        # Stop button
        if cols[2].button("⛔ Stop", key=f"stop_{item_id}"):
            store = load_store()
            it = store.get(item_id)
            if it and it.get("monitoring"):
                it["monitoring"] = False
                it.setdefault("logs", []).insert(0, {"time": datetime.utcnow().isoformat(), "msg": "monitoring stopped by user"})
                save_store(store)
                st.info(f"Stopped monitoring {it.get('url')}")
                st.experimental_rerun()

        # Delete button
        if cols[3].button("🗑 Delete", key=f"delete_{item_id}"):
            store = load_store()
            if item_id in store:
                # mark monitoring false first (threads should see this and exit)
                store[item_id]["monitoring"] = False
                store[item_id].setdefault("logs", []).insert(0, {"time": datetime.utcnow().isoformat(), "msg": "deleted by user"})
                # remove entry
                del store[item_id]
                save_store(store)
                st.warning(f"Deleted {item.get('url')}")
                st.experimental_rerun()

        # Expandable logs & controls
        with cols[4]:
            with st.expander("Logs & Settings", expanded=False):
                st.write("Logs (most recent first):")
                logs = item.get("logs", [])[:50]
                for log in logs:
                    t = log.get("time")
                    m = log.get("msg")
                    st.write(f"- {t} — {m}")
                # Interval update
                new_interval = st.number_input(f"Interval (s) for id={item_id}", min_value=10, value=int(item.get("interval", DEFAULT_INTERVAL)), key=f"int_{item_id}")
                if st.button("Update interval", key=f"update_{item_id}"):
                    store = load_store()
                    it = store.get(item_id)
                    if it:
                        it["interval"] = int(new_interval)
                        it.setdefault("logs", []).insert(0, {"time": datetime.utcnow().isoformat(), "msg": f"interval updated to {new_interval}s"})
                        save_store(store)
                        st.success("Interval updated.")
                        st.experimental_rerun()

# Option to start any monitors that were left running across restarts
if st.button("Restart all monitors that were running", key="restart_all"):
    store = load_store()
    started = 0
    for item_id, item in store.items():
        if item.get("monitoring"):
            with _threads_lock:
                if item_id not in _threads:
                    t = threading.Thread(target=monitor_loop, args=(item_id,), daemon=True)
                    _threads[item_id] = t
                    t.start()
                    started += 1
    st.success(f"Restarted {started} monitor(s).")

st.markdown("---")
st.caption(f"Store path: `{DB_PATH}` — This file is used for persistence and is safe to keep in tempdir.")
