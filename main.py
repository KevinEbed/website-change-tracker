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
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///urls.db'
db = SQLAlchemy(app)

class URL(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    link = db.Column(db.String(500), nullable=False)
    monitoring = db.Column(db.Boolean, default=False)
    interval = db.Column(db.Integer, default=60)

with app.app_context():
    db.create_all()

monitoring_threads = {}

HTML_TEMPLATE = '''
<!doctype html>
<html lang="en">
<head>
    <title>URL Monitor</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body class="bg-light">
<div class="container py-5">
    <h2 class="mb-4 text-center">🌐 Website Change Monitor</h2>
    <form method="post" class="row g-3 mb-4">
        <div class="col-md-6">
            <input type="text" name="link" class="form-control" placeholder="Enter URL" required>
        </div>
        <div class="col-md-3">
            <input type="number" name="interval" class="form-control" placeholder="Check every (sec)" required min="10">
        </div>
        <div class="col-md-3">
            <button type="submit" class="btn btn-primary w-100">➕ Add URL</button>
        </div>
    </form>
    <ul class="list-group">
        {% for url in urls %}
        <li class="list-group-item d-flex justify-content-between align-items-center">
            <div>
                <strong>{{ url.link }}</strong> — every {{ url.interval }}s
                {% if url.monitoring %}
                    <span class="badge bg-success ms-2">Monitoring</span>
                {% else %}
                    <span class="badge bg-secondary ms-2">Idle</span>
                {% endif %}
            </div>
            <div>
                {% if url.monitoring %}
                    <a href="/stop/{{ url.id }}" class="btn btn-warning btn-sm">⛔ Stop</a>
                {% else %}
                    <a href="/start/{{ url.id }}" class="btn btn-success btn-sm">▶️ Start</a>
                {% endif %}
                <a href="/delete/{{ url.id }}" class="btn btn-danger btn-sm">🗑 Delete</a>
            </div>
        </li>
        {% endfor %}
    </ul>
</div>
</body>
</html>
'''

def send_email(subject, body):
    msg = MIMEText(body)
    msg['From'] = EMAIL_SENDER
    msg['To'] = EMAIL_RECEIVER
    msg['Subject'] = subject
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.send_message(msg)
        print("[INFO] Email sent.")
    except Exception as e:
        print(f"[ERROR] Failed to send email: {e}")

def send_telegram(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message
        }
        requests.post(url, data=payload)
        print("[INFO] Telegram message sent.")
    except Exception as e:
        print(f"[ERROR] Failed to send Telegram message: {e}")

def monitor_website(url, url_id, interval):
    print(f"👀 Monitoring {url}")
    try:
        response = requests.get(url)
        old_hash = hashlib.md5(response.content).hexdigest()
    except Exception as e:
        print(f"[ERROR] Failed to fetch initial content: {e}")
        return

    while True:
        with app.app_context():
            url_obj = URL.query.get(url_id)
            if not url_obj or not url_obj.monitoring:
                print(f"[INFO] Monitoring stopped for {url}")
                break

        try:
            time.sleep(interval)
            response = requests.get(url)
            current_hash = hashlib.md5(response.content).hexdigest()
            if current_hash != old_hash:
                print(f"[INFO] Change detected on {url} at {datetime.now()}")
                message = f"🔔 Change detected on: {url} at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                send_email("Website Content Changed", message)
                send_telegram(message)
                old_hash = current_hash
            else:
                print(f"[DEBUG] No change at {datetime.now()}")
        except Exception as e:
            print(f"[ERROR] Error during monitoring: {e}")

@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        link = request.form['link']
        interval = int(request.form['interval'])
        if link and interval:
            new_url = URL(link=link, interval=interval)
            db.session.add(new_url)
            db.session.commit()
    urls = URL.query.all()
    return render_template_string(HTML_TEMPLATE, urls=urls)

@app.route('/start/<int:url_id>')
def start_monitoring(url_id):
    url_entry = URL.query.get_or_404(url_id)
    if not url_entry.monitoring:
        url_entry.monitoring = True
        db.session.commit()
        thread = threading.Thread(target=monitor_website, args=(url_entry.link, url_id, url_entry.interval), daemon=True)
        monitoring_threads[url_id] = thread
        thread.start()
    return redirect('/')

@app.route('/stop/<int:url_id>')
def stop_monitoring(url_id):
    url_entry = URL.query.get_or_404(url_id)
    url_entry.monitoring = False
    db.session.commit()
    return redirect('/')

@app.route('/delete/<int:url_id>')
def delete_url(url_id):
    url_entry = URL.query.get_or_404(url_id)
    if url_entry.monitoring:
        url_entry.monitoring = False
    db.session.delete(url_entry)
    db.session.commit()
    return redirect('/')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
