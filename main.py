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
    .monitoring-table {
        width: 100%;
        border-collapse: collapse;
    }
    .monitoring-table th {
        background-color: #f5f5f5;
        text-align: left;
        padding: 1rem;
    }
    .monitoring-table td {
        padding: 1rem;
        border-bottom: 1px solid #eee;
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

# Load websites on app start
load_websites()

# Handle delete confirmation
if st.session_state.delete_confirm:
    site_to_delete = st.session_state.delete_confirm
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
            if st.session_state.editing_website:
                delete = st.form_submit_button("🗑️ Delete")
        
        if submitted:
            if url.strip() != "":
                add_or_update_website(url, name if name.strip() != "" else url, interval, active)
                st.success("✅ Website saved successfully!")
                st.session_state.editing_website = None
                st.rerun()
            else:
                st.error("❌ Please enter a valid URL")
        
        if cancel:
            st.session_state.editing_website = None
            st.session_state.delete_confirm = None
            st.rerun()
        
        if st.session_state.editing_website and 'delete' in locals() and delete:
            st.session_state.delete_confirm = st.session_state.editing_website["id"]
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

# Display websites in a table
if st.session_state.websites:
    # Display table with custom styling
    st.markdown("""
    <table class="monitoring-table">
        <thead>
            <tr>
                <th>Name</th>
                <th>URL</th>
                <th>Interval</th>
                <th>Status</th>
                <th>Last Checked</th>
                <th>Actions</th>
            </tr>
        </thead>
        <tbody>
    """, unsafe_allow_html=True)
    
    for site in st.session_state.websites:
        status_class = "status-active" if site["active"] else "status-inactive"
        st.markdown(f"""
        <tr>
            <td>{site.get('name', site['url'])}</td>
            <td><span class="url-display">{site['url']}</span></td>
            <td>{site['interval']}s</td>
            <td><span class="{status_class}">{"Active" if site["active"] else "Inactive"}</span></td>
            <td>{site['last_checked'] if site['last_checked'] else 'Never'}</td>
            <td>
                <form method="post">
                    <button class="btn-edit" name="edit_site" value="{site['id']}">Edit</button>
                    <button class="btn-delete" name="delete_site" value="{site['id']}">Delete</button>
                </form>
            </td>
        </tr>
        """, unsafe_allow_html=True)
    
    st.markdown("""
        </tbody>
    </table>
    """, unsafe_allow_html=True)
    
    # Handle form submissions for edit/delete
    if "edit_site" in st.experimental_get_query_params():
        site_id = st.experimental_get_query_params()["edit_site"][0]
        edit_website(site_id)
        st.experimental_set_query_params()  # Clear query params
        st.rerun()
    
    if "delete_site" in st.experimental_get_query_params():
        site_id = st.experimental_get_query_params()["delete_site"][0]
        st.session_state.delete_confirm = site_id
        st.experimental_set_query_params()  # Clear query params
        st.rerun()
    
    # Manual check button
    if st.button("🔍 Check All Websites Now"):
        st.info("Manual check functionality would be implemented here")
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
                        placeholder.markdown(f"""
                        <div class='notification-card highlight'>
                            ✅ Monitoring started successfully!<br>
                            <span class='url-display'>{selected_site['url']}</span><br>
                            Waiting for changes...
                        </div>
                        """, unsafe_allow_html=True)

                    elif current_hash != prev_hash:
                        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        st.markdown(f"""
                        <div class='notification-card error'>
                            🚨 Change Detected at {timestamp}!<br>
                            <span class='url-display'>{selected_site['url']}</span><br>
                            Content has been modified.
                        </div>
                        """, unsafe_allow_html=True)
                        # Update website data
                        for site in st.session_state.websites:
                            if site["url"] == selected_site["url"]:
                                site["last_changed"] = timestamp
                                site["current_hash"] = current_hash
                                break
                        save_websites()
                        prev_hash = current_hash
                    else:
                        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        placeholder.markdown(f"""
                        <div class='notification-card info'>
                            🔁 Refresh #{refresh_count + 1} at {timestamp}<br>
                            <span class='url-display'>{selected_site['url']}</span><br>
                            No changes detected.
                        </div>
                        """, unsafe_allow_html=True)
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
                    st.markdown(f"""
                    <div class='notification-card error'>
                        {error_msg}<br>
                        <span class='url-display'>{selected_site['url']}</span>
                    </div>
                    """, unsafe_allow_html=True)
                    st.info("💡 Tip: Try enabling 'Skip SSL Verification' in settings if this is a known issue with the website.")
                    break
                except requests.exceptions.RequestException as e:
                    st.markdown(f"""
                    <div class='notification-card error'>
                        ❌ Network error while checking the website:<br>
                        <span class='url-display'>{selected_site['url']}</span><br>
                        Error: {e}
                    </div>
                    """, unsafe_allow_html=True)
                    break
                except Exception as e:
                    st.markdown(f"""
                    <div class='notification-card error'>
                        ❌ Error while checking the website:<br>
                        <span class='url-display'>{selected_site['url']}</span><br>
                        Error: {e}
                    </div>
                    """, unsafe_allow_html=True)
                    break
else:
    st.info("ℹ️ Add websites using the form in the sidebar to begin monitoring.")

# Footer
st.markdown("<div class='footer'>Website Change Detector | Monitor your favorite websites for changes</div>", unsafe_allow_html=True)
