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
from bs4 import BeautifulSoup
import re

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
def add_or_update_website(url, name, interval, active, monitor_type="any_change"):
    website_data = {
        "id": hashlib.md5(url.encode()).hexdigest()[:8],
        "url": url,
        "name": name,
        "interval": interval,
        "active": active,
        "monitor_type": monitor_type,  # "any_change" or "stwdo_rooms"
        "last_checked": None,
        "last_changed": None,
        "current_hash": None,
        "previous_rooms": [],
        "first_scan_completed": False
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
def send_email_notification(url, site_name, message=""):
    if not EMAIL_SENDER or not EMAIL_PASSWORD or not EMAIL_RECEIVER:
        return False
        
    try:
        subject = "🔔 Website Change Detected"
        body = f"{message}\n\nWebsite: {site_name}\nURL: {url}\nTime: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
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
def send_telegram_notification(url, site_name, message=""):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return False
        
    try:
        full_message = f"🔔 {message}\n\nWebsite: {site_name}\nURL: {url}\nTime: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        response = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data={"chat_id": TELEGRAM_CHAT_ID, "text": full_message}
        )
        return response.status_code == 200
    except Exception as e:
        print(f"Telegram error: {e}")
        return False

# Extract room information from STWDO website
def extract_stwdo_rooms(content):
    soup = BeautifulSoup(content, 'html.parser')
    rooms = []
    
    # Look for room listings - this may need adjustment based on the actual HTML structure
    # Try multiple approaches to find room listings
    
    # Approach 1: Look for elements with common room-related classes
    room_elements = soup.find_all(['div', 'article', 'li', 'section'], 
                                 class_=re.compile(r'.*(wohnung|zimmer|angebot|room|listing|item).*', re.I))
    
    # Approach 2: Look for elements containing price information
    price_elements = soup.find_all(text=re.compile(r'€|EUR|Euro|\d+\s*€', re.I))
    
    # Approach 3: Look for links that might contain room details
    link_elements = soup.find_all('a', href=re.compile(r'.*(wohnung|zimmer|angebot).*', re.I))
    
    # Process room elements
    for element in room_elements:
        # Get text content
        text = element.get_text(strip=True)
        if text and len(text) > 20:  # Only consider substantial content
            # Create a unique identifier for this room based on key details
            identifier = text[:100].strip()  # Use first 100 chars as identifier
            rooms.append({
                "id": hashlib.md5(identifier.encode()).hexdigest()[:12],
                "content": identifier,
                "full_content": text[:300]  # Store first 300 chars for reference
            })
    
    # Process price elements if we haven't found enough rooms
    if len(rooms) < 5:  # Arbitrary threshold
        for price_element in price_elements:
            parent = price_element.parent
            if parent:
                text = parent.get_text(strip=True)
                if text and len(text) > 20:
                    identifier = text[:100].strip()
                    rooms.append({
                        "id": hashlib.md5(identifier.encode()).hexdigest()[:12],
                        "content": identifier,
                        "full_content": text[:300]
                    })
    
    # Process link elements if we haven't found enough rooms
    if len(rooms) < 5:
        for link_element in link_elements:
            try:
                text = link_element.get_text(strip=True)
                if text and len(text) > 10:
                    # Skip href extraction to avoid attribute access issues
                    identifier = text[:100].strip()
                    rooms.append({
                        "id": hashlib.md5(identifier.encode()).hexdigest()[:12],
                        "content": identifier,
                        "full_content": text[:300]
                    })
            except Exception:
                # Skip elements that cause issues
                continue
    
    # Remove duplicates based on ID
    unique_rooms = []
    seen_ids = set()
    for room in rooms:
        if room["id"] not in seen_ids:
            unique_rooms.append(room)
            seen_ids.add(room["id"])
    
    return unique_rooms

