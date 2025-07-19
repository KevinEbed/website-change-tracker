from flask import Flask, request, redirect, render_template_string
from flask_sqlalchemy import SQLAlchemy
import requests
import hashlib
import os
import smtplib
import threading
import time
from datetime import datetime
from email.mime.text import MIMEText
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///monitored_sites.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# DB Model
class MonitoredSite(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String(200), unique=True, nullable=False)
    interval = db.Column(db.Integer, nullable=False)
    is_active = db.Column(db.Boolean, default=False)
    last_checked = db.Column(db.DateTime)

# Thread Management
monitoring_threads = {}  # {id: {"thread": t, "stop": Event()}}

def send_email_notification(url):
    subject = "🔔 Website Change Detected"
    body = f"The content at {url} has changed."
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = EMAIL_SENDER
    msg["To"] = EMAIL_RECEIVER

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.send_message(msg)
        print("📧 Email sent!")
    except Exception as e:
        print(f"❌ Email failed: {e}")

def send_telegram_notification(url):
    message = f"🔔 Change detected at {url}"
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data={"chat_id": TELEGRAM_CHAT_ID, "text": message}
        )
        if response.status_code == 200:
            print("📩 Telegram sent!")
        else:
            print("⚠️ Telegram failed.")
    except Exception as e:
        print(f"❌ Telegram error: {e}")

def monitor_website(site_id, url, interval, stop_event):
    print(f"👀 Monitoring {url}")
    prev_hash = None

    while not stop_event.is_set():
        try:
            response = requests.get(url, timeout=10)
            content = response.text
            current_hash = hashlib.md5(content.encode()).hexdigest()

            if prev_hash is None:
                prev_hash = current_hash
            elif current_hash != prev_hash:
                print("🚨 Change Detected!")
                send_email_notification(url)
                send_telegram_notification(url)
                prev_hash = current_hash

            site = MonitoredSite.query.get(site_id)
            if site:
                site.last_checked = datetime.utcnow()
                db.session.commit()

            time.sleep(interval)
        except Exception as e:
            print(f"❌ Monitoring error: {e}")
            break

@app.before_first_request
def setup():
    db.create_all()

@app.route('/', methods=['GET', 'POST'])
def home():
    message = ""

    if request.method == 'POST':
        url = request.form['url']
        interval = int(request.form['interval'])

        existing = MonitoredSite.query.filter_by(url=url).first()
        if existing:
            message = "⚠️ URL already exists."
        else:
            new_site = MonitoredSite(url=url, interval=interval)
            db.session.add(new_site)
            db.session.commit()
            message = f"✅ Added {url}"

    sites = MonitoredSite.query.all()
    return render_template_string(TEMPLATE, message=message, sites=sites)

@app.route('/start/<int:site_id>')
def start_monitoring(site_id):
    site = MonitoredSite.query.get_or_404(site_id)
    if site.is_active:
        return redirect('/')

    stop_event = threading.Event()
    thread = threading.Thread(target=monitor_website, args=(site.id, site.url, site.interval, stop_event), daemon=True)
    thread.start()
    monitoring_threads[site.id] = {"thread": thread, "stop": stop_event}
    site.is_active = True
    db.session.commit()
    return redirect('/')

@app.route('/stop/<int:site_id>')
def stop_monitoring(site_id):
    if site_id in monitoring_threads:
        monitoring_threads[site_id]['stop'].set()
        del monitoring_threads[site_id]

    site = MonitoredSite.query.get_or_404(site_id)
    site.is_active = False
    db.session.commit()
    return redirect('/')

@app.route('/delete/<int:site_id>')
def delete_site(site_id):
    stop_monitoring(site_id)
    site = MonitoredSite.query.get_or_404(site_id)
    db.session.delete(site)
    db.session.commit()
    return redirect('/')

# HTML Template with table
TEMPLATE = '''
<!doctype html>
<title>Website Change Detector</title>
<h2>🌐 Website Change Detector</h2>
<form method=post>
  <label>Enter URL:</label><br>
  <input type=text name=url size=50 required><br><br>
  <label>Interval (sec):</label><br>
  <input type=number name=interval min=10 max=3600 value=60><br><br>
  <button type="submit">➕ Add</button>
</form>

<p>{{ message }}</p>

<h3>📋 Monitored Websites</h3>
<table border=1 cellpadding=6>
<tr><th>ID</th><th>URL</th><th>Interval</th><th>Status</th><th>Last Checked</th><th>Actions</th></tr>
{% for site in sites %}
<tr>
  <td>{{ site.id }}</td>
  <td>{{ site.url }}</td>
  <td>{{ site.interval }}</td>
  <td>{{ '✅ Active' if site.is_active else '❌ Inactive' }}</td>
  <td>{{ site.last_checked or 'Never' }}</td>
  <td>
    {% if site.is_active %}
      <a href="/stop/{{ site.id }}">⏹ Stop</a>
    {% else %}
      <a href="/start/{{ site.id }}">▶️ Start</a>
    {% endif %}
    | <a href="/delete/{{ site.id }}" onclick="return confirm('Are you sure?')">🗑 Delete</a>
  </td>
</tr>
{% endfor %}
</table>
'''

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
