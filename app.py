# -*- coding: utf-8 -*-
"""
Market Research Pro — Flask Web Server (Full Edition)
=====================================================
All features from the desktop app, now served as a mobile web app.

FOLDER STRUCTURE:
  your_project/
  ├── app.py                    ← this file
  ├── final_project_mobile.py   ← your logic file (unchanged)
  ├── static/
  │   └── style.css
  └── templates/
      └── index.html
"""

import threading
import json
import logging
from flask import Flask, render_template, request, jsonify
import final_project_mobile as fpm

log = logging.getLogger("FlaskApp")
fpm.init_db()

app = Flask(__name__)


# ── Pages ─────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/check")
def check():
    return "Market Research Pro — server running ✓"


# ── Core search (Maps + Amazon + Play in parallel) ────────────────────────────

@app.route("/search", methods=["POST"])
def search():
    body     = request.get_json(force=True)
    query    = (body.get("query") or "").strip()
    location = (body.get("location") or "Ahmedabad").strip()
    if not query:
        return jsonify({"error": "Query is required"}), 400

    results = {"maps": [], "amazon": [], "play": []}
    errors  = []

    def fetch_maps():
        try:
            results["maps"] = fpm.MapsDataFetcher.fetch_places(query, location)
        except Exception as e:
            errors.append(f"Maps: {e}")

    def fetch_amazon():
        try:
            results["amazon"] = fpm.AmazonFetcher.fetch(query)
        except Exception as e:
            errors.append(f"Amazon: {e}")

    def fetch_play():
        try:
            results["play"] = fpm.PlayStoreFetcher.fetch(query)
        except Exception as e:
            errors.append(f"Play: {e}")

    threads = [
        threading.Thread(target=fetch_maps,   daemon=True),
        threading.Thread(target=fetch_amazon, daemon=True),
        threading.Thread(target=fetch_play,   daemon=True),
    ]
    for t in threads: t.start()
    for t in threads: t.join(timeout=45)

    try:
        fpm.save_search(query, location, None,
                        results["maps"], results["amazon"], results["play"])
    except Exception:
        pass

    if errors:
        results["warnings"] = errors
    return jsonify(results)


# ── Restaurant search ─────────────────────────────────────────────────────────

@app.route("/restaurants", methods=["POST"])
def restaurants():
    body     = request.get_json(force=True)
    cuisine  = (body.get("cuisine") or "").strip()
    location = (body.get("location") or "Ahmedabad").strip()
    vibe     = (body.get("vibe") or "").strip()
    if not cuisine:
        return jsonify({"error": "Cuisine is required"}), 400

    query = f"{cuisine} {vibe} restaurant".strip() if vibe else f"{cuisine} restaurant"
    try:
        data = fpm.MapsDataFetcher.fetch_places(query, location, is_restaurant=True)
        return jsonify({"restaurants": data})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Google Trends ─────────────────────────────────────────────────────────────

@app.route("/trends", methods=["POST"])
def trends():
    body    = request.get_json(force=True)
    keyword = (body.get("query") or "").strip()
    if not keyword:
        return jsonify({"error": "Query is required"}), 400
    try:
        data = fpm.fetch_google_trends(keyword)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── AI Business Report ────────────────────────────────────────────────────────

@app.route("/report", methods=["POST"])
def report():
    body        = request.get_json(force=True)
    query       = (body.get("query") or "").strip()
    location    = (body.get("location") or "").strip()
    maps        = body.get("maps", [])
    amazon      = body.get("amazon", [])
    play        = body.get("play", [])
    trends_data = body.get("trends", {})
    price_range = body.get("price_range", None)
    if not query:
        return jsonify({"error": "Query is required"}), 400
    try:
        text = fpm.generate_business_report(
            query, location, price_range, maps, amazon, play, trends_data)
        fpm.save_report(query, location, text)
        return jsonify({"report": text})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── AI Chat ───────────────────────────────────────────────────────────────────

@app.route("/chat", methods=["POST"])
def chat():
    body     = request.get_json(force=True)
    messages = body.get("messages", [])
    if not messages:
        return jsonify({"error": "No messages"}), 400
    try:
        reply = fpm.chat_with_ai(messages[-10:])
        return jsonify({"reply": reply})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Search history ────────────────────────────────────────────────────────────

@app.route("/history", methods=["GET"])
def history():
    try:
        rows = fpm.load_searches()
        data = [{"id": r[0], "query": r[1], "location": r[2],
                 "maps": r[3], "amazon": r[4], "play": r[5],
                 "timestamp": r[6]} for r in rows]
        return jsonify({"history": data})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/history/<int:sid>", methods=["GET"])
def history_item(sid):
    try:
        data = fpm.load_search_data(sid)
        if data:
            return jsonify(data)
        return jsonify({"error": "Not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    log.info("Starting Market Research Pro — Full Web Edition")
    app.run(host="0.0.0.0", port=5000, debug=False)