# Detect new rooms on STWDO website
def detect_new_rooms(current_content, previous_rooms):
    current_rooms = extract_stwdo_rooms(current_content)
    
    # Convert previous_rooms to set of IDs for comparison
    previous_room_ids = set(room["id"] for room in previous_rooms)
    
    # Find new rooms (in current but not in previous)
    new_rooms = []
    for room in current_rooms:
        if room["id"] not in previous_room_ids:
            new_rooms.append(room)
    
    return new_rooms, current_rooms

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
            monitor_type = st.radio("🔍 Monitoring Type:", 
                                  ["Any Change", "STWDO Room Detection"], 
                                  index=0 if st.session_state.editing_website.get("monitor_type", "any_change") == "any_change" else 1)
        else:
            url = st.text_input("🔗 Website URL:", placeholder="https://example.com")
            name = st.text_input("📝 Website Name:", placeholder="My Website")
            interval = st.number_input("⏱️ Check Interval (seconds):", min_value=30, max_value=3600, value=60, step=30)
            active = st.checkbox("✅ Active", value=True)
            monitor_type = st.radio("🔍 Monitoring Type:", 
                                  ["Any Change", "STWDO Room Detection"], 
                                  index=0)
        
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
                monitor_type_value = "stwdo_rooms" if monitor_type == "STWDO Room Detection" else "any_change"
                add_or_update_website(url, name_value, interval, active, monitor_type_value)
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
            monitor_type_text = "STWDO Room Detection" if site.get("monitor_type") == "stwdo_rooms" else "Any Change"
            st.markdown(f"<div class='website-info'><span class='info-label'>Monitor Type:</span> <span class='info-value'>{monitor_type_text}</span></div>", unsafe_allow_html=True)
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
                
                # Update last checked time
                site["last_checked"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                if site.get("monitor_type") == "stwdo_rooms" and "stwdo.de" in site["url"]:
                    # Special handling for STWDO room detection
                    previous_rooms = site.get("previous_rooms", [])
                    first_scan = not site.get("first_scan_completed", False)
                    
                    new_rooms, current_rooms = detect_new_rooms(content, previous_rooms)
                    
                    # Always update the rooms list
                    site["previous_rooms"] = current_rooms
                    site["first_scan_completed"] = True
                    
                    if not first_scan and new_rooms:
                        # New rooms detected (not the first scan)
                        site["last_changed"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        changes_detected.append({
                            "site": site,
                            "new_rooms": new_rooms
                        })
                        
                        # Send notifications
                        site_name = site.get('name', site['url'])
                        message = f"New rooms detected on {site_name}!\n\nNew listings found: {len(new_rooms)}"
                        if enable_email:
                            send_email_notification(site["url"], site_name, message)
                        if enable_telegram:
                            send_telegram_notification(site["url"], site_name, message)
                else:
                    # Regular change detection
                    current_hash = hashlib.md5(content.encode()).hexdigest()
                    
                    if site.get("current_hash") is None:
                        site["current_hash"] = current_hash
                    elif current_hash != site["current_hash"]:
                        # Change detected
                        site["last_changed"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        site["current_hash"] = current_hash
                        changes_detected.append({"site": site})
                        
                        # Send notifications
                        site_name = site.get('name', site['url'])
                        message = f"Change detected on {site_name}!"
                        if enable_email:
                            send_email_notification(site["url"], site_name, message)
                        if enable_telegram:
                            send_telegram_notification(site["url"], site_name, message)
                        
                # Save updated website data
                save_websites()
                        
            except Exception as e:
                print(f"Error checking {site['url']}: {e}")
        
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
        prev_rooms = selected_site.get("previous_rooms", [])
        first_scan = not selected_site.get("first_scan_completed", False)
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

                    # Update last checked time
                    selected_site["last_checked"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    
                    if selected_site.get("monitor_type") == "stwdo_rooms" and "stwdo.de" in selected_site["url"]:
                        # Special handling for STWDO room detection
                        new_rooms, current_rooms = detect_new_rooms(content, prev_rooms)
                        
                        # Always update the rooms list
                        selected_site["previous_rooms"] = current_rooms
                        selected_site["first_scan_completed"] = True
                        prev_rooms = current_rooms
                        
                        if not first_scan and new_rooms:
                            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                            # Send notifications only
                            site_name = selected_site.get('name', selected_site['url'])
                            message = f"New rooms detected on {site_name}!\n\nNew listings found: {len(new_rooms)}"
                            if enable_email:
                                send_email_notification(selected_site["url"], site_name, message)
                            if enable_telegram:
                                send_telegram_notification(selected_site["url"], site_name, message)
                            
                            # Update website data
                            selected_site["last_changed"] = timestamp
                        elif first_scan:
                            # Mark first scan as completed
                            first_scan = False
                    else:
                        # Regular change detection
                        current_hash = hashlib.md5(content.encode()).hexdigest()

                        if prev_hash is None:
                            prev_hash = current_hash

                        elif current_hash != prev_hash:
                            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                            # Send notifications only
                            site_name = selected_site.get('name', selected_site['url'])
                            message = f"Change detected on {site_name}!"
                            if enable_email:
                                send_email_notification(selected_site["url"], site_name, message)
                            if enable_telegram:
                                send_telegram_notification(selected_site["url"], site_name, message)
                            
                            # Update website data
                            selected_site["last_changed"] = timestamp
                            selected_site["current_hash"] = current_hash
                            prev_hash = current_hash
                        else:
                            pass  # No change detected
                    
                    # Save updated website data
                    for site in st.session_state.websites:
                        if site["url"] == selected_site["url"]:
                            site.update(selected_site)
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
