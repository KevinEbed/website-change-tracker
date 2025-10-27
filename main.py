import streamlit as st
import requests
import hashlib
import time
import os
from dotenv import load_dotenv
import smtplib
from email.mime.text import MIMEText
from datetime import datetime
import json

# Load environment variables
load_dotenv()
EMAIL_SENDER = os.getenv("EMAIL_SENDER", "")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER", "")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Set up the page configuration
st.set_page_config(
    page_title="Website Change Detector", 
    layout="wide",
    page_icon="🌐"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #4CAF50;
        text-align: center;
        margin-bottom: 2rem;
    }
    .sub-header {
        font-size: 1.5rem;
        color: #2196F3;
        margin-bottom: 1rem;
    }
    .notification-card {
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 1rem 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .success {
        background-color: #E8F5E9;
        border-left: 4px solid #4CAF50;
    }
    .warning {
        background-color: #FFF3E0;
        border-left: 4px solid #FF9800;
    }
    .error {
        background-color: #FFEBEE;
        border-left: 4px solid #F44336;
    }
    .info {
        background-color: #E3F2FD;
        border-left: 4px solid #2196F3;
    }
    .footer {
        text-align: center;
        padding: 1rem;
        color: #757575;
        font-size: 0.9rem;
    }
</style>
""", unsafe_allow_html=True)

# Header section
st.markdown("<h1 class='main-header'>🌐 Website Change Detector</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; font-size: 1.2rem; color: #666;'>Monitor websites for changes and get instant notifications</p>", unsafe_allow_html=True)

# Sidebar for settings
with st.sidebar:
    st.markdown("<h2 class='sub-header'>⚙️ Settings</h2>", unsafe_allow_html=True)
    refresh_interval = st.number_input("Check every (seconds)", min_value=30, max_value=3600, value=60, step=30)
    enable_email = st.checkbox("Enable Email Notifications", value=True)
    enable_telegram = st.checkbox("Enable Telegram Notifications", value=True)
    st.markdown("---")
    st.markdown("<h3 class='sub-header'>📊 Monitoring History</h3>", unsafe_allow_html=True)
    
    # Display monitoring history if exists
    if os.path.exists("monitoring_history.json"):
        with open("monitoring_history.json", "r") as f:
            history = json.load(f)
        for item in history[-5:]:  # Show last 5 items
            st.markdown(f"<div class='notification-card info'>{item['timestamp']}<br>{item['url']}</div>", unsafe_allow_html=True)

# Main content area
url = st.text_input("🔗 Enter the URL to monitor:", value="", placeholder="https://example.com")

def send_email_notification(url):
    if not enable_email:
        return
        
    # Check if email credentials are provided
    if not EMAIL_SENDER or not EMAIL_PASSWORD or not EMAIL_RECEIVER:
        st.warning("📧 Email credentials not configured. Skipping email notification.")
        return
        
    subject = "🔔 Website Change Detected"
    body = f"The content at {url} has changed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}."
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = EMAIL_SENDER
    msg["To"] = EMAIL_RECEIVER

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.send_message(msg)
        st.success("📧 Email notification sent!")
    except Exception as e:
        st.error(f"❌ Email failed: {e}")

def send_telegram_notification(url):
    if not enable_telegram:
        return
        
    # Check if Telegram credentials are provided
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        st.warning("📩 Telegram credentials not configured. Skipping Telegram notification.")
        return
        
    message = f"🔔 Change detected at {url} at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data={"chat_id": TELEGRAM_CHAT_ID, "text": message}
        )
        if response.status_code == 200:
            st.success("📩 Telegram notification sent!")
        else:
            st.warning("⚠️ Telegram message failed to send.")
    except Exception as e:
        st.error(f"❌ Telegram error: {e}")

def save_to_history(url, timestamp):
    history_file = "monitoring_history.json"
    if os.path.exists(history_file):
        with open(history_file, "r") as f:
            history = json.load(f)
    else:
        history = []
    
    history.append({
        "url": url,
        "timestamp": timestamp,
        "hash": hashlib.md5(url.encode()).hexdigest()[:8]
    })
    
    # Keep only last 50 entries
    if len(history) > 50:
        history = history[-50:]
    
    with open(history_file, "w") as f:
        json.dump(history, f)

if url.strip() != "":
    placeholder = st.empty()
    prev_hash = None
    refresh_count = 0
    monitoring = True

    # Start monitoring button
    start_button = st.button("▶️ Start Monitoring", key="start")
    stop_button = st.button("⏹️ Stop Monitoring", key="stop")
    
    if start_button:
        monitoring = True
        st.session_state.monitoring = True
    if stop_button:
        monitoring = False
        st.session_state.monitoring = False
        
    if "monitoring" not in st.session_state:
        st.session_state.monitoring = False
        
    if st.session_state.monitoring:
        while monitoring:
            try:
                with st.spinner(f"🔍 Checking {url} for changes..."):
                    response = requests.get(url, timeout=10)
                    content = response.text
                    current_hash = hashlib.md5(content.encode()).hexdigest()

                if prev_hash is None:
                    prev_hash = current_hash
                    placeholder.markdown(f"<div class='notification-card success'>✅ Monitoring started for {url}. Waiting for changes...</div>", unsafe_allow_html=True)

                elif current_hash != prev_hash:
                    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    st.markdown(f"<div class='notification-card error'>🚨 Change Detected at {timestamp}!</div>", unsafe_allow_html=True)
                    send_email_notification(url)
                    send_telegram_notification(url)
                    save_to_history(url, timestamp)
                    prev_hash = current_hash
                else:
                    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    placeholder.markdown(f"<div class='notification-card info'>🔁 Refresh #{refresh_count + 1} at {timestamp} - No changes detected</div>", unsafe_allow_html=True)

                refresh_count += 1
                time.sleep(refresh_interval)

            except requests.exceptions.RequestException as e:
                st.markdown(f"<div class='notification-card error'>❌ Network error while checking the website: {e}</div>", unsafe_allow_html=True)
                break
            except Exception as e:
                st.markdown(f"<div class='notification-card error'>❌ Error while checking the website: {e}</div>", unsafe_allow_html=True)
                break
else:
    st.info("ℹ️ Please enter a URL above to begin monitoring.")
    
# Footer
st.markdown("<div class='footer'>Website Change Detector | Monitor your favorite websites for changes</div>", unsafe_allow_html=True)
