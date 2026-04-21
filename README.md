# Market Research Pro — Product Analysis Edition

This folder contains the **Ultimate Edition** of the Market Research Pro application, specifically tuned for deep competitor and product landscape analysis.

## 🚀 Getting Started

👉 For detailed documentation, see [README_ULTIMATE.md](README_ULTIMATE.md)

1. **Install Dependencies**:
   ```bash
   pip install requests python-dotenv beautifulsoup4 matplotlib numpy Pillow textblob google-play-scraper pytrends reportlab serpapi deep-translator langdetect
   ```

2. **Setup Local AI (Ollama)**:
   - Install Ollama from [ollama.com](https://ollama.com).
   - Pull the required models:
     ```bash
     ollama pull qwen2.5:1.5b
     ollama pull qwen2.5-vl
     ```
   - Ensure `ollama serve` is running.

3. **Configure API**:
   - Create a `.env` file in this directory and add your `SERPAPI_KEY`.

4. **Launch**:
   ```bash
   python final_project.py
   ```

## 🛠️ Features

- **Multi-Mode Analysis**: Switch between "Market Research" and "Restaurant Analysis" for tailored data fetching.
- **AI Vision Gallery**: Automated media classification and Menu OCR using local vision intelligence.
- **Professional Dashboard**: Interactive charts for Market Structure (Chain vs Local), Pricing Landscape, and Demand Trends.
- **Deep Sentiment**: Natural language processing on customer reviews with multilingual support.

## 📁 File Structure

- `final_project.py`: Main application entry point.
- `logs/`: Application execution logs.
- `market_research.db`: Local SQLite cache and search history.
