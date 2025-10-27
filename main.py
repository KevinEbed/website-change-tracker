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
import urllib3
import pandas as pd

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
        padding: 1.5rem;
        border-radius: 0.75rem;
        margin: 1.5rem 0;
        box-shadow: 0 4px 8px rgba(0,0,0,0.15);
        font-weight: 500;
        font-size: 1.1rem;
        transition: all 0.3s ease;
    }
    .notification-card:hover {
        box-shadow: 0 6px 12px rgba(0,0,0,0.2);
        transform: translateY(-2px);
    }
    .success {
        background: linear-gradient(135deg, #E8F5E9, #C8E6C9);
        border-left: 6px solid #4CAF50;
        color: #2E7D32;
    }
    .warning {
        background: linear-gradient(135deg, #FFF3E0, #FFE0B2);
        border-left: 6px solid #FF9800;
        color: #EF6C00;
    }
    .error {
        background: linear-gradient(135deg, #FFEBEE, #FFCDD2);
        border-left: 6px solid #F44336;
        color: #C62828;
    }
    .info {
        background: linear-gradient(135deg, #E3F2FD, #BBDEFB);
        border-left: 6px solid #2196F3;
        color: #1565C0;
    }
    .highlight {
        background: linear-gradient(135deg, #F3E5F5, #E1BEE7);
        border-left: 6px solid #9C27B0;
        color: #6A1B9A;
        font-weight: bold;
        text-align: center;
        font-size: 1.2rem;
        padding: 2rem;
    }
    .footer {
        text-align: center;
        padding: 1.5rem;
        color: #757575;
        font-size: 0.9rem;
        margin-top: 2rem;
        border-top: 1px solid #E0E0E0;
    }
    .url-display {
        font-weight: bold;
        color: #1976D2;
        word-break: break-all;
        font-size: 1.05rem;
    }
    .status-active {
        background-color: #E8F5E9;
        color: #2E7D32;
        padding: 0.25rem 0.5rem;
        border-radius: 0.25rem;
        font-weight: bold;
    }
    .status-inactive {
        background-color: #FFEBEE;
        color: #C62828;
        padding: 0.25rem 0.5rem;
        border-radius: 0.25rem;
        font-weight: bold;
    }
    .website-info {
        padding: 0.5rem 0;
        border-bottom: 1px solid #eee;
    }
    .website-info:last-child {
        border-bottom: none;
    }
    .info-label {
        font-weight: bold;
        color: #666;
        display: inline-block;
        width: 120px;
    }
    .info-value {
        color: #333;
    }
    .website-section {
        margin-bottom: 1.5rem;
    }
    .website-header {
        font-size: 1.3rem;
        font-weight: bold;
        color: #2196F3;
        margin-bottom: 0.5rem;
    }
    .btn-delete {
        background-color: #f44336;
        color: white;
        border: none;
        padding: 0.5rem 1rem;
        border-radius: 0.25rem;
        cursor: pointer;
    }
    .btn-edit {
        background-color: #2196F3;
        color: white;
        border: none;
        padding: 0.5rem 1rem;
        border-radius: 0.25rem;
        cursor: pointer;
        margin-right: 0.5rem;
    }
    .btn-check {
        background-color: #4CAF50;
        color: white;
        border: none;
        padding: 0.5rem 1rem;
        border-radius: 0.25rem;
        cursor: pointer;
        margin-right: 0.5rem;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if "websites" not in st.session_state:
    st.session_state.websites = []

if "editing_website" not in st.session_state:
    st.session_state.editing_website = None

if "delete_confirm" not in st.session_state:
    st.session_state.delete_confirm = None

# Header section
st.markdown("<h1 class='main-header'>🌐 Website Change Detector</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; font-size: 1.2rem; color: #666;'>Monitor multiple websites for changes and get instant notifications</p>", unsafe_allow_html=True)

# Load websites from file
def load_websites():
    if os.path.exists("websites.json"):
        with open("websites.json", "r") as f:
            st.session_state.websites = json.load(f)
    else:
        st.session_state.websites = []

# Save websites to file
def save_websites():
    with open("websites.json", "w") as f:
        json.dump(st.session_state.websites, f)

# Add or update website
def add_or_update_website(url, name, interval, active):
    website_data = {
        "id": hashlib.md5(url.encode()).hexdigest()[:8],
        "url": url,
        "name": name,
        "interval": interval,
        "active": active,
        "last_checked": None,
        "last_changed": None,
        "current_hash": None
    }
    
    # Check if website already exists
    existing_index = None
    for i, site in enumerate(st.session_state.websites):
        if site["url"] == url:
            existing_index = i
            break
    
    if existing_index is not None:
        # Update existing website
        st.session_state.websites[existing_index] = website_data
    else:
        # Add new website
        st.session_state.websites.append(website_data)
    
    save_websites()

# Delete website
def delete_website(site_id):
    st.session_state.websites = [site for site in st.session_state.websites if site["id"] != site_id]
    save_websites()
    st.session_state.delete_confirm = None

# Edit website - set editing state
def edit_website(site_id):
    for site in st.session_state.websites:
        if site["id"] == site_id:
            st.session_state.editing_website = site
            break

# Delete website - set delete confirmation
def confirm_delete_website(site_id):
    st.session_state.delete_confirm = site_id

# Send email notification
def send_email_notification(url, site_name):
    if not EMAIL_SENDER or not EMAIL_PASSWORD or not EMAIL_RECEIVER:
        return False
        
    try:
        subject = "🔔 Website Change Detected"
        body = f"A change was detected on the website: {site_name}\nURL: {url}\nTime: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = EMAIL_SENDER
        msg["To"] = EMAIL_RECEIVER

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.send_message(msg)
        return True
    except Exception as e:
        print(f"Email error: {e}")
        return False

# Send Telegram notification
def send_telegram_notification(url, site_name):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return False
        
    try:
        message = f"🔔 Change detected on {site_name}\nURL: {url}\nTime: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        response = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data={"chat_id": TELEGRAM_CHAT_ID, "text": message}
        )
        return response.status_code == 200
    except Exception as e:
        print(f"Telegram error: {e}")
        return False

# Load websites on app start
load_websites()

# Handle delete confirmation
if st.session_state.delete_confirm:
    site_to_delete = st.session_state.delete_confirm
    st.warning(f"Are you sure you want to delete this website?")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ Confirm Delete"):
            delete_website(site_to_delete)
            st.success("Website deleted successfully!")
            st.rerun()
    with col2:
        if st.button("❌ Cancel"):
            st.session_state.delete_confirm = None
            st.rerun()

# Sidebar for adding/editing websites
with st.sidebar:
    st.markdown("<h2 class='sub-header'>➕ Add/Edit Website</h2>", unsafe_allow_html=True)
    
    # Form for adding/editing websites
    with st.form("website_form"):
        # Pre-fill form if editing
        if st.session_state.editing_website:
            url = st.text_input("🔗 Website URL:", value=st.session_state.editing_website["url"])
            name = st.text_input("📝 Website Name:", value=st.session_state.editing_website.get("name", ""))
            interval = st.number_input("⏱️ Check Interval (seconds):", min_value=30, max_value=3600, 
                                     value=st.session_state.editing_website["interval"], step=30)
            active = st.checkbox("✅ Active", value=st.session_state.editing_website["active"])
        else:
            url = st.text_input("🔗 Website URL:", placeholder="https://example.com")
            name = st.text_input("📝 Website Name:", placeholder="My Website")
            interval = st.number_input("⏱️ Check Interval (seconds):", min_value=30, max_value=3600, value=60, step=30)
            active = st.checkbox("✅ Active", value=True)
        
        # Buttons
        col1, col2, col3 = st.columns(3)
        with col1:
            submitted = st.form_submit_button("💾 Save Website")
        with col2:
            cancel = st.form_submit_button("❌ Cancel")
        with col3:
            delete_button = None
            if st.session_state.editing_website:
                delete_button = st.form_submit_button("🗑️ Delete")
        
        if submitted:
            if url and url.strip() != "":
                name_value = name if name and name.strip() != "" else url
                add_or_update_website(url, name_value, interval, active)
                st.success("✅ Website saved successfully!")
                st.session_state.editing_website = None
                st.rerun()
            else:
                st.error("❌ Please enter a valid URL")
        
        if cancel:
            st.session_state.editing_website = None
            st.session_state.delete_confirm = None
            st.rerun()
        
        if st.session_state.editing_website and delete_button:
            confirm_delete_website(st.session_state.editing_website["id"])
            st.rerun()
    
    st.markdown("---")
    st.markdown("<h3 class='sub-header'>⚙️ Global Settings</h3>", unsafe_allow_html=True)
    enable_email = st.checkbox("Enable Email Notifications", value=True)
    enable_telegram = st.checkbox("Enable Telegram Notifications", value=True)
    skip_ssl_verification = st.checkbox("Skip SSL Verification", value=False)
    
    st.markdown("---")
    st.markdown("<h3 class='sub-header'>📊 Monitoring History</h3>", unsafe_allow_html=True)
    
    # Display monitoring history if exists
    if os.path.exists("monitoring_history.json"):
        with open("monitoring_history.json", "r") as f:
            history = json.load(f)
        for item in history[-5:]:  # Show last 5 items
            st.markdown(f"<div class='notification-card info'>{item['timestamp']}<br>{item['url']}</div>", unsafe_allow_html=True)

# Main content area
st.markdown("<h2 class='sub-header'>📋 Monitored Websites</h2>", unsafe_allow_html=True)

# Display websites in a clean format
if st.session_state.websites:
    for i, site in enumerate(st.session_state.websites):
        # Website header with name
        st.markdown(f"<div class='website-header'>{site.get('name', site['url'])}</div>", unsafe_allow_html=True)
        
        # Website details
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown(f"<div class='website-info'><span class='info-label'>URL:</span> <span class='info-value'>{site['url']}</span></div>", unsafe_allow_html=True)
            st.markdown(f"<div class='website-info'><span class='info-label'>Interval:</span> <span class='info-value'>{site['interval']} seconds</span></div>", unsafe_allow_html=True)
            st.markdown(f"<div class='website-info'><span class='info-label'>Status:</span> <span class='info-value'>{'Active' if site['active'] else 'Inactive'}</span></div>", unsafe_allow_html=True)
            st.markdown(f"<div class='website-info'><span class='info-label'>Last Checked:</span> <span class='info-value'>{site['last_checked'] if site['last_checked'] else 'Never'}</span></div>", unsafe_allow_html=True)
        with col2:
            if st.button("✏️ Edit", key=f"edit_{site['id']}"):
                edit_website(site["id"])
                st.rerun()
            if st.button("🗑️ Delete", key=f"delete_{site['id']}"):
                confirm_delete_website(site["id"])
                st.rerun()
        
        # Add separator except for the last item
        if i < len(st.session_state.websites) - 1:
            st.markdown("---")
    
    # Manual check button
    if st.button("🔍 Check All Websites Now"):
        st.info("Checking all websites for changes...")
        changes_detected = []
        
        for site in st.session_state.websites:
            try:
                # Configure request based on SSL setting
                if skip_ssl_verification:
                    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                    response = requests.get(site["url"], timeout=10, verify=False)
                else:
                    response = requests.get(site["url"], timeout=10)
                
                content = response.text
                current_hash = hashlib.md5(content.encode()).hexdigest()
                
                # Update last checked time
                site["last_checked"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                if site.get("current_hash") is None:
                    site["current_hash"] = current_hash
                elif current_hash != site["current_hash"]:
                    # Change detected
                    site["last_changed"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    site["current_hash"] = current_hash
                    changes_detected.append(site)
                    
                    # Send notifications
                    site_name = site.get('name', site['url'])
                    if enable_email:
                        send_email_notification(site["url"], site_name)
                    if enable_telegram:
                        send_telegram_notification(site["url"], site_name)
                        
            except Exception as e:
                print(f"Error checking {site['url']}: {e}")
        
        save_websites()
        
        if changes_detected:
            st.success(f"Changes detected on {len(changes_detected)} website(s). Notifications sent.")
        else:
            st.info("No changes detected on any websites.")
else:
    st.info("ℹ️ No websites are currently being monitored. Add a website using the form in the sidebar.")

# Individual website monitoring section
st.markdown("---")
st.markdown("<h2 class='sub-header'>🎯 Monitor Specific Website</h2>", unsafe_allow_html=True)

# Select website to monitor
if st.session_state.websites:
    website_options = {site.get("name", site["url"]): site for site in st.session_state.websites}
    selected_name = st.selectbox("Select a website to monitor:", list(website_options.keys()))
    selected_site = website_options[selected_name]
    
    if selected_site:
        placeholder = st.empty()
        prev_hash = selected_site.get("current_hash", None)
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
                    with st.spinner(f"🔍 Checking {selected_site['url']} for changes..."):
                        # Configure request based on SSL setting
                        if skip_ssl_verification:
                            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                            response = requests.get(selected_site["url"], timeout=10, verify=False)
                        else:
                            response = requests.get(selected_site["url"], timeout=10)
                        
                        content = response.text
                        current_hash = hashlib.md5(content.encode()).hexdigest()

                    if prev_hash is None:
                        prev_hash = current_hash
                        # Update website data
                        for site in st.session_state.websites:
                            if site["url"] == selected_site["url"]:
                                site["last_checked"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                break
                        save_websites()

                    elif current_hash != prev_hash:
                        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        # Send notifications only
                        site_name = selected_site.get('name', selected_site['url'])
                        if enable_email:
                            email_sent = send_email_notification(selected_site["url"], site_name)
                        if enable_telegram:
                            telegram_sent = send_telegram_notification(selected_site["url"], site_name)
                        
                        # Update website data
                        for site in st.session_state.websites:
                            if site["url"] == selected_site["url"]:
                                site["last_changed"] = timestamp
                                site["current_hash"] = current_hash
                                site["last_checked"] = timestamp
                                break
                        save_websites()
                        prev_hash = current_hash
                    else:
                        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        # Update website data
                        for site in st.session_state.websites:
                            if site["url"] == selected_site["url"]:
                                site["last_checked"] = timestamp
                                break
                        save_websites()

                    refresh_count += 1
                    time.sleep(selected_site["interval"])

                except requests.exceptions.SSLError as e:
                    error_msg = f"🔒 SSL Certificate Error: {str(e)}"
                    print(f"SSL Error for {selected_site['url']}: {error_msg}")
                    break
                except requests.exceptions.RequestException as e:
                    print(f"Network error for {selected_site['url']}: {e}")
                    break
                except Exception as e:
                    print(f"Error checking {selected_site['url']}: {e}")
                    break
else:
    st.info("ℹ️ Add websites using the form in the sidebar to begin monitoring.")

# Footer
st.markdown("<div class='footer'>Website Change Detector | Monitor your favorite websites for changes</div>", unsafe_allow_html=True)
