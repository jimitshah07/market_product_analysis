================================================================================
                    MARKET RESEARCH PRO — ULTIMATE EDITION
                         README & SETUP DOCUMENTATION
================================================================================

OVERVIEW
--------
Market Research Pro is an AI-powered desktop application built for Indian
entrepreneurs to perform competitive market analysis. It aggregates data from
Google Maps, Amazon.in, Google Play Store, and Google Trends, then uses a
locally running AI (Ollama) to generate business intelligence reports.

--------------------------------------------------------------------------------
LANGUAGE
--------
  Python 3.9+  (recommended: Python 3.10 or 3.11)

--------------------------------------------------------------------------------
CORE FRAMEWORK
--------------
  tkinter          — Built-in Python GUI framework (ships with Python)
  ttk              — Themed widget set (part of tkinter)

--------------------------------------------------------------------------------
REQUIRED DEPENDENCIES  (must install)
--------------------------------------
Install all at once:
  pip install requests python-dotenv beautifulsoup4 matplotlib numpy

Individual packages:

  Package              Version (min)   Purpose
  ───────────────────  ─────────────   ──────────────────────────────────────
  requests             2.28+           HTTP calls to Ollama API & Amazon scrape
  python-dotenv        1.0+            Load .env config (API keys, model name)
  beautifulsoup4       4.12+           HTML parsing for Amazon.in scrape
  matplotlib           3.7+            Charts & graphs (analytics, trends, etc.)
  numpy                1.24+           Data calculations for radar & price charts

--------------------------------------------------------------------------------
OPTIONAL DEPENDENCIES  (install for full functionality)
-------------------------------------------------------
  pip install textblob google-play-scraper pytrends reportlab serpapi
              deep-translator langdetect

  Package                Version (min)   Purpose / Feature unlocked
  ─────────────────────  ─────────────   ──────────────────────────────────────
  textblob               0.17+           Sentiment analysis on reviews
  google-play-scraper    1.2+            Fetch Play Store apps & reviews
  pytrends               4.9+            Google Trends data (India)
  reportlab              4.0+            Export reports to PDF
  serpapi                2.0+            SerpAPI client for Maps/Amazon search
  deep-translator        1.9+            Translate Hindi/Gujarati/regional reviews
  langdetect             1.0.9+          Auto-detect Indian language in reviews

--------------------------------------------------------------------------------
EXTERNAL SERVICE DEPENDENCIES
------------------------------
  1. SerpAPI (https://serpapi.com)
     - Used for: Google Maps local shop search, Amazon.in product search
     - Setup: Get a free/paid API key from serpapi.com
     - Configure: Set SERPAPI_KEY in .env file (see Configuration below)

  2. Ollama  (https://ollama.com)
     - Used for: Local AI model — query parsing, report generation, chat
     - Setup:
         a. Download & install from https://ollama.com
         b. Pull model:   ollama pull qwen2.5:1.5b
         c. Start server: ollama serve
     - The app defaults to qwen2.5:1.5b (fast & lightweight)
     - You can use any Ollama-compatible model (e.g. qwen2.5:7b, llama3.2)

--------------------------------------------------------------------------------
CONFIGURATION  (.env file)
---------------------------
Create a file named  .env  in the same folder as the script:

    SERPAPI_KEY=your_serpapi_key_here
    OLLAMA_MODEL=qwen2.5:1.5b
    OLLAMA_URL=http://localhost:11434

  SERPAPI_KEY   — Your SerpAPI key (required for Maps & Amazon data)
  OLLAMA_MODEL  — Ollama model to use for AI features (default: qwen2.5:1.5b)
  OLLAMA_URL    — Ollama server URL (default: http://localhost:11434)

--------------------------------------------------------------------------------
DATABASE
--------
  SQLite3  — Built into Python (no install needed)
  File:      market_research.db  (auto-created on first run)
  Tables:    searches, cache, reports

  The database stores:
    - All search results (maps, Amazon, Play Store data)
    - API response cache (12-hour TTL to reduce API calls)
    - Generated AI reports

--------------------------------------------------------------------------------
FILES GENERATED AT RUNTIME
---------------------------
  market_research.db   — SQLite database (search history, cache, reports)
  logs/app_YYYYMMDD.log — Daily log file (auto-created in logs/ folder)

--------------------------------------------------------------------------------
HOW TO RUN
----------
  1. Install Python 3.9+ from https://python.org
  2. Install required dependencies:
       pip install requests python-dotenv beautifulsoup4 matplotlib numpy
  3. Install optional dependencies for full features:
       pip install textblob google-play-scraper pytrends reportlab serpapi deep-translator langdetect
  4. Set up Ollama:
       a. Download from https://ollama.com
       b. Run: ollama pull qwen2.5:1.5b
       c. Run: ollama serve
  5. Create .env file with your SERPAPI_KEY (see Configuration above)
  6. Run the app:
       python market_research_pro.py

--------------------------------------------------------------------------------
KEY FEATURES
------------
  - Natural language query parsing via local Ollama AI
  - Google Maps competitor shop analysis (ratings, reviews, hours, location)
  - Amazon.in product price landscape & competitor listing
  - Google Play Store app category analysis
  - Google Trends demand signal (India, 12-month)
  - Multilingual sentiment analysis (English, Hindi, Gujarati & 8 more languages)
  - Interactive analytics dashboard (bar charts, scatter plots, radar charts)
  - Break-even & profit calculator with live chart
  - AI-generated business intelligence report (PDF + TXT export)
  - Search history with reload, JSON export
  - Dark / Light theme toggle
  - 12-hour API response cache (SQLite)

--------------------------------------------------------------------------------
TECH STACK SUMMARY
------------------
  Layer              Technology
  ─────────────────  ──────────────────────────────────────────────────────────
  Language           Python 3.9+
  GUI Framework      Tkinter (ttk)
  AI / LLM           Ollama (local) — qwen2.5:1.5b default
  Data Viz           Matplotlib + NumPy
  Database           SQLite3 (built-in)
  Web Scraping       BeautifulSoup4 + Requests
  Sentiment NLP      TextBlob + deep-translator + langdetect
  Maps & Search      SerpAPI (Google Maps engine)
  E-commerce         SerpAPI (Amazon engine) + direct scrape fallback
  App Store          google-play-scraper
  Trends             pytrends (Google Trends unofficial API)
  PDF Export         Reportlab
  Config             python-dotenv (.env file)
  Caching            SQLite3 (12-hour TTL)
  Logging            Python logging module (rotating daily log files)

--------------------------------------------------------------------------------
KNOWN REQUIREMENTS / NOTES
--------------------------
  - Google Trends may return HTTP 429 (rate limit). Wait 5–10 minutes and retry.
  - Amazon.in scraping uses a fallback direct scraper if SerpAPI is unavailable.
  - Ollama must be running (ollama serve) before launching the app.
  - The app requires an active internet connection for all data fetching.
  - urllib3 v2 compatibility patch is applied automatically at startup.
  - Minimum window size: 1100 x 700 px. Recommended: 1520 x 920 px.

--------------------------------------------------------------------------------
DEVELOPED FOR
-------------
  Indian market research context (INR pricing, Indian city locations,
  Indian language review support, Google Trends geo: IN)

================================================================================
                       Market Research Pro — Ultimate Edition
================================================================================
