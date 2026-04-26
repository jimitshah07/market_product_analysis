================================================================================
                    MARKET RESEARCH PRO — ULTIMATE EDITION
                         README & SETUP DOCUMENTATION
================================================================================

OVERVIEW
--------
Market Research Pro is a high-end, AI-powered desktop application designed for 
entrepreneurs in India to perform professional-grade market intelligence. 
It features specialized modes for General Market Research and Deep Restaurant 
Competitor Analysis, integrating data from Google Maps, Amazon.in, Play Store, 
and Google Trends with a local AI brain (Ollama).

--------------------------------------------------------------------------------
CORE TECHNOLOGY
---------------
  - Language: Python 3.9+ (Tested on 3.10/3.11)
  - Interface: Tkinter + Custom "Deep Space" Design System
  - AI Engine: Ollama (Local API)
  - Data Visualization: Matplotlib Figure OO API
  - Database: SQLite3 (Local storage & 12-hour result caching)

--------------------------------------------------------------------------------
KEY FEATURES & MODES
--------------------
1. 🍽️ RESTAURANT INTELLIGENCE MODE
   - Surgical competitor analysis for food businesses.
   - High-Power Photo Discovery: Multi-stage surgical discovery (Maps + Web fallback).
   - AI Vision Media Categorization: Automatically sorts photos into Food, Menu, 
     and Ambiance buckets using local Vision models (qwen2.5-vl/llava).
   - Deep Menu OCR: Extracts dishes and prices directly from menu photos.
   - Popular Dish Discovery: Mines reviews for "Best Sellers" and "Must Tries."

2. 📊 PROFESSIONAL MARKET ANALYTICS
   - Market Structure Analysis: Chain vs. Local brand dominance charts.
   - Pricing Landscapes: Amazon.in competitor price distribution.
   - Demand Signals: Integrated Google Trends for Indian market demand.
   - Relevance-Based Sorting: Prioritizes major brands and market leaders.

3. ✍️ AI-POWERED REPORTING
   - Local LLM query parsing & intelligence reports via Ollama.
   - Professional PDF Export (ReportLab).
   - Multilingual Sentiment Analysis: Supports English, Hindi, Gujarati, and 
     8+ regional languages.

--------------------------------------------------------------------------------
REQUIRED DEPENDENCIES
----------------------
Core Installation:
  pip install requests python-dotenv beautifulsoup4 matplotlib numpy Pillow

Feature Unlock (Recommended):
  pip install textblob google-play-scraper pytrends reportlab serpapi deep-translator langdetect

--------------------------------------------------------------------------------
EXTERNAL AI SETUP (Ollama)
--------------------------
1. Download from: https://ollama.com
2. Required Models:
     - Language:   ollama pull qwen2.5:1.5b
     - Vision:     ollama pull qwen2.5-vl  (or 'llava')
3. Start:         ollama serve

--------------------------------------------------------------------------------
⚠️  API KEY SETUP (REQUIRED — READ CAREFULLY)
---------------------------------------------
This project uses SerpAPI to fetch data from Google Maps, Amazon, and Google
Trends. The API key is NOT included in this repository for security reasons.

Every user must obtain and configure their OWN API key. Here's how:

STEP 1 — Get a free SerpAPI key:
  → Go to: https://serpapi.com
  → Sign up for a free account (100 free searches/month included)
  → Copy your API key from the dashboard

STEP 2 — Create a .env file in the project root folder:
  (The project root is the same folder that contains final_project.py)

  Create a file named exactly:  .env
  Add these lines inside it:

      SERPAPI_KEY=paste_your_key_here
      OLLAMA_MODEL=qwen2.5:1.5b
      OLLAMA_URL=http://localhost:11434

  A template file called .env.example is included — you can copy/rename it.

STEP 3 — Never share your .env file:
  → The .env file is blocked by .gitignore and will NEVER be uploaded to GitHub
  → Do not send it to anyone or commit it to any repository
  → Each person running this project needs their own key

WHY THE KEY IS NOT IN THE CODE:
  The source code previously had the API key hardcoded as a fallback value.
  This was a security risk — anyone who downloaded the project could see and
  use the key, exhausting its free quota. The key has now been removed from
  all source files. The app reads it ONLY from your local .env file.

--------------------------------------------------------------------------------
HOW TO RUN
----------
  python final_project.py

FOR MOBILE/WEB (Flask server):
  1. Run "python app.py"
  2. Open the IP address shown in the terminal on your phone or another device

--------------------------------------------------------------------------------
NOTES & SUPPORT
---------------
  - Database: market_research.db (Auto-created, stores history & cache)
  - Logs: logs/ folder contains daily rotating app logs
  - Performance: All AI processing is local; high RAM recommended for 
    Ollama Vision features
  - If SerpAPI key is missing or empty, data fetching will fail with an error —
    this is expected and means you need to add your key to the .env file


================================================================================
                       Developed for the Indian Market Context
================================================================================
