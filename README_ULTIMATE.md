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
CONFIGURATION (.env)
---------------------
Create a .env file:
    SERPAPI_KEY=your_key_here
    OLLAMA_MODEL=qwen2.5:1.5b
    OLLAMA_VISION_MODEL=qwen2.5-vl
    OLLAMA_URL=http://localhost:11434

--------------------------------------------------------------------------------
HOW TO RUN
----------
  python final_project.py

FOR MOBILE APPLICATION:

Steps:
1. Run "python app.py"
2. Enter the same IP obtained in the output on your web browser or any other laptop to run it locally on your device

--------------------------------------------------------------------------------
NOTES & SUPPORT
---------------
  - Database: market_research.db (Auto-created, stores history & cache).
  - Logs: logs/ folder contains daily rotating app logs.
  - Performance: All AI processing is local; high RAM is recommended for 
    Ollama Vision features.




================================================================================
                       Developed for the Indian Market Context
================================================================================
