# Market Research Tool

A desktop-based market research assistant that helps you analyze competitors and generate insights for a product idea.  

You describe your product in plain English, and the tool:
- extracts structured data using an LLM
- finds competitors from Google Maps, Play Store, and Amazon
- analyzes reviews and listings
- generates a simple report with insights

---

## Features

- Natural language input (no strict format needed)
- AI-based extraction of product, location, and price range
- Competitor discovery:
  - Google Maps businesses
  - Play Store apps (if relevant)
  - Amazon products
- Review scraping and basic analysis
- Visual insights using matplotlib
- Simple GUI (Tkinter-based)

---

## Project Structure

Tool/
│
├── app.py              # Main UI logic (Tkinter app)
├── main.py             # Entry point
├── fetchers.py         # Data fetching (Maps, Play Store, Amazon)
├── llm.py              # LLM integration (Ollama)
├── utils.py            # Helper utilities
├── constants.py        # Config + theme constants
├── popups.py           # UI popups
├── requirements.txt    # Dependencies
├── .env                # API keys (you need to configure this)

---

## Requirements

- Python 3.10+
- Internet connection (for APIs)
- Ollama installed locally (for LLM parsing)

---

## Dependencies

Install everything using:

pip install -r requirements.txt

Main packages used:
- matplotlib
- google-play-scraper
- google-search-results (SerpAPI)
- python-dotenv

---

## Setup

### 1. Clone / Extract the Project

git clone <your-repo>
cd Tool

or just extract the ZIP and open the folder.

---

### 2. Create `.env` file

You’ll need API keys and config.

Example:

SERPAPI_KEY=your_serpapi_key_here
OLLAMA_URL=http://localhost:11434/api/generate
OLLAMA_MODEL=mistral

---

### 3. Install & Run Ollama

Install Ollama from: https://ollama.com/

Then pull a model:

ollama pull mistral

Start Ollama (if not already running):

ollama serve

---

## How to Run

From inside the project folder:

python main.py

That will launch the GUI.

---

## How to Use

1. Enter a product idea in plain English  
   Example:
   I want to sell headphones in Ahmedabad around 2000

2. The tool will:
   - extract product + location + price
   - fetch competitors
   - display results in tabs

3. You can:
   - view listings
   - explore reviews
   - generate insights

---

## Notes / Limitations

- SerpAPI has rate limits (free tier is limited)
- Play Store scraping may fail if Google changes structure
- Amazon scraping is indirect (via search APIs, not official)
- LLM parsing depends on your local Ollama model quality
- UI is Tkinter → not super modern, but works

---

## Tools & Technologies Used

- Python (core logic)
- Tkinter (GUI)
- Matplotlib (charts)
- SerpAPI (Google Maps data)
- Google Play Scraper (app data)
- Ollama (local LLM)
- dotenv (config management)
