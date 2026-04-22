"""
tracker.py — Tracker server (Flask)

The Tracker maintains a list of active peers and provides node discovery.

API endpoints:
  POST /register        Register / heartbeat, body: {url: str}
  GET  /peers           Return list of active peer URLs
  GET  /health          Health check
"""

import threading
import time

from flask import Flask, request, jsonify

from config import HEARTBEAT_INTERVAL


def create_tracker_app() -> Flask:
    app = Flask(__name__)

    # peers: {url -> last_seen_timestamp}
    _peers: dict[str, float] = {}
    _lock   = threading.Lock()

    def _prune():
        """Remove nodes that have not sent a heartbeat within 2x HEARTBEAT_INTERVAL."""
        cutoff = time.time() - HEARTBEAT_INTERVAL * 2
        with _lock:
            dead = [url for url, ts in _peers.items() if ts < cutoff]
            for url in dead:
                del _peers[url]

    # ── Routes ────────────────────────────────────────────────────────────────

    @app.route("/register", methods=["POST"])
    def register():
        data = request.get_json(silent=True) or {}
        url  = data.get("url", "").strip()
        if not url:
            return jsonify({"error": "missing url"}), 400
        with _lock:
            _peers[url] = time.time()
        _prune()
        return jsonify({"status": "ok", "registered": url}), 200

    @app.route("/peers", methods=["GET"])
    def list_peers():
        _prune()
        with _lock:
            return jsonify({"peers": list(_peers.keys())}), 200

    @app.route("/health", methods=["GET"])
    def health():
        with _lock:
            count = len(_peers)
        return jsonify({"status": "ok", "peer_count": count}), 200

    return app
