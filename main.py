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

with app.app_context():
    db.create_all()

HTML_TEMPLATE = '''
<!doctype html>
<title>URL Monitor</title>
<h2>Enter URL to monitor:</h2>
<form method=post>
  <input type=text name=link size=60>
  <input type=submit value=Add>
</form>
<ul>
{% for url in urls %}
  <li>{{ url.link }} - {% if url.monitoring %}<strong>Monitoring</strong>{% else %}<a href="/start/{{ url.id }}">Start Monitoring</a>{% endif %}</li>
{% endfor %}
</ul>
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
        if link:
            new_url = URL(link=link)
            db.session.add(new_url)
            db.session.commit()
    urls = URL.query.all()
    return render_template_string(HTML_TEMPLATE, urls=urls)

@app.route('/start/<int:url_id>')
def start_monitoring(url_id):
    url_entry = URL.query.get_or_404(url_id)
    url_entry.monitoring = True
    db.session.commit()
    threading.Thread(target=monitor_website, args=(url_entry.link, url_id, 60), daemon=True).start()
    return redirect('/')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
