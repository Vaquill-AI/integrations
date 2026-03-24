"""
Optional health-check HTTP server for platforms that require an endpoint
(e.g., Replit, Railway, uptime monitors).

Usage in bot.py:
    from health_check import start_health_server
    start_health_server()  # before bot.run()
"""

import os
from datetime import datetime, timezone
from threading import Thread

from flask import Flask, jsonify

app = Flask(__name__)
start_time = datetime.now(tz=timezone.utc)


@app.route("/")
def home():
    return jsonify(
        {
            "status": "healthy",
            "service": "Vaquill Discord Bot",
            "uptime": str(datetime.now(tz=timezone.utc) - start_time),
        }
    )


@app.route("/health")
def health():
    return jsonify({"status": "ok"}), 200


def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)


def start_health_server():
    """Start health-check server in a daemon thread."""
    server_thread = Thread(target=run, daemon=True)
    server_thread.start()
