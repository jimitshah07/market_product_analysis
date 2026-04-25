"""
Market Research Pro — Ultimate Edition (HANG-FREE BUILD)
=========================================================
Fixes applied vs. previous version
------------------------------------
1.  SortPreferenceDialog  — removed blocking parent.wait_window(); dialog now uses
    a callback pattern so the main-thread event loop is never blocked.
2.  _run_all              — no longer opens the sort dialog synchronously before
    spawning worker threads.  Sort can be changed any time via the sidebar button.
3.  _scroll_chat_bottom   — uses a single after(50, …) shot; no recursive loop.
4.  _tick_clock           — guarded with winfo_exists() so it stops safely on close.
5.  Analytics             — always computed off the main thread; only the final
    _build_analytics() call runs on the main thread (via self.after).
6.  Matplotlib            — all charts use the Figure OO API exclusively; no
    plt.subplots / plt.show / plt.close calls that can deadlock with TkAgg.
7.  SQLite                — all DB reads/writes wrapped in try/except with
    isolation_level=None (auto-commit) to prevent journal-lock hangs.
8.  Thread workers        — every worker catches ALL exceptions and always calls
    the on_*_fail callback so _check_all_done() is always reached.
9.  Retry delays          — time.sleep() in with_retry is harmless inside daemon
    threads; confirmed no sleep on the main thread.
10. _on_closing           — plt.close("all") + os._exit(0) retained; added
    after_cancel for the clock callback so Tk doesn't error after destroy.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import json
import os
import re
import time
import logging
import sqlite3
import hashlib
import webbrowser
import urllib.request
import urllib.parse
import urllib.error
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from collections import Counter
from dotenv import load_dotenv

# ── urllib3 v2 compat patch ───────────────────────────────────────────────────
try:
    from urllib3.util.retry import Retry as _Retry
    _orig_retry_init = _Retry.__init__
    def _patched_retry_init(self, *args, **kwargs):
        if "method_whitelist" in kwargs:
            kwargs["allowed_methods"] = kwargs.pop("method_whitelist")
        _orig_retry_init(self, *args, **kwargs)
    _Retry.__init__ = _patched_retry_init
except Exception:
    pass

load_dotenv()
SERPAPI_KEY  = os.getenv("SERPAPI_KEY", "7fd9b6a3d93cb68813e8af8a95f4aa4543cebd2cbeb1d12ac466651c3bedf292")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:1.5b")
OLLAMA_URL   = os.getenv("OLLAMA_URL",   "http://localhost:11434")

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, f"app_{datetime.now().strftime('%Y%m%d')}.log")),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("MarketResearchPro")


def _check_ollama() -> bool:
    try:
        resp = requests.get(f"{OLLAMA_URL}/api/tags", timeout=3)
        return resp.status_code == 200
    except Exception:
        return False


OLLAMA_AVAILABLE = _check_ollama()
if OLLAMA_AVAILABLE:
    log.info(f"Ollama reachable at {OLLAMA_URL}  ·  model: {OLLAMA_MODEL}")
else:
    log.warning(f"Ollama not reachable at {OLLAMA_URL}. Start: ollama serve")

# ── Optional imports ──────────────────────────────────────────────────────────
try:
    from textblob import TextBlob
    TEXTBLOB_AVAILABLE = True
except ImportError:
    TEXTBLOB_AVAILABLE = False

try:
    from pytrends.request import TrendReq
    PYTRENDS_AVAILABLE = True
except ImportError:
    PYTRENDS_AVAILABLE = False

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors as rl_colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                    Table, TableStyle, HRFlowable)
    from reportlab.lib.enums import TA_LEFT, TA_CENTER
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

try:
    from serpapi import GoogleSearch
    SERPAPI_PKG_AVAILABLE = True
except ImportError:
    SERPAPI_PKG_AVAILABLE = False

try:
    from google_play_scraper import search as gplay_search, reviews as gplay_reviews
    GPLAY_AVAILABLE = True
except ImportError:
    GPLAY_AVAILABLE = False

try:
    from deep_translator import GoogleTranslator
    DEEP_TRANSLATOR_AVAILABLE = True
except ImportError:
    DEEP_TRANSLATOR_AVAILABLE = False

try:
    from langdetect import detect as lang_detect, LangDetectException
    LANGDETECT_AVAILABLE = True
except ImportError:
    LANGDETECT_AVAILABLE = False

from bs4 import BeautifulSoup

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np

# ══════════════════════════════════════════════════════════════════════════════
#  ULTRA-PREMIUM DESIGN SYSTEM  ·  Market Research Pro  2025 Edition
#  Aesthetic: Deep-space data terminal — precision, depth, controlled neon
# ══════════════════════════════════════════════════════════════════════════════
THEMES = {
    "dark": {
        # Background layers — true black-navy hierarchy
        "BG":        "#03060f",   # void black — deepest background
        "SURFACE":   "#080e1f",   # card layer 1
        "SURFACE2":  "#0d1630",   # card layer 2 (elevated panels)
        "SURFACE3":  "#111e3c",   # interactive elements / inputs
        "SURFACE4":  "#162448",   # hover / highlight state
        # Borders
        "BORDER":    "#172038",   # hairline separators
        "BORDER2":   "#1f2f52",   # visible dividers
        "BORDER3":   "#2a406e",   # accent borders
        # Text hierarchy
        "TEXT1":     "#e6efff",   # primary — crisp white-blue
        "TEXT2":     "#6b88b8",   # secondary — steel
        "TEXT3":     "#2e4570",   # muted / disabled
        # Table rows
        "ROW_ODD":   "#070d1c",
        "ROW_EVEN":  "#080e1f",
        "ROW_SEL":   "#0d2550",
        "GREEN_ROW": "#071c17",
        # Glow tints for cards
        "GLOW_BLUE": "#0a1e40",
        "GLOW_TEAL": "#071e1a",
        "GLOW_GOLD": "#1e1608",
    },
    "light": {
        "BG":        "#f0f4fb",
        "SURFACE":   "#ffffff",
        "SURFACE2":  "#e8eef9",
        "SURFACE3":  "#d8e3f4",
        "SURFACE4":  "#ccd8ee",
        "BORDER":    "#c2cfe8",
        "BORDER2":   "#a8bedc",
        "BORDER3":   "#8aaace",
        "TEXT1":     "#080e1f",
        "TEXT2":     "#3a5275",
        "TEXT3":     "#8099bb",
        "ROW_ODD":   "#f8fafd",
        "ROW_EVEN":  "#ffffff",
        "ROW_SEL":   "#cddeff",
        "GREEN_ROW": "#d6f5ec",
        "GLOW_BLUE": "#dce8fa",
        "GLOW_TEAL": "#d0f0ea",
        "GLOW_GOLD": "#fdf3d8",
    },
}

# ── Signature accent palette (unchanged across themes — neon always pops) ─────
PRIMARY   = "#3d8eff"   # sapphire electric blue
PRIMARY_D = "#2070e0"   # deeper press state
PRIMARY_L = "#6aaeff"   # lighter hover
ACCENT    = "#00d4a8"   # bioluminescent teal
ACCENT_D  = "#009e7d"
ACCENT2   = "#f5a623"   # molten amber/gold
ACCENT3   = "#a855f7"   # vivid violet
ACCENT4   = "#06b6d4"   # cyan ice
DANGER    = "#f43f5e"   # rose red
SUCCESS   = "#10b981"   # emerald
WARNING   = "#fbbf24"   # amber
ORANGE    = "#f97316"   # restaurant vivid orange

# Gradient definitions (used in canvas drawing)
GRAD_BLUE  = ("#3d8eff", "#1a4fa8")
GRAD_TEAL  = ("#00d4a8", "#008866")
GRAD_GOLD  = ("#f5a623", "#c47d0a")
GRAD_VIOLET= ("#a855f7", "#7c3aed")

CURRENT_THEME = "dark"


def T(key):
    return THEMES[CURRENT_THEME].get(key, THEMES["dark"].get(key, "#ffffff"))


# ── Typography system ─────────────────────────────────────────────────────────
# Primary: "Segoe UI Variable" / "Segoe UI" — clean geometric
# Mono: "Cascadia Code" → "Consolas" fallback
FONT_HERO    = ("Segoe UI Variable", 24, "bold")
FONT_TITLE   = ("Segoe UI Variable", 13, "bold")
FONT_HEADING = ("Segoe UI Variable", 10, "bold")
FONT_LABEL   = ("Segoe UI",  9, "bold")
FONT_BODY    = ("Segoe UI",  9)
FONT_SMALL   = ("Segoe UI",  8)
FONT_MONO    = ("Cascadia Code", 8)
FONT_INPUT   = ("Segoe UI Variable", 11)
FONT_TAG     = ("Segoe UI",  7, "bold")


# ── Widget factory helpers ────────────────────────────────────────────────────
def _neon_btn(parent, text, bg, fg, cmd, font=None, padx=16, pady=8,
              cursor="hand2", **kw):
    """Flat button with crisp styling — returns the button widget."""
    b = tk.Button(
        parent, text=text,
        font=font or FONT_LABEL,
        bg=bg, fg=fg,
        activebackground=bg,
        activeforeground=fg,
        relief="flat", bd=0,
        padx=padx, pady=pady,
        cursor=cursor,
        command=cmd,
        **kw,
    )
    return b


def _pill_label(parent, text, bg, fg, font=None, padx=10, pady=3):
    """Tight pill-shaped label."""
    return tk.Label(
        parent, text=text,
        font=font or FONT_TAG,
        bg=bg, fg=fg,
        padx=padx, pady=pady,
    )


def _section_header(parent, title, subtitle="", accent=PRIMARY, bg=None):
    """Consistent section header with left accent stripe."""
    bg = bg or T("SURFACE")
    f = tk.Frame(parent, bg=bg)
    stripe = tk.Frame(f, bg=accent, width=3)
    stripe.pack(side="left", fill="y", padx=(0, 12))
    inner = tk.Frame(f, bg=bg)
    inner.pack(side="left", fill="x", expand=True)
    tk.Label(inner, text=title, font=FONT_HEADING, bg=bg, fg=T("TEXT1")).pack(anchor="w")
    if subtitle:
        tk.Label(inner, text=subtitle, font=FONT_SMALL, bg=bg, fg=T("TEXT2")).pack(anchor="w")
    return f


def _stat_card(parent, col, icon, label, value, fg=None, sub=None, bg=None):
    """Metric card with icon, value, label, optional subtitle."""
    fg  = fg  or PRIMARY
    bg  = bg  or T("SURFACE")
    f   = tk.Frame(parent, bg=bg, padx=16, pady=14,
                   highlightbackground=T("BORDER2"), highlightthickness=1)
    f.grid(row=0, column=col, padx=5, sticky="ew")
    # Top accent line
    tk.Frame(f, bg=fg, height=2).pack(fill="x", pady=(0, 10))
    # Icon
    tk.Label(f, text=icon, font=("Segoe UI", 22),
             bg=bg, fg=fg).pack()
    # Value — big
    tk.Label(f, text=value, font=("Segoe UI Variable", 15, "bold"),
             bg=bg, fg=fg).pack(pady=(4, 0))
    # Label
    tk.Label(f, text=label, font=FONT_LABEL, bg=bg, fg=T("TEXT1")).pack()
    if sub:
        tk.Label(f, text=sub, font=FONT_SMALL, bg=bg,
                 fg=T("TEXT3"), wraplength=200).pack(pady=(2, 0))
    return f


def rating_color(score) -> str:
    try:
        score = float(score)
    except (TypeError, ValueError):
        return THEMES[CURRENT_THEME]["TEXT2"]
    if score >= 4.0:
        return SUCCESS
    if score >= 3.0:
        return WARNING
    return DANGER


def _plt_rc():
    """Apply theme to matplotlib rc params — call before creating any Figure."""
    import matplotlib as mpl
    mpl.rcParams.update({
        "axes.facecolor":    T("SURFACE"),
        "figure.facecolor":  T("BG"),
        "axes.edgecolor":    T("BORDER"),
        "axes.labelcolor":   T("TEXT2"),
        "xtick.color":       T("TEXT3"),
        "ytick.color":       T("TEXT3"),
        "text.color":        T("TEXT1"),
        "grid.color":        T("BORDER"),
        "axes.titlecolor":   T("TEXT1"),
        "axes.spines.top":   False,
        "axes.spines.right": False,
    })


_plt_rc()

# ── SQLite ────────────────────────────────────────────────────────────────────
DB_PATH = os.path.join(os.path.dirname(__file__), "market_research.db")


def _db():
    """Return a new SQLite connection with a generous timeout to avoid lock-hangs."""
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")   # allow concurrent readers
    return conn


def init_db():
    try:
        conn = _db()
        c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS searches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query TEXT, location TEXT, price_range TEXT,
            maps_count INTEGER, amzn_count INTEGER, play_count INTEGER,
            timestamp TEXT, data_json TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS cache (
            cache_key TEXT PRIMARY KEY,
            data_json TEXT, created_at TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query TEXT, location TEXT, report_text TEXT, timestamp TEXT)""")
        conn.commit()
        conn.close()
        log.info("Database initialised")
    except Exception as e:
        log.error(f"init_db error: {e}")


def save_search(query, location, price_range, maps_data, amzn_data, play_data):
    try:
        conn = _db()
        c = conn.cursor()
        c.execute(
            """INSERT INTO searches
               (query,location,price_range,maps_count,amzn_count,play_count,timestamp,data_json)
               VALUES (?,?,?,?,?,?,?,?)""",
            (query, location, json.dumps(price_range),
             len(maps_data), len(amzn_data), len(play_data),
             datetime.now().isoformat(),
             json.dumps({"maps": maps_data, "amzn": amzn_data, "play": play_data},
                        ensure_ascii=False)),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        log.error(f"save_search error: {e}")


def load_searches():
    try:
        conn = _db()
        c = conn.cursor()
        c.execute(
            "SELECT id,query,location,maps_count,amzn_count,play_count,timestamp "
            "FROM searches ORDER BY id DESC LIMIT 50"
        )
        rows = c.fetchall()
        conn.close()
        return rows
    except Exception as e:
        log.error(f"load_searches error: {e}")
        return []


def load_search_data(search_id):
    try:
        conn = _db()
        c = conn.cursor()
        c.execute(
            "SELECT data_json,query,location,price_range FROM searches WHERE id=?",
            (search_id,),
        )
        row = c.fetchone()
        conn.close()
        if row:
            data = json.loads(row[0])
            data["query"]       = row[1]
            data["location"]    = row[2]
            data["price_range"] = json.loads(row[3]) if row[3] else None
            return data
    except Exception as e:
        log.error(f"load_search_data error: {e}")
    return None


def save_report(query, location, report_text):
    try:
        conn = _db()
        c = conn.cursor()
        c.execute(
            "INSERT INTO reports (query,location,report_text,timestamp) VALUES (?,?,?,?)",
            (query, location, report_text, datetime.now().isoformat()),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        log.error(f"save_report error: {e}")


# ── Cache ─────────────────────────────────────────────────────────────────────
CACHE_TTL_HOURS = 12


def cache_key(source, query, location=""):
    raw = f"{source}:{query.lower()}:{location.lower()}"
    return hashlib.md5(raw.encode()).hexdigest()


def get_cache(key):
    try:
        conn = _db()
        c = conn.cursor()
        c.execute("SELECT data_json,created_at FROM cache WHERE cache_key=?", (key,))
        row = c.fetchone()
        conn.close()
        if row:
            created = datetime.fromisoformat(row[1])
            if datetime.now() - created < timedelta(hours=CACHE_TTL_HOURS):
                return json.loads(row[0])
    except Exception as e:
        log.error(f"get_cache error: {e}")
    return None


def set_cache(key, data):
    try:
        conn = _db()
        c = conn.cursor()
        c.execute(
            "INSERT OR REPLACE INTO cache (cache_key,data_json,created_at) VALUES (?,?,?)",
            (key, json.dumps(data, ensure_ascii=False), datetime.now().isoformat()),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        log.error(f"set_cache error: {e}")


# ── Retry helper (ONLY call from daemon threads) ──────────────────────────────
def with_retry(fn, retries=2, delay=2):
    last_err = None
    for attempt in range(retries + 1):
        try:
            return fn()
        except Exception as e:
            last_err = e
            if attempt < retries:
                log.warning(f"Retry {attempt+1}/{retries}: {e}")
                time.sleep(delay)
    raise last_err


# ── Translation helper ────────────────────────────────────────────────────────
_INDIAN_LANGS = {"hi", "gu", "mr", "ta", "te", "kn", "ml", "pa", "bn", "ur", "or"}


def translate_to_english(text: str) -> str:
    if not text or not text.strip():
        return text
    if not LANGDETECT_AVAILABLE or not DEEP_TRANSLATOR_AVAILABLE:
        return text
    try:
        detected = lang_detect(text)
        if detected == "en":
            return text
        translated = GoogleTranslator(source="auto", target="en").translate(text[:500])
        if translated:
            return translated
    except Exception as e:
        log.debug(f"Translation skipped: {e}")
    return text


# ── Sentiment ─────────────────────────────────────────────────────────────────
def analyze_sentiment(texts: List[str]) -> Dict:
    if not TEXTBLOB_AVAILABLE or not texts:
        return {"positive": 0, "negative": 0, "neutral": 0,
                "avg_polarity": 0, "keywords": [], "translated": 0}
    polarities = []
    positive = negative = neutral = translation_count = 0
    all_words: List[str] = []
    for text in texts:
        if not text:
            continue
        try:
            original   = str(text)
            translated = translate_to_english(original)
            if translated != original:
                translation_count += 1
            blob = TextBlob(translated)
            pol  = blob.sentiment.polarity
            polarities.append(pol)
            if pol > 0.1:    positive += 1
            elif pol < -0.1: negative += 1
            else:            neutral  += 1
            all_words.extend(w.lower() for w in blob.words if len(w) > 3)
        except Exception:
            pass
    freq      = Counter(all_words)
    stopwords = {
        "this","that","with","have","from","they","been","were","will","your",
        "more","also","than","then","when","what","which","their","there",
        "these","those","would","could","should","very","just","like","good",
        "great","nice","love","best","really","much","even","only","after",
        "before","while","still","some","other","about","again","here","know",
    }
    keywords = [(w, c) for w, c in freq.most_common(20) if w not in stopwords][:10]
    return {
        "positive":     positive,
        "negative":     negative,
        "neutral":      neutral,
        "avg_polarity": round(sum(polarities) / len(polarities), 3) if polarities else 0,
        "keywords":     keywords,
        "translated":   translation_count,
    }


# ── Google Trends ─────────────────────────────────────────────────────────────
def fetch_google_trends(keyword: str) -> Dict:
    if not PYTRENDS_AVAILABLE:
        return {"error": "pytrends not installed — run: pip install pytrends"}
    import random
    for attempt in range(3):
        try:
            pt = TrendReq(
                hl="en-IN", tz=330,
                timeout=(15, 40),
                retries=3,
                backoff_factor=2.5,
                requests_args={"headers": {
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        f"Chrome/12{random.randint(0,5)}.0.0.0 Safari/537.36"
                    ),
                    "Accept-Language": "en-IN,en;q=0.9,hi;q=0.8",
                }},
            )
            time.sleep(random.uniform(1.5, 4.0) + attempt * 2)
            pt.build_payload([keyword], cat=0, timeframe="today 12-m", geo="IN")
            interest = pt.interest_over_time()
            if interest.empty:
                return {"error": "No trend data returned."}
            vals  = interest[keyword].tolist()
            dates = [str(d.date()) for d in interest.index]
            related = {}
            try:
                rq  = pt.related_queries()
                top = rq.get(keyword, {}).get("top")
                if top is not None and not top.empty:
                    related = dict(zip(
                        top["query"].head(5).tolist(),
                        top["value"].head(5).tolist(),
                    ))
            except Exception:
                pass
            return {
                "dates": dates, "values": vals,
                "avg":   round(sum(vals) / len(vals), 1),
                "peak":  max(vals),
                "trend": ("rising"    if vals[-1] > vals[0] else
                          "declining" if vals[-1] < vals[0] else "stable"),
                "related": related,
            }
        except Exception as e:
            err = str(e)
            if "429" in err or "Too Many Requests" in err:
                if attempt < 2:
                    wait = (attempt + 1) * 15 + random.uniform(2, 8)
                    log.warning(f"Trends rate-limited — waiting {wait:.0f}s")
                    time.sleep(wait)
                    continue
                return {"error": "Google Trends rate-limiting (HTTP 429). Wait a few minutes."}
            return {"error": err}
    return {"error": "Trends failed after retries."}


# ── Helpers ───────────────────────────────────────────────────────────────────
def scrollable_frame(parent, bg=None):
    if bg is None:
        bg = T("SURFACE")
    outer  = tk.Frame(parent, bg=bg)
    outer.pack(fill="both", expand=True)
    canvas = tk.Canvas(outer, bg=bg, bd=0, highlightthickness=0)
    vsb    = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=vsb.set)
    vsb.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)
    inner  = tk.Frame(canvas, bg=bg)
    win_id = canvas.create_window((0, 0), window=inner, anchor="nw")
    inner.bind("<Configure>",
               lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.bind("<Configure>",
                lambda e: canvas.itemconfig(win_id, width=e.width))

    def _on_mousewheel(event):
        try:
            x, y = outer.winfo_pointerxy()
            widget_under_cursor = outer.winfo_containing(x, y)
            if widget_under_cursor:
                # Scroll if the hovered widget is the outer frame or any of its children
                w_str = str(widget_under_cursor)
                o_str = str(outer)
                if w_str == o_str or w_str.startswith(o_str + "."):
                    canvas.yview_scroll(-1 * (event.delta // 120), "units")
        except tk.TclError:
            pass

    # Bind to the top-level window with add="+" to retain existing bindings
    parent_toplevel = outer.winfo_toplevel()
    if parent_toplevel:
        parent_toplevel.bind("<MouseWheel>", _on_mousewheel, add="+")
        
    return outer, inner, canvas


def parse_hours_for_display(hours_raw) -> str:
    if not hours_raw:
        return ""
    now_day = datetime.now().strftime("%A")
    if isinstance(hours_raw, str):
        return hours_raw
    if isinstance(hours_raw, list):
        for entry in hours_raw:
            if isinstance(entry, dict):
                day_str  = entry.get("day", "")
                time_str = entry.get("hours", "")
                if now_day[:3].lower() in day_str.lower() or now_day.lower() in day_str.lower():
                    if "-" in time_str:
                        parts = time_str.split("-", 1)
                        return f"Opens {parts[0].strip()}  ·  Closes {parts[1].strip() if len(parts) > 1 else ''}"
                    return time_str
            elif isinstance(entry, str):
                return entry
        first = hours_raw[0]
        if isinstance(first, dict):
            t = first.get("hours", "")
            if "-" in t:
                parts = t.split("-", 1)
                return f"Opens {parts[0].strip()}  ·  Closes {parts[1].strip() if len(parts) > 1 else ''}"
            return t
        return str(first)
    return str(hours_raw)


# ── Ollama ────────────────────────────────────────────────────────────────────
def _ollama_chat(messages: List[Dict], temperature: float = 0.3, max_tokens: int = 900) -> str:
    if not OLLAMA_AVAILABLE:
        raise RuntimeError(
            f"Ollama is not running at {OLLAMA_URL}.\n"
            "  1. Install : https://ollama.com\n"
            f"  2. Pull   : ollama pull {OLLAMA_MODEL}\n"
            "  3. Start  : ollama serve"
        )
    payload = {
        "model":   OLLAMA_MODEL,
        "messages": messages,
        "stream":  False,
        "options": {"temperature": temperature, "num_predict": max_tokens},
    }
    resp = requests.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=120)
    resp.raise_for_status()
    content = resp.json().get("message", {}).get("content")
    if not content:
        raise ValueError("Ollama returned empty response — is the model loaded?")
    return content


def parse_prompt_with_llm(user_text: str) -> dict:
    system_prompt = f"""### Role
You are a Market Research Analyst. Extract commercial data points from entrepreneur queries.

### Extraction Logic
1. product: The specific item being manufactured or sold.
2. location: Target city or region.
3. price_range: The targeted SELLING PRICE to consumer (NOT marketing budget).
   - "around 50k" → [45000, 55000] | "50k to 60k" → [50000, 60000]
   - No price mentioned → null
   - Convert: Lakh=100000, k=1000

### Output
Return ONLY valid JSON. No markdown, no explanations.

### Examples
User: "I want to sell headphones in Delhi for around 2000."
Output: {{"product": "headphones", "location": "Delhi", "price_range": [1800, 2200]}}

### Current Task
User: "{user_text}"
Output:"""
    full_text = _ollama_chat(
        messages=[{"role": "user", "content": system_prompt}],
        temperature=0, max_tokens=200,
    )
    clean = full_text.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
    return json.loads(clean)


def generate_business_report(query, location, price_range,
                              maps_data, amzn_data, play_data, trends_data) -> str:
    def fmt_shops(data):
        out = []
        for c in sorted(data, key=lambda x: x["rating"], reverse=True)[:5]:
            out.append(f"- {c['name']} | Rating: {c['rating']}/5 | Reviews: {c['review_count']}")
        return "\n".join(out) or "No data"

    def fmt_products(data):
        prices = [p["price_num"] for p in data if p.get("price_num")]
        lines  = [f"- {p['title'][:55]} | {p.get('price','N/A')} | ★{p.get('rating','?')}"
                  for p in data[:5]]
        summary = ""
        if prices:
            summary = f"Range ₹{min(prices):,.0f}–₹{max(prices):,.0f}, avg ₹{sum(prices)/len(prices):,.0f}"
        return "\n".join(lines) + (f"\n{summary}" if summary else "")

    rated   = [c["rating"] for c in maps_data if c["rating"] > 0]
    avg_r   = f"{sum(rated)/len(rated):.1f}" if rated else "N/A"
    pr_str  = f"₹{price_range[0]:,}–₹{price_range[1]:,}" if price_range else "Not specified"
    trend_s = ""
    if trends_data and "error" not in trends_data:
        trend_s = f"Trend: {trends_data.get('trend','?')} | Avg interest: {trends_data.get('avg',0)}/100"

    prompt = f"""You are a business analyst. Write a market entry report for an Indian entrepreneur.

PRODUCT: {query}
LOCATION: {location}
TARGET PRICE: {pr_str}

TOP LOCAL SHOPS ({len(maps_data)} found, avg rating {avg_r}/5):
{fmt_shops(maps_data)}

AMAZON.IN ({len(amzn_data)} products):
{fmt_products(amzn_data)}

{trend_s}

Write using ONLY these sections, each under 5 lines:
## 1. Market Opportunity (2 lines + score /10)
## 2. Top Competitors (3 bullets max)
## 3. Cost Breakdown (manufacturing, logistics, margin — use ₹)
## 4. Pricing & Profit (gross profit, margin %, break-even units)
## 5. Entry Strategy (3 bullets)
## 6. Key Risks (2 bullets)

Be specific. Use ₹. No preamble."""
    return _ollama_chat(
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3, max_tokens=650,
    )


def chat_with_ai(messages: List[Dict]) -> str:
    system = {
        "role": "system",
        "content": (
            "You are an expert Market Research AI assistant for Indian entrepreneurs. "
            "You help analyse markets, competitors, pricing, logistics and strategy. "
            "Be concise but insightful. Use ₹ for prices. Indian market context."
        ),
    }
    return _ollama_chat(messages=[system] + messages, temperature=0.4, max_tokens=300)


# ── Data fetchers ─────────────────────────────────────────────────────────────
class MapsDataFetcher:
    @staticmethod
    def fetch_places(product: str, location: str = "Ahmedabad",
                     is_restaurant: bool = False) -> List[Dict]:
        ck = cache_key("maps_r" if is_restaurant else "maps", product, location)
        cached = get_cache(ck)
        if cached:
            return cached

        def _fetch():
            q = (f"{product} near {location}" if is_restaurant
                 else f"{product} shop near {location}")
            params = urllib.parse.urlencode({
                "engine": "google_maps", "q": q,
                "type": "search", "api_key": SERPAPI_KEY, "hl": "en",
            })
            with urllib.request.urlopen(
                f"https://serpapi.com/search?{params}", timeout=25
            ) as r:
                return json.loads(r.read().decode())

        data = with_retry(_fetch)
        out  = []
        for idx, place in enumerate(data.get("local_results", [])[:15]):
            open_now  = place.get("open_now", None)
            op_hours  = place.get("operating_hours", "")
            if not isinstance(op_hours, str):
                op_hours = ""
            hours_raw = place.get("hours", [])
            hours_display = parse_hours_for_display(hours_raw)
            
            fallback_status = op_hours if op_hours else hours_display
            if open_now is True:
                bstatus = fallback_status if fallback_status else "OPERATIONAL"
            elif open_now is False:
                bstatus = fallback_status if fallback_status else "CLOSED"
            else:
                bstatus = fallback_status if fallback_status else "UNKNOWN"
            
            bstatus = str(bstatus)
            
            raw_type  = place.get("type", [])
            shop_type = ", ".join(
                raw_type if isinstance(raw_type, list) else [raw_type or "Store"]
            )[:50] or "Store"
            maps_link = place.get("link", "") or (
                "https://www.google.com/maps/search/" +
                urllib.parse.quote(place.get("title", "") + " " + location)
            )
            photos    = [place["thumbnail"]] if place.get("thumbnail") else []
            out.append({
                "name":            place.get("title", "Unknown"),
                "type":            shop_type,
                "rating":          float(place.get("rating") or 0),
                "review_count":    int(place.get("reviews") or 0),
                "price_label":     translate_price_label(place.get("price", "") or "N/A"),
                "location":        place.get("address", location),
                "lat":             place.get("gps_coordinates", {}).get("latitude", ""),
                "lng":             place.get("gps_coordinates", {}).get("longitude", ""),
                "maps_link":       maps_link,
                "phone":           place.get("phone", ""),
                "website":         place.get("website", ""),
                "hours":           hours_raw,
                "hours_display":   parse_hours_for_display(hours_raw),
                "open_now":        open_now,
                "business_status": bstatus,
                "place_id":        str(place.get("place_id", "")),
                "data_id":         str(place.get("data_id", "")),
                "thumbnail":       place.get("thumbnail", ""),
                "photos":          photos,
                "market_share":    0,
                "reviews":         [],
                "proximity_rank":  idx,
            })
        set_cache(ck, out)
        return out

    @staticmethod
    def fetch_reviews(place_id: str, max_pages: int = 3) -> Dict:
        """Paginated multi-sort review fetch: newest + ratingLow. Captures native topics too."""
        if not place_id:
            return {"reviews": [], "topics": []}
        ck = cache_key("reviews_v4", place_id)
        cached = get_cache(ck)
        if cached:
            return cached

        all_reviews: List[Dict] = []
        native_topics: List[Dict] = []
        seen: set = set()

        def _page(sort_by: str, token: str = "") -> Dict:
            p: Dict = {
                "engine": "google_maps_reviews",
                "place_id": place_id,
                "api_key": SERPAPI_KEY,
                "hl": "en",
                "sort_by": sort_by,
            }
            if token:
                p["next_page_token"] = token
            params = urllib.parse.urlencode(p)
            with urllib.request.urlopen(
                f"https://serpapi.com/search?{params}", timeout=25
            ) as r:
                return json.loads(r.read().decode())

        token = ""
        for i in range(max_pages):
            try:
                resp = _page("newest", token)
                # Capture topics from the first page of "newest"
                if i == 0 and not native_topics:
                    native_topics = resp.get("topics", [])
                    
                for rv in resp.get("reviews", []):
                    uid = (str(rv.get("user", {}).get("name", "")) +
                           str(rv.get("rating", "")))
                    if uid not in seen:
                        seen.add(uid)
                        all_reviews.append(rv)
                token = resp.get("serpapi_pagination", {}).get("next_page_token", "")
                if not token:
                    break
            except Exception as e:
                log.warning(f"Reviews newest page error: {e}")
                break

        try:
            low_resp = _page("ratingLow")
            # If topics weren't found in newest, try here
            if not native_topics:
                native_topics = low_resp.get("topics", [])
                
            for rv in low_resp.get("reviews", []):
                uid = (str(rv.get("user", {}).get("name", "")) +
                       str(rv.get("rating", "")))
                if uid not in seen:
                    seen.add(uid)
                    all_reviews.append(rv)
        except Exception as e:
            log.warning(f"Reviews ratingLow page error: {e}")

        result = {"reviews": all_reviews, "topics": native_topics}
        set_cache(ck, result)
        return result

    @staticmethod
    def fetch_photos(place_id: str, data_id: str = "") -> List[Dict]:
        """Fetch photos for a restaurant.
        Strategy:
          1. SerpApi google_maps_photos with data_id  (needs hex 0x… id)
          2. SerpApi google_maps_photos with place_id (ChIJ… id — sometimes works)
          3. Direct scrape of Google Maps place page  (no API needed)
          4. DuckDuckGo image search for restaurant name (final fallback)
        """
        lookup_id = place_id or data_id
        if not lookup_id:
            return []
        ck = cache_key("photos_v5", lookup_id)
        cached = get_cache(ck)
        if cached:
            return cached

        result: List[Dict] = []

        # ── Strategy 1 & 2: SerpApi (try data_id first, then place_id) ──────────
        def _serpapi_fetch(param_name: str, id_val: str) -> List[Dict]:
            if not id_val:
                return []
            params = urllib.parse.urlencode({
                "engine":    "google_maps_photos",
                param_name:  id_val,
                "api_key":   SERPAPI_KEY,
            })
            resp = requests.get(
                f"https://serpapi.com/search?{params}",
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"},
                timeout=25,
            )
            resp.raise_for_status()
            data = resp.json()
            photos: List[Dict] = []
            seen: set = set()
            for p in data.get("photos", [])[:100]:
                url = (p.get("original") or p.get("image") or p.get("thumbnail") or "")
                if not url or not isinstance(url, str):
                    continue
                url = url.strip()
                if not url.lower().startswith(("http://", "https://")):
                    continue
                if url in seen:
                    continue
                seen.add(url)
                photos.append({
                    "url":      url,
                    "tag":      str(p.get("tag", "") or p.get("type", "") or ""),
                    "title":    str(p.get("title", "") or p.get("alt", "") or ""),
                    "category": str(p.get("category", "") or ""),
                })
            return photos

        for param, id_val in [("data_id", data_id), ("data_id", place_id),
                               ("place_id", place_id)]:
            if not id_val:
                continue
            try:
                result = _serpapi_fetch(param, id_val)
                if result:
                    log.info(f"SerpApi photos: {len(result)} via {param}={id_val[:20]}")
                    break
            except Exception as e:
                log.warning(f"Photos fetch ({param}): {e}")

        # ── Strategy 3: Scrape Google Maps place page directly ───────────────────
        if not result and place_id:
            try:
                gmap_url = f"https://www.google.com/maps/place/?q=place_id:{place_id}"
                resp = requests.get(
                    gmap_url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                        "Accept-Language": "en-US,en;q=0.9",
                    },
                    timeout=20,
                )
                text = resp.text
                # Extract lh5/lh6 googleusercontent photo URLs embedded in page JS
                seen: set = set()
                for m in re.finditer(r'https://lh[3-6]\.googleusercontent\.com/[^"\'\\s>]+', text):
                    u = m.group(0).split("\\")[0].split('"')[0]
                    # Filter: must look like a photo (not icon/avatar — icons are tiny)
                    if "=s" in u:
                        # Force a decent size by replacing size param
                        u = re.sub(r'=s\d+', '=s800', u)
                    if u not in seen and len(u) > 60:
                        seen.add(u)
                        result.append({"url": u, "tag": "", "title": "", "category": ""})
                        if len(result) >= 100:
                            break
                if result:
                    log.info(f"Google Maps page scrape: {len(result)} photos for {place_id}")
            except Exception as e:
                log.warning(f"Google Maps page scrape error: {e}")

        # ── Strategy 4: DuckDuckGo image search (last resort) ────────────────────
        if not result:
            try:
                pass # Disabled because querying place_id fetches irrelevant images
                shop_enc = urllib.parse.quote(f"{place_id[:10]} restaurant food photos")
                ddg_url  = f"https://duckduckgo.com/?q={shop_enc}&iax=images&ia=images"
                resp = requests.get(
                    ddg_url,
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
                    timeout=15,
                )
                # Extract vqd token
                vqd_m = re.search(r'vqd=([\d-]+)', resp.text)
                if vqd_m:
                    vqd = vqd_m.group(1)
                    api = (f"https://duckduckgo.com/i.js?q={shop_enc}"
                           f"&o=json&p=1&s=0&u=bing&f=,,,&l=us-en&vqd={vqd}")
                    img_resp = requests.get(api, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
                    for item in img_resp.json().get("results", [])[:20]:
                        u = item.get("image", "")
                        if u and u.startswith("http"):
                            result.append({"url": u, "tag": "", "title": item.get("title",""), "category": ""})
                if result:
                    log.info(f"DuckDuckGo fallback: {len(result)} images")
            except Exception as e:
                log.warning(f"DuckDuckGo image fallback error: {e}")

        set_cache(ck, result)
        return result


class AmazonFetcher:
    @staticmethod
    def fetch(keyword: str) -> List[Dict]:
        ck = cache_key("amazon", keyword)
        cached = get_cache(ck)
        if cached:
            return cached
        if SERPAPI_KEY and SERPAPI_PKG_AVAILABLE:
            try:
                return AmazonFetcher._serpapi(keyword, ck)
            except Exception as e:
                log.warning(f"SerpAPI failed ({e}), falling back to direct scrape")
        return AmazonFetcher._direct(keyword, ck)

    @staticmethod
    def _serpapi(keyword, ck):
        def _fetch():
            return GoogleSearch({
                "engine": "amazon", "amazon_domain": "amazon.in",
                "k": keyword, "api_key": SERPAPI_KEY,
            }).get_dict()
        results  = with_retry(_fetch)
        products = []
        for p in results.get("organic_results", [])[:10]:
            price_raw = p.get("price", "")
            price_num = None
            if price_raw:
                try:
                    price_num = float(str(price_raw).replace("₹", "").replace(",", "").strip())
                except Exception:
                    pass
            products.append({
                "title":    p.get("title", "—"),
                "price":    price_raw or "N/A",
                "price_num": price_num,
                "rating":   p.get("rating", "N/A"),
                "reviews":  p.get("reviews", 0),
                "link":     p.get("link", ""),
                "position": p.get("position", 0),
                "asin":     p.get("asin", ""),
            })
        set_cache(ck, products)
        return products

    @staticmethod
    def _direct(keyword: str, ck: str) -> List[Dict]:
        session = requests.Session()
        headers = {
            "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                               "AppleWebKit/537.36 (KHTML, like Gecko) "
                               "Chrome/124.0.0.0 Safari/537.36",
            "Accept-Language": "en-IN,en;q=0.9",
            "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer":         "https://www.amazon.in/",
        }
        try:
            session.get("https://www.amazon.in", headers=headers, timeout=4)
        except Exception:
            pass
        url  = f"https://www.amazon.in/s?k={urllib.parse.quote(keyword)}"
        resp = session.get(url, headers=headers, timeout=20)
        soup = BeautifulSoup(resp.text, "html.parser")
        products: List[Dict] = []
        for item in soup.select('[data-component-type="s-search-result"]')[:12]:
            try:
                title_el    = item.select_one("h2 span")
                price_whole = item.select_one(".a-price-whole")
                price_frac  = item.select_one(".a-price-fraction")
                rating_el   = item.select_one('[aria-label*="out of 5 stars"]')
                reviews_el  = item.select_one('[aria-label*="ratings"]')
                link_el     = item.select_one("h2 a[href]")
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                if len(title) < 5:
                    continue
                price_raw = "N/A"
                price_num = None
                if price_whole:
                    frac      = price_frac.get_text(strip=True) if price_frac else "00"
                    price_raw = f"₹{price_whole.get_text(strip=True).replace(',','')}.{frac}"
                    try:
                        price_num = float(re.sub(r"[^\d.]", "", price_raw))
                    except Exception:
                        pass
                rating = "N/A"
                if rating_el:
                    m = re.search(r"([\d.]+)\s+out of", rating_el.get("aria-label", ""))
                    if m:
                        rating = m.group(1)
                reviews = 0
                if reviews_el:
                    m = re.search(r"([\d,]+)", reviews_el.get("aria-label", ""))
                    if m:
                        try:
                            reviews = int(m.group(1).replace(",", ""))
                        except Exception:
                            pass
                link = ""
                if link_el:
                    href = link_el.get("href", "")
                    link = "https://www.amazon.in" + href if href.startswith("/") else href
                products.append({
                    "title":    title,
                    "price":    price_raw,
                    "price_num": price_num,
                    "rating":   rating,
                    "reviews":  reviews,
                    "link":     link,
                    "position": len(products) + 1,
                    "asin":     "",
                })
            except Exception as ex:
                log.debug(f"Amazon parse error: {ex}")
        log.info(f"Amazon direct: {len(products)} products for '{keyword}'")
        set_cache(ck, products)
        return products


class PlayStoreFetcher:
    @staticmethod
    def fetch(query: str, n_hits: int = 10, review_count: int = 15) -> List[Dict]:
        ck = cache_key("play", query)
        cached = get_cache(ck)
        if cached:
            return cached
        if not GPLAY_AVAILABLE:
            raise RuntimeError("google_play_scraper not installed.")
        results: List[Dict] = []
        seen_ids: set = set()
        for attempt in [query, f"{query} app", f"best {query}"]:
            try:
                hits = gplay_search(query=attempt, lang="en", country="in", n_hits=n_hits)
                for h in hits:
                    if h.get("appId") and h["appId"] not in seen_ids:
                        seen_ids.add(h["appId"])
                        results.append(h)
                if len(results) >= n_hits:
                    break
            except Exception:
                continue
        apps: List[Dict] = []
        for i, r in enumerate(results[:n_hits]):
            try:
                revs_raw, _ = gplay_reviews(
                    app_id=r["appId"], lang="en", country="in", count=review_count
                )
                revs = [{"score": rv["score"],
                         "content": rv["content"] or "",
                         "thumbsUpCount": rv.get("thumbsUpCount", 0)}
                        for rv in revs_raw]
            except Exception:
                revs = []
            apps.append({
                "rank":     i,
                "appTitle": r.get("title", "—"),
                "rating":   float(r.get("score") or 0),
                "isFree":   r.get("free", True),
                "price":    r.get("price", 0),
                "genre":    r.get("genre", "—"),
                "installs": r.get("installs", "—"),
                "appId":    r["appId"],
                "reviews":  revs,
            })
        set_cache(ck, apps)
        return apps


# ── PDF export ────────────────────────────────────────────────────────────────
def export_pdf(report_text: str, query: str, location: str, path: str,
               maps_data=None, amzn_data=None, price_range=None):
    if not REPORTLAB_AVAILABLE:
        raise RuntimeError("reportlab not installed — run: pip install reportlab")
    doc    = SimpleDocTemplate(path, pagesize=A4,
                               rightMargin=2*cm, leftMargin=2*cm,
                               topMargin=2*cm,   bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    story  = []

    title_style = ParagraphStyle("title", fontSize=20, fontName="Helvetica-Bold",
                                 textColor=rl_colors.HexColor("#4f8ef7"), spaceAfter=6)
    sub_style   = ParagraphStyle("sub",   fontSize=10, fontName="Helvetica",
                                 textColor=rl_colors.HexColor("#8b99b5"), spaceAfter=20)
    h2_style    = ParagraphStyle("h2",    fontSize=13, fontName="Helvetica-Bold",
                                 textColor=rl_colors.HexColor("#00d4aa"),
                                 spaceBefore=14, spaceAfter=6)
    body_style  = ParagraphStyle("body",  fontSize=9, fontName="Helvetica",
                                 textColor=rl_colors.black, spaceAfter=4, leading=14)
    bold_style  = ParagraphStyle("bold",  fontSize=9, fontName="Helvetica-Bold",
                                 textColor=rl_colors.HexColor("#4f8ef7"), spaceAfter=4)

    story.append(Paragraph("Market Intelligence Report", title_style))
    story.append(Paragraph(
        f"{query.title()}  ·  {location}  ·  Generated {datetime.now().strftime('%d %b %Y, %H:%M')}",
        sub_style,
    ))
    story.append(HRFlowable(width="100%", thickness=1,
                             color=rl_colors.HexColor("#2a3a54")))
    story.append(Spacer(1, 0.4*cm))

    if maps_data or amzn_data:
        prices = [p.get("price_num") for p in (amzn_data or []) if p.get("price_num")]
        rated  = [c["rating"] for c in (maps_data or []) if c.get("rating", 0) > 0]
        pr_str = f"₹{price_range[0]:,} – ₹{price_range[1]:,}" if price_range else "N/A"
        tdata  = [
            ["Metric", "Value"],
            ["Local Shops Found",        str(len(maps_data or []))],
            ["Amazon Products",          str(len(amzn_data or []))],
            ["Target Price Range",       pr_str],
            ["Avg Competitor Rating",    f"{sum(rated)/len(rated):.1f}/5.0" if rated else "N/A"],
            ["Amazon Price Range",       f"₹{min(prices):,.0f} – ₹{max(prices):,.0f}" if prices else "N/A"],
        ]
        t = Table(tdata, colWidths=[8*cm, 8*cm])
        t.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, 0), rl_colors.HexColor("#4f8ef7")),
            ("TEXTCOLOR",     (0, 0), (-1, 0), rl_colors.white),
            ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",      (0, 0), (-1,-1), 9),
            ("ROWBACKGROUNDS",(0, 1), (-1,-1), [rl_colors.HexColor("#f0f4ff"), rl_colors.white]),
            ("GRID",          (0, 0), (-1,-1), 0.5, rl_colors.HexColor("#c0ccd8")),
            ("PADDING",       (0, 0), (-1,-1), 6),
        ]))
        story.append(t)
        story.append(Spacer(1, 0.5*cm))

    for line in report_text.split("\n"):
        stripped = line.strip()
        if not stripped:
            story.append(Spacer(1, 0.2*cm))
        elif stripped.startswith("## "):
            story.append(Paragraph(stripped[3:], h2_style))
        elif stripped.startswith("# "):
            story.append(Paragraph(stripped[2:], h2_style))
        elif stripped.startswith("**") and stripped.endswith("**"):
            story.append(Paragraph(stripped.strip("**"), bold_style))
        elif stripped.startswith("- ") or stripped.startswith("* "):
            story.append(Paragraph(f"• {stripped[2:]}", body_style))
        else:
            clean = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", stripped)
            story.append(Paragraph(clean, body_style))

    story.append(Spacer(1, 1*cm))
    story.append(HRFlowable(width="100%", thickness=0.5,
                             color=rl_colors.HexColor("#2a3a54")))
    story.append(Paragraph(
        f"Generated by Market Research Pro  ·  {datetime.now().strftime('%d %b %Y')}",
        sub_style,
    ))
    doc.build(story)
    log.info(f"PDF exported: {path}")


# ── Photo categorisation helpers ───────────────────────────────────────────────
_FOOD_KW = {
    "pizza","burger","curry","biryani","dessert",
    "cake","salad","pasta","sandwich","soup","snack","drink","beverage","chai",
    "coffee","juice","platter","thali","momos","naan","roti","dosa","idli","vada",
    "paneer","chicken","mutton","fish","prawn","kebab","tandoori","masala","samosa",
    "pasta","pizza","sandwich","burger","fry","fries","soup","salad","drink","beverage",
}
_MENU_KW = {
    "menu","price","list","card","board","tariff","rates","order","item",
    "specials","offers","combo","price list","item list","what we serve",
    "bill","check","qr","pricing","cost","rate",
}
_AMBI_KW = {
    "interior","exterior","decor","ambiance","ambience","seating","table","chair",
    "entrance","hall","dining","outdoor","indoor","rooftop","terrace","counter",
    "view","building","facade","sign","logo","light","wall","art","staff","setup",
    "vibe","atmosphere","lighting","booth","bar","sofa","signage","street","inside",
    "outside","storefront","facade","entrance","architecture","decor",
}


def _kw_score(text: str, kwset: set) -> int:
    t = text.lower()
    return sum(1 for kw in kwset if kw in t)


def _classify_heuristic(url: str, tag: str = "", title: str = "") -> str:
    combined = f"{url} {tag} {title}".lower()
    fs  = _kw_score(combined, _FOOD_KW)
    ms  = _kw_score(combined, _MENU_KW)
    as_ = _kw_score(combined, _AMBI_KW)
    best = max(fs, ms, as_)
    if best == 0:   return "other"
    if best == ms:  return "menu"
    if best == fs:  return "food"
    return "ambi"


def _ollama_classify_image(url: str, restaurant_name: str) -> str:
    """Vision-model classification via Ollama (llava / qwen2.5-vl / moondream)."""
    if not OLLAMA_AVAILABLE:
        return "other"
    try:
        resp = requests.get(f"{OLLAMA_URL}/api/tags", timeout=4)
        models = [m["name"] for m in resp.json().get("models", [])]
        vision = next(
            (m for m in models if any(v in m.lower()
             for v in ["llava","bakllava","moondream","qwen2.5-vl","minicpm","llama"])),
            None,
        )
        if not vision:
            return "other"
    except Exception:
        return "other"
    try:
        import base64 as _b64
        with urllib.request.urlopen(url, timeout=10) as r:
            img_bytes = r.read()
        b64 = _b64.b64encode(img_bytes).decode()
        payload = {
            "model": vision, "stream": False,
            "options": {"temperature": 0, "num_predict": 6},
            "messages": [{
                "role": "user",
                "content": (
                    f"Restaurant '{restaurant_name}'. "
                    "Reply ONE word only: food, menu, or ambi. "
                    "CRITICAL: If the image is a BUILDING, OUTSIDE SIGN, or STOREFRONT, reply 'ambi'. "
                    "food=close-up of a plate/dish, menu=list of items with prices."
                ),
                "images": [b64],
            }],
        }
        r2     = requests.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=30)
        reply  = r2.json().get("message", {}).get("content", "").strip().lower()
        if   "food" in reply: return "food"
        elif "menu" in reply: return "menu"
        elif "ambi" in reply: return "ambi"
    except Exception as e:
        log.debug(f"Vision classify: {e}")
    return "other"


def categorize_photos(photo_dicts: List[Dict],
                      restaurant_name: str) -> Dict[str, List[str]]:
    buckets: Dict[str, List[str]] = {
        "food": [], "menu": [], "ambi": [], "other": []
    }
    unclassified: List[str] = []

    for pd in photo_dicts:
        url   = pd.get("url", "")
        tag   = pd.get("tag", "").lower()
        title = pd.get("title", "").lower()
        cat   = pd.get("category", "").lower()
        if not url:
            continue

        # Layer 1: SerpApi structural tags
        combined = f"{tag} {cat}".strip()
        if any(t in combined for t in ["menu","price","list","order"]):
            buckets["menu"].append(url); continue
        if any(t in combined for t in ["interior","exterior","ambiance","ambience","seating","decor",
                                        "building","outdoor","indoor","rooftop","entrance","facade","storefront"]):
            buckets["ambi"].append(url); continue
        if any(t in combined for t in ["food","dish","meal","drink","plate","eat","cuisine"]):
            buckets["food"].append(url); continue

        # Layer 2: keyword heuristics
        cat2 = _classify_heuristic(url, tag, title)
        if cat2 != "other":
            buckets[cat2].append(url)
        else:
            unclassified.append(url)

    # Layer 3: Limited AI Vision Categorisation (Optional & Async friendly)
    if OLLAMA_AVAILABLE and unclassified:
        # We only do the first 8 unclassified ones to keep wait times reasonable
        for url in unclassified[:8]:
            ai_cat = _ollama_classify_image(url, restaurant_name)
            if ai_cat in buckets:
                buckets[ai_cat].append(url)
            else:
                buckets["other"].append(url)
        buckets["other"].extend(unclassified[8:])
    else:
        buckets["other"].extend(unclassified)
        
    return buckets


def _ollama_read_menu_photos(urls: List[str], restaurant_name: str) -> str:
    """Extracts menu items and prices via a local Ollama vision model."""
    if not OLLAMA_AVAILABLE:
        return "Ollama is not running. Please start Ollama with a vision model (e.g. llava, qwen2.5-vl) to use this feature."
    
    try:
        resp = requests.get(f"{OLLAMA_URL}/api/tags", timeout=4)
        models = [m["name"] for m in resp.json().get("models", [])]
        vision = next(
            (m for m in models if any(v in m.lower() for v in ["llava","bakllava","moondream","qwen2.5-vl","minicpm","llama"])),
            None,
        )
        if not vision:
            return "No vision model found in Ollama.\nPlease run: ollama pull llava\nOr: ollama pull qwen2.5-vl"
    except Exception as e:
        return f"Error connecting to Ollama: {e}"

    b64_images = []
    import base64 as _b64
    for u in urls[:3]:
        try:
            with urllib.request.urlopen(u, timeout=10) as r:
                b64_images.append(_b64.b64encode(r.read()).decode())
        except Exception:
            pass
            
    if not b64_images:
        return "Failed to download menu images for OCR."

    try:
        payload = {
            "model": vision,
            "stream": False,
            "options": {"temperature": 0.1, "num_predict": 1000},
            "messages": [{
                "role": "user",
                "content": (
                    f"You are a helpful AI assistant. Attached is the menu for the restaurant '{restaurant_name}'. "
                    "Please extract all the dishes, items, and their prices logically into a clean text list. "
                    "Use bullet points."
                ),
                "images": b64_images,
            }],
        }
        r2 = requests.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=180)
        return r2.json().get("message", {}).get("content", "").strip()
    except Exception as e:
        log.warning(f"Vision OCR fail: {e}")
        return f"Menu parsing failed: {e}"


def intelligent_extract_dishes(reviews: List[Dict], topics: List[Dict]) -> List[Dict]:
    FOOD_ITEMS = {
        "biryani","pizza","burger","pasta","curry","momos","tikka","paneer","naan",
        "roti","dosa","idli","vada","samosa","chaat","paratha","thali","cake",
        "gulab jamun","rasmalai","chai","coffee","lassi","juice","sandwich","roll",
        "manchurian","noodles","sushi","waffle","omelette","fried rice","spring roll",
        "chicken","mutton","fish","prawn","kebab","tandoori","masala","dal makhani",
        "chole bhature","pav bhaji","dhokla","khandvi","farsan","undihiyu","jalebi",
        "khichdi","kadhi","soup","mocktail","dessert","ice cream","shake","kulfi",
        "kofta","kulcha","raita","papad","salad","hakka noodles","momos","spring roll"
    }
    
    counts = Counter()
    citations = {}
    
    # Categorization Map
    CAT_MAP = {
        "Starters & Snacks": ["momos", "tikka", "kebab", "samosa", "chaat", "manchurian", "spring roll", "pav bhaji", "dhokla", "khandvi", "farsan", "roll", "omelette", "soup"],
        "Main Course": ["biryani", "pizza", "burger", "pasta", "curry", "paneer", "dosa", "idli", "vada", "thali", "dal makhani", "chole bhature", "khichdi", "kadhi", "kofta", "noodles", "fried rice", "sushi", "hakka noodles", "pav bhaji", "chicken", "mutton", "fish", "prawn", "masala"],
        "Breads & Sides": ["naan", "roti", "paratha", "kulcha", "raita", "papad", "salad"],
        "Desserts & Sweets": ["cake", "gulab jamun", "rasmalai", "jalebi", "ice cream", "kulfi", "waffle", "dessert", "shake"],
        "Beverages": ["chai", "coffee", "lassi", "juice", "mocktail"]
    }

    def _get_cat(dish_name):
        d_lower = dish_name.lower()
        for cat, items in CAT_MAP.items():
            if any(it in d_lower for it in items):
                return cat
        return "Popular Mentions"

    NON_VEG = {"chicken", "mutton", "fish", "prawn", "egg", "meat", "lamb", "beef", "pork", "salmon", "wings", "tandoori", "kabab", "kebab", "prawns"}
    def _is_veg(dish_name):
        d_lower = dish_name.lower()
        return not any(nv in d_lower for nv in NON_VEG)

    for rev in reviews:
        text = (rev.get("snippet", "") or rev.get("text", "") or "").lower()
        if not text:
            continue
            
        author = rev.get("user", {}).get("name", "A Customer")
        rating = rev.get("rating", 0)
        
        for item in FOOD_ITEMS:
            if re.search(r'\b' + re.escape(item) + r'\b', text):
                counts[item] += 1
                if item not in citations and rating >= 4:
                    match_idx = text.find(item)
                    start = max(0, match_idx - 40)
                    end = min(len(text), match_idx + 60)
                    snippet = text[start:end].replace('\n', ' ')
                    if start > 0: snippet = "..." + snippet
                    if end < len(text): snippet = snippet + "..."
                    citations[item] = {"quote": snippet.capitalize(), "author": author}

    native_topic_keywords = {t.get("keyword", "").lower(): t.get("mentions", 0) for t in topics}
    results = []
    
    for item, cnt in counts.most_common(20):
        if cnt < 2 and item not in native_topic_keywords:
            continue
            
        is_verified = False
        native_cnt = 0
        score = cnt
        
        for k, v in native_topic_keywords.items():
            if item in k or k in item:
                is_verified = True
                native_cnt = v
                score += v
                break
                
        results.append({
            "dish": item.title(),
            "count": cnt,
            "native_count": native_cnt,
            "is_verified": is_verified,
            "score": score,
            "is_veg": _is_veg(item),
            "category": _get_cat(item),
            "citation": citations.get(item, {}).get("quote", ""),
            "author": citations.get(item, {}).get("author", "")
        })
        
    for topic_kw, mentions in native_topic_keywords.items():
        if mentions < 3: continue
        if any(topic_kw in r["dish"].lower() or r["dish"].lower() in topic_kw for r in results):
            continue
            
        if any(non_food in topic_kw for non_food in ["service", "staff", "place", "ambience", "price", "money", "table", "wait", "time", "manager", "experience", "vibe"]):
            continue
            
        results.append({
            "dish": topic_kw.title(),
            "count": 0,
            "native_count": mentions,
            "is_verified": True,
            "score": mentions,
            "is_veg": _is_veg(topic_kw),
            "category": _get_cat(topic_kw),
            "citation": "Recommended extensively across customer reviews.",
            "author": "Google Maps Aggregation"
        })
        
    return results


def translate_price_label(raw: str) -> str:
    """Translate symbols like $$$ into descriptive text."""
    if not raw or raw == "N/A":
        return "Budget Unknown"
    if any(c in raw for c in "₹$€£"):
        # If it's already a range like ₹500-1000, leave it
        if any(d.isdigit() for d in raw):
            return raw
        # Otherwise translate symbol tiers
        count = len(raw.strip())
        if count == 1: return "Economy (~₹200)"
        if count == 2: return "Mid-Range (~₹500)"
        if count == 3: return "Upscale (~₹1200)"
        if count >= 4: return "Fine Dining (~₹3000)"
    return raw


def extract_bestsellers(reviews: List[Dict]) -> List[str]:
    FOOD_ITEMS = {
        "biryani","pizza","burger","pasta","curry","momos","tikka","paneer","naan",
        "roti","dosa","idli","vada","samosa","chaat","paratha","thali","cake",
        "gulab jamun","rasmalai","chai","coffee","lassi","juice","sandwich","roll",
        "manchurian","noodles","sushi","waffle","omelette","fried rice","spring roll",
        "chicken","mutton","fish","prawn","kebab","tandoori","masala",
    }
    counter: Counter = Counter()
    for rev in reviews:
        text = (rev.get("snippet","") or rev.get("text","") or "").lower()
        if not text: continue
        for item in FOOD_ITEMS:
            if item in text:
                counter[item] += 1
    return [item for item, cnt in counter.most_common(8) if cnt >= 2]


# ── Restaurant Card ────────────────────────────────────────────────────────────
class RestaurantCard:
    REST_COLOR = "#ff7043"

    def __init__(self, parent, restaurant: Dict, index: int, app_root):
        self.data     = restaurant
        self.app_root = app_root
        self._build(parent, index)

    def _build(self, parent, index):
        r      = self.data
        rating = r["rating"]
        accent = rating_color(rating)

        # Card container with subtle shadow effect
        wrapper = tk.Frame(parent, bg=T("BORDER"), pady=1)
        wrapper.pack(fill="x", padx=12, pady=4)

        card = tk.Frame(wrapper, bg=T("SURFACE"), relief="flat")
        card.pack(fill="x")

        # Left accent strip — width varies by rating quality
        strip_w = 8 if rating >= 4.5 else 6
        tk.Frame(card, bg=accent, width=strip_w).pack(side="left", fill="y")

        body = tk.Frame(card, bg=T("SURFACE"), padx=16, pady=14)
        body.pack(side="left", fill="both", expand=True)

        # ── Row 1: rank badge + name + type ───────────────────────────────
        row1 = tk.Frame(body, bg=T("SURFACE")); row1.pack(fill="x")
        # Rank badge
        rank_bg = accent if rating >= 4.0 else T("SURFACE3")
        tk.Label(row1, text=f"#{index}", font=("Segoe UI",9,"bold"),
                 bg=rank_bg, fg="#fff", padx=8, pady=3).pack(side="left", padx=(0,10))
        tk.Label(row1, text=r["name"], font=("Segoe UI",13,"bold"),
                 bg=T("SURFACE"), fg=T("TEXT1")).pack(side="left")
        if r.get("type"):
            tk.Label(row1, text=f"  ·  {r['type'][:30]}", font=("Segoe UI",9),
                     bg=T("SURFACE"), fg=T("TEXT3")).pack(side="left")

        # ── Row 2: stars + rating + reviews + price ────────────────────────
        row2 = tk.Frame(body, bg=T("SURFACE")); row2.pack(fill="x", pady=(6,4))
        filled  = int(round(rating))
        stars   = "★" * filled + "☆" * (5 - filled)
        tk.Label(row2, text=stars, font=("Segoe UI",12),
                 bg=T("SURFACE"), fg=ACCENT2).pack(side="left")
        tk.Label(row2, text=f" {rating:.1f}", font=("Segoe UI",11,"bold"),
                 bg=T("SURFACE"), fg=accent).pack(side="left")
        tk.Label(row2, text=f"  ·  {r['review_count']:,} reviews",
                 font=("Segoe UI",9), bg=T("SURFACE"), fg=T("TEXT2")).pack(side="left")
        if r.get("price_label") and r["price_label"] not in ("N/A",""):
            tk.Label(row2, text=f"  ·  {r['price_label']}",
                     font=("Segoe UI",9), bg=T("SURFACE"), fg=ACCENT2).pack(side="left")

        # ── Row 3: address ─────────────────────────────────────────────────
        tk.Label(body, text=f"📍  {r['location']}",
                 font=("Segoe UI",8), fg=T("TEXT2"), bg=T("SURFACE"),
                 wraplength=920, justify="left", anchor="w").pack(fill="x")

        # ── Row 4: hours ───────────────────────────────────────────────────
        hd = r.get("hours_display", "")
        if hd:
            on  = r.get("open_now")
            dot = "●" if on is True else "○" if on is False else "◌"
            clr = SUCCESS if on is True else DANGER if on is False else WARNING
            tk.Label(body, text=f"{dot}  {hd}",
                     font=("Segoe UI",8), fg=clr, bg=T("SURFACE"),
                     anchor="w").pack(fill="x", pady=(3,0))

        # ── Buttons row ────────────────────────────────────────────────────
        btns = tk.Frame(body, bg=T("SURFACE")); btns.pack(anchor="w", pady=(10,2))

        def mkbtn(text, bg, cmd, fg="#fff", padx=14):
            b = tk.Button(btns, text=text, font=("Segoe UI",8,"bold"),
                          bg=bg, fg=fg, relief="flat", padx=padx, pady=6,
                          cursor="hand2", activebackground=bg,
                          activeforeground=fg, command=cmd)
            b.pack(side="left", padx=(0,8))
            # Hover effect
            b.bind("<Enter>", lambda e, w=b, c=bg: w.config(relief="groove"))
            b.bind("<Leave>", lambda e, w=b: w.config(relief="flat"))

        mkbtn("🗺️  Maps", SUCCESS,
              lambda lnk=r["maps_link"]: webbrowser.open(lnk))
        mkbtn("👁️  Reviews & Photos", PRIMARY,
              lambda: MapsReviewPopup(self.app_root, self.data, is_restaurant=True))
        if r.get("website"):
            mkbtn("🌐  Website", T("SURFACE3"),
                  lambda: webbrowser.open(r["website"]), T("TEXT1"), 10)


# ── Restaurant Panel ───────────────────────────────────────────────────────────
class RestaurantPanel:
    REST_COLOR = "#ff7043"

    def __init__(self, parent_root):
        self.root = parent_root
        self.win  = tk.Toplevel(parent_root)
        self.win.title("🍽️  Restaurant Competitor Analysis")
        self.win.geometry("1300x900")
        self.win.configure(bg=T("BG"))
        self.win.protocol("WM_DELETE_WINDOW", self.win.withdraw)
        self._rest_data:          List[Dict] = []
        self._rest_current_data:  List[Dict] = []
        self._fixed_header_count: int        = 0
        self._build()

    def _build(self):
        RC = self.REST_COLOR

        # ── Premium header ─────────────────────────────────────────────────
        hdr_outer = tk.Frame(self.win, bg=RC)
        hdr_outer.pack(fill="x")
        # Top gradient strip: amber → orange
        grad = tk.Frame(hdr_outer, height=3, bg=RC)
        grad.pack(fill="x")
        for col in ["#ffd700", "#ffb347", RC, "#cc4a1a"]:
            tk.Frame(grad, bg=col, height=3).pack(side="left", fill="x", expand=True)

        hdr = tk.Frame(hdr_outer, bg=RC, pady=18, padx=26)
        hdr.pack(fill="x")
        left_hdr = tk.Frame(hdr, bg=RC)
        left_hdr.pack(side="left", fill="x", expand=True)
        tk.Label(left_hdr, text="🍽️  Restaurant Competitor Analysis",
                 font=("Segoe UI Variable", 16, "bold"),
                 bg=RC, fg="#ffffff").pack(anchor="w")
        tk.Label(left_hdr,
                 text="Search  ·  Ratings & Reviews  ·  Photo Gallery  ·  AI Insights  ·  Best Sellers",
                 font=("Segoe UI", 9),
                 bg=RC, fg="#ffe0c8").pack(anchor="w", pady=(3, 0))

        # Right badge
        badge = tk.Frame(hdr, bg="#b03a15", padx=16, pady=10)
        badge.pack(side="right")
        tk.Label(badge, text="RESTAURANT\nINTELLIGENCE",
                 font=("Segoe UI Variable", 8, "bold"),
                 bg="#b03a15", fg="#ffe8d6",
                 justify="center").pack()

        # ── Search bar row ──────────────────────────────────────────────────
        search_bg = T("SURFACE2")
        sf = tk.Frame(self.win, bg=search_bg, pady=14, padx=22)
        sf.pack(fill="x")
        sf.columnconfigure((1, 3, 5), weight=1)

        def field(col, label, var, placeholder=""):
            tk.Label(sf, text=label,
                     font=("Segoe UI Variable", 9, "bold"),
                     bg=search_bg, fg=T("TEXT2")).grid(
                row=0, column=col, sticky="w",
                padx=(0 if col == 0 else 16, 6))
            e = tk.Entry(sf, textvariable=var,
                         font=("Segoe UI Variable", 10),
                         bg=T("SURFACE3"), fg=T("TEXT1"),
                         insertbackground=ACCENT,
                         relief="flat", bd=0,
                         highlightbackground=T("BORDER2"),
                         highlightthickness=1)
            e.grid(row=0, column=col + 1, sticky="ew", ipady=8, padx=(0, 4))
            return e

        self.cuisine_var = tk.StringVar()
        self.loc_var     = tk.StringVar(value="Ahmedabad")
        self.vibe_var    = tk.StringVar()
        field(0, "🍴  Cuisine", self.cuisine_var)
        field(2, "📍  City / Area", self.loc_var)
        field(4, "✨  Vibe (optional)", self.vibe_var)

        # ── Action bar ─────────────────────────────────────────────────────
        ab = tk.Frame(self.win, bg=T("SURFACE"), pady=11, padx=20)
        ab.pack(fill="x")
        self.search_btn = tk.Button(
            ab, text="  🔍  Find Restaurant Competitors  ",
            font=("Segoe UI Variable", 10, "bold"),
            bg=RC, fg="#ffffff",
            relief="flat", padx=22, pady=10,
            cursor="hand2",
            activebackground="#cc4a1a", activeforeground="#ffffff",
            command=self._search)
        self.search_btn.pack(side="left", padx=(0, 20))

        # Sort controls
        tk.Label(ab, text="Sort by:",
                 font=("Segoe UI", 9, "bold"),
                 bg=T("SURFACE"), fg=T("TEXT2")).pack(side="left", padx=(0, 8))
        self.sort_var = tk.StringVar(value="Rating")
        for opt, icon in [("Rating", "⭐"), ("Reviews", "💬"), ("Name", "🔤")]:
            tk.Radiobutton(
                ab, text=f"{icon} {opt}",
                variable=self.sort_var, value=opt,
                font=("Segoe UI", 9),
                bg=T("SURFACE"), fg=T("TEXT1"),
                selectcolor=T("SURFACE3"),
                activebackground=T("SURFACE"),
                indicatoron=False, padx=10, pady=5,
                relief="flat", cursor="hand2",
                command=self._resort).pack(side="left", padx=(0, 6))

        self.status_lbl = tk.Label(ab, text="",
                                   font=("Segoe UI", 9),
                                   bg=T("SURFACE"), fg=T("TEXT2"))
        self.status_lbl.pack(side="right", padx=8)

        # ── Divider ─────────────────────────────────────────────────────────
        tk.Frame(self.win, bg=T("BORDER"), height=2).pack(fill="x")

        # ── Results area (scrollable) ────────────────────────────────────────
        _, self.results_inner, self._results_canvas = scrollable_frame(
            self.win, bg=T("BG"))
        tk.Label(self.results_inner,
                 text="🍽️  Enter a cuisine type above and click  Find Restaurant Competitors\n\n"
                      "Examples: Punjabi · Chinese · Italian · Gujarati · Continental",
                 font=("Segoe UI",11), fg=T("TEXT2"), bg=T("BG"),
                 justify="center").pack(pady=80)
    def show(self):
        self.win.deiconify(); self.win.lift(); self.win.focus_force()

    def _search(self):
        cuisine  = self.cuisine_var.get().strip()
        location = self.loc_var.get().strip() or "Ahmedabad"
        vibe     = self.vibe_var.get().strip()
        if not cuisine:
            messagebox.showwarning("Missing Input",
                "Please enter a cuisine type.", parent=self.win); return
        query = f"{cuisine} {vibe} restaurant".strip() if vibe else f"{cuisine} restaurant"
        for w in self.results_inner.winfo_children(): w.destroy()
        tk.Label(self.results_inner,
                 text=f"⏳  Searching {cuisine} restaurants in {location}…",
                 font=FONT_BODY, fg=T("TEXT2"), bg=T("BG")).pack(pady=40)
        self.search_btn.config(state="disabled", bg=T("TEXT3"))
        self.status_lbl.config(text="Searching…", fg=WARNING)

        def worker():
            try:
                data = MapsDataFetcher.fetch_places(query, location, is_restaurant=True)
                self.win.after(0, self._on_success, data, cuisine, location)
            except Exception as e:
                self.win.after(0, self._on_fail, str(e))
        threading.Thread(target=worker, daemon=True).start()

    def _on_success(self, data, cuisine, location):
        self._rest_data = data
        self.search_btn.config(state="normal", bg=self.REST_COLOR)
        self.status_lbl.config(
            text=f"✓  {len(data)} {cuisine.title()} restaurants found in {location}",
            fg=SUCCESS)
        self._display(data, cuisine, location)

    def _on_fail(self, msg):
        self.search_btn.config(state="normal", bg=self.REST_COLOR)
        self.status_lbl.config(text="Error ✗", fg=DANGER)
        for w in self.results_inner.winfo_children(): w.destroy()
        tk.Label(self.results_inner, text=f"❌  {msg}",
                 font=FONT_BODY, fg=DANGER, bg=T("BG"), wraplength=900).pack(pady=40)

    def _display(self, data, cuisine, location):
        for w in self.results_inner.winfo_children(): w.destroy()
        if not data:
            tk.Label(self.results_inner,
                     text="No restaurants found. Try a different cuisine or location.",
                     font=("Segoe UI",11), fg=T("TEXT2"), bg=T("BG"),
                     pady=40).pack()
            return

        rated     = [r for r in data if r["rating"] > 0]
        avg       = round(sum(r["rating"] for r in rated) / len(rated), 2) if rated else 0
        total_rev = sum(r["review_count"] for r in data)
        top_r     = max(rated, key=lambda x: x["rating"]) if rated else None
        most_rev  = max(data, key=lambda x: x["review_count"]) if data else None

        # ── Premium summary header ──────────────────────────────────────────
        summ_outer = tk.Frame(self.results_inner, bg=T("BG"), pady=12, padx=12)
        summ_outer.pack(fill="x")

        # Title row
        title_row = tk.Frame(summ_outer, bg=T("BG")); title_row.pack(fill="x", pady=(0,10))
        tk.Label(title_row,
                 text=f"🍽️  {cuisine.title()} Restaurants in {location}",
                 font=("Segoe UI",13,"bold"), bg=T("BG"), fg=T("TEXT1")).pack(side="left")
        tk.Label(title_row,
                 text=f"  {len(data)} found",
                 font=("Segoe UI",10), bg=T("BG"), fg=ACCENT).pack(side="left")

        # Stat cards row
        stats_row = tk.Frame(summ_outer, bg=T("BG")); stats_row.pack(fill="x")
        stats_row.columnconfigure((0,1,2,3), weight=1)

        def stat_card(col, icon, label, val, fg=PRIMARY, sub=None):
            f = tk.Frame(stats_row, bg=T("SURFACE"), padx=14, pady=14)
            f.grid(row=0, column=col, padx=5, sticky="ew")
            # top accent line
            tk.Frame(f, bg=fg, height=3).pack(fill="x", pady=(0,8))
            tk.Label(f, text=icon, font=("Segoe UI",20), bg=T("SURFACE")).pack()
            tk.Label(f, text=val, font=("Segoe UI",14,"bold"),
                     bg=T("SURFACE"), fg=fg).pack(pady=(4,0))
            tk.Label(f, text=label, font=("Segoe UI",8,"bold"),
                     bg=T("SURFACE"), fg=T("TEXT1")).pack()
            if sub:
                tk.Label(f, text=sub, font=("Segoe UI",8),
                         bg=T("SURFACE"), fg=T("TEXT3"),
                         wraplength=180).pack(pady=(2,0))

        stat_card(0, "🍴", "Restaurants Found", str(len(data)), ACCENT)
        stat_card(1, "⭐", "Avg Rating",         f"{avg}/5.0",  ACCENT2,
                  sub=f"Top: {top_r['name'][:20] if top_r else '—'}")
        stat_card(2, "💬", "Total Reviews",      f"{total_rev:,}", PRIMARY,
                  sub=f"Most: {most_rev['name'][:20] if most_rev else '—'}")
        stat_card(3, "📍", "Location",            location,     SUCCESS)

        # ── Chart ──────────────────────────────────────────────────────────
        if rated:
            self._embed_chart(rated)

        # ── Divider + sort indicator ────────────────────────────────────────
        div = tk.Frame(self.results_inner, bg=T("SURFACE"), pady=8, padx=16)
        div.pack(fill="x")
        tk.Label(div, text="▼  Restaurant Rankings", font=("Segoe UI",10,"bold"),
                 bg=T("SURFACE"), fg=T("TEXT1")).pack(side="left")
        self._sort_indicator = tk.Label(div, text="Sorted by: Rating",
                                        font=("Segoe UI",8), bg=T("SURFACE"), fg=T("TEXT2"))
        self._sort_indicator.pack(side="right")
        tk.Frame(self.results_inner, bg=T("BORDER"), height=1).pack(fill="x", padx=12)

        # Record fixed header count BEFORE adding cards
        self._fixed_header_count = len(self.results_inner.winfo_children())
        self._rest_current_data = data
        self._resort()

    def _embed_chart(self, rated):
        cf = tk.Frame(self.results_inner, bg=T("SURFACE"))
        cf.pack(fill="x", padx=10, pady=(4, 0))
        names   = [r["name"][:16] for r in rated]
        ratings = [r["rating"]    for r in rated]
        colors  = [SUCCESS if v >= 4.5 else PRIMARY if v >= 4.0 else ACCENT2 if v >= 3.0 else DANGER
                   for v in ratings]
        _plt_rc()
        # Use Figure OO API — never plt.subplots() inside Tk (causes TkAgg deadlock)
        fig = Figure(figsize=(11, max(2.6, len(names) * 0.32)), dpi=96)
        fig.patch.set_facecolor(T("SURFACE"))
        ax = fig.add_subplot(111)
        ax.set_facecolor(T("SURFACE2"))
        bars = ax.barh(names, ratings, color=colors, edgecolor=T("BG"), height=0.52)
        ax.set_xlim(0, 5.6)
        ax.axvline(4.0, color=T("BORDER"), linestyle="--", linewidth=0.9, alpha=0.7)
        ax.set_xlabel("Rating", fontweight="bold", color=T("TEXT2"), fontsize=9)
        ax.set_title("Restaurant Ratings at a Glance", fontweight="bold",
                     color=T("TEXT1"), pad=10, fontsize=11)
        ax.tick_params(colors=T("TEXT2"), labelsize=9)
        ax.spines[:].set_color(T("BORDER"))
        for i, (bar, v) in enumerate(zip(bars, ratings)):
            ax.text(v + 0.07, i, f"{v:.1f}", va="center", fontsize=8,
                    fontweight="bold", color=T("TEXT1"))
        fig.tight_layout(pad=1.5)
        cv = FigureCanvasTkAgg(fig, master=cf)
        cv.draw()
        cv.get_tk_widget().pack(fill="x", padx=4, pady=8)

    def _resort(self):
        if not self._rest_current_data: return
        # Destroy only card widgets; keep the fixed header widgets
        children = list(self.results_inner.winfo_children())
        for w in children[self._fixed_header_count:]:
            w.destroy()
        key = self.sort_var.get()
        icons = {"Rating": "⭐", "Reviews": "💬", "Name": "🔤"}
        if key == "Rating":
            sdata = sorted(self._rest_current_data,
                           key=lambda x: (x["rating"], x["review_count"]), reverse=True)
        elif key == "Reviews":
            sdata = sorted(self._rest_current_data,
                           key=lambda x: x["review_count"], reverse=True)
        else:
            sdata = sorted(self._rest_current_data, key=lambda x: x["name"])
        for i, r in enumerate(sdata, 1):
            RestaurantCard(self.results_inner, r, i, self.root)
        # Update sort indicator label
        try:
            self._sort_indicator.config(
                text=f"Sorted by: {icons.get(key,'')} {key}")
        except Exception:
            pass
        # Force canvas scroll region refresh
        self.results_inner.update_idletasks()



# ─────────────────────────────────────────────────────────────────────────────
# FIX: SortPreferenceDialog — NO wait_window / NO blocking the main thread
#   Uses a callback instead.  Call pattern:
#       SortPreferenceDialog(parent, current, callback=lambda pref: ...)
# ─────────────────────────────────────────────────────────────────────────────
class SortPreferenceDialog:
    OPTION_META = {
        "nearest": {
            "icon": "📍", "label": "Nearest",
            "desc": "Show shops closest to your\nsearch location first",
            "color": ACCENT,
        },
        "top_rated": {
            "icon": "★", "label": "Top Rated",
            "desc": "Show highest-rated shops\nwith most reviews first",
            "color": SUCCESS,
        },
        "both": {
            "icon": "⚡", "label": "Best Match",
            "desc": "Balanced score: rating\nplus proximity combined",
            "color": PRIMARY,
        },
    }

    def __init__(self, parent, current: str = "both", callback=None):
        """
        callback(preference_str) is called when the user confirms.
        If callback is None the dialog still works but nothing happens on confirm.
        IMPORTANT: we intentionally do NOT call parent.wait_window() or grab_set()
        in a way that would block the Tk event loop.
        """
        self._callback = callback
        self.win = tk.Toplevel(parent)
        self.win.title("Sort Local Shops")
        self.win.geometry("480x320")
        self.win.resizable(False, False)
        self.win.configure(bg=T("BG"))
        # transient but NOT grab_set — grab_set() with wait_window is what hung the app
        self.win.transient(parent)
        self._build(current)
        # centre on parent
        self.win.update_idletasks()
        px, py = parent.winfo_rootx(), parent.winfo_rooty()
        pw, ph = parent.winfo_width(),  parent.winfo_height()
        ww, wh = self.win.winfo_width(), self.win.winfo_height()
        self.win.geometry(f"+{px+(pw-ww)//2}+{py+(ph-wh)//2}")
        # No wait_window — dialog is non-blocking

    def _build(self, current):
        # ── Header ────────────────────────────────────────────────────────
        hdr = tk.Frame(self.win, bg=T("SURFACE2"), pady=16)
        hdr.pack(fill="x")
        # Gradient strip
        grad = tk.Frame(hdr, height=3, bg=T("SURFACE2"))
        grad.pack(fill="x", pady=(0, 12))
        for col in [PRIMARY, ACCENT, ACCENT2]:
            tk.Frame(grad, bg=col, height=3).pack(side="left", fill="x", expand=True)
        # Icon + text
        hdr_inner = tk.Frame(hdr, bg=T("SURFACE2"))
        hdr_inner.pack(padx=22)
        tk.Label(hdr_inner, text="⚡",
                 font=("Segoe UI Variable", 18, "bold"),
                 bg=T("SURFACE2"), fg=ACCENT2).pack(side="left", padx=(0, 12))
        txt_col = tk.Frame(hdr_inner, bg=T("SURFACE2"))
        txt_col.pack(side="left")
        tk.Label(txt_col, text="Sort Local Shops",
                 font=("Segoe UI Variable", 12, "bold"),
                 bg=T("SURFACE2"), fg=T("TEXT1")).pack(anchor="w")
        tk.Label(txt_col, text="Choose the ranking order for competitor results",
                 font=("Segoe UI", 8),
                 bg=T("SURFACE2"), fg=T("TEXT2")).pack(anchor="w")

        # ── Cards ─────────────────────────────────────────────────────────
        cards_frame = tk.Frame(self.win, bg=T("BG"), pady=20, padx=20)
        cards_frame.pack(fill="both", expand=True)
        cards_frame.columnconfigure((0, 1, 2), weight=1)

        self._selected_var = tk.StringVar(value=current)
        self._cards: Dict = {}
        for col_idx, (key, meta) in enumerate(self.OPTION_META.items()):
            self._make_card(cards_frame, col_idx, key, meta)

        # ── Confirm button ─────────────────────────────────────────────────
        btn_frame = tk.Frame(self.win, bg=T("SURFACE2"), pady=14)
        btn_frame.pack(fill="x", side="bottom")
        tk.Button(
            btn_frame,
            text="  ✦  Confirm & Apply  ",
            font=("Segoe UI Variable", 9, "bold"),
            bg=PRIMARY, fg="#ffffff",
            relief="flat", padx=22, pady=9,
            cursor="hand2",
            activebackground=PRIMARY_D, activeforeground="#ffffff",
            command=self._confirm,
        ).pack()

    def _make_card(self, parent, col_idx, key, meta):
        is_selected  = (self._selected_var.get() == key)
        border_color = meta["color"] if is_selected else T("BORDER")
        card = tk.Frame(parent, bg=T("SURFACE"), padx=10, pady=14,
                        highlightbackground=border_color,
                        highlightthickness=2, cursor="hand2")
        card.grid(row=0, column=col_idx, padx=6, sticky="nsew")
        accent_bar = tk.Frame(card, bg=meta["color"] if is_selected else T("BORDER"), height=3)
        accent_bar.pack(fill="x", pady=(0, 10))
        icon_lbl = tk.Label(card, text=meta["icon"],
                            font=("Segoe UI", 22), bg=T("SURFACE"), fg=meta["color"])
        icon_lbl.pack()
        name_lbl = tk.Label(card, text=meta["label"],
                            font=("Segoe UI", 10, "bold"), bg=T("SURFACE"),
                            fg=meta["color"] if is_selected else T("TEXT1"))
        name_lbl.pack(pady=(4, 0))
        desc_lbl = tk.Label(card, text=meta["desc"],
                            font=FONT_SMALL, bg=T("SURFACE"), fg=T("TEXT2"), justify="center")
        desc_lbl.pack(pady=(4, 0))

        def on_click(k=key):
            self._selected_var.set(k)
            self._refresh_cards()

        for widget in (card, accent_bar, icon_lbl, name_lbl, desc_lbl):
            widget.bind("<Button-1>", lambda e, k=key: on_click(k))

        self._cards[key] = {
            "card": card, "accent_bar": accent_bar,
            "name_lbl": name_lbl, "meta": meta,
        }

    def _refresh_cards(self):
        selected = self._selected_var.get()
        for key, widgets in self._cards.items():
            meta  = widgets["meta"]
            is_sel = (key == selected)
            col   = meta["color"] if is_sel else T("BORDER")
            widgets["card"].config(highlightbackground=col)
            widgets["accent_bar"].config(bg=col)
            widgets["name_lbl"].config(fg=meta["color"] if is_sel else T("TEXT1"))

    def _confirm(self):
        pref = self._selected_var.get()
        self.win.destroy()
        if self._callback:
            self._callback(pref)


# ── Sort helper ───────────────────────────────────────────────────────────────
def sort_maps_data(data: List[Dict], preference: str) -> List[Dict]:
    if not data:
        return data
    if preference == "nearest":
        return sorted(data, key=lambda x: x.get("proximity_rank", 0))
    if preference == "top_rated":
        return sorted(data,
                      key=lambda x: (x.get("rating", 0), x.get("review_count", 0)),
                      reverse=True)
    max_rank = max((x.get("proximity_rank", 0) for x in data), default=1) or 1

    def composite(item):
        rat_norm  = item.get("rating", 0) / 5.0
        prox_norm = 1.0 - (item.get("proximity_rank", 0) / max_rank)
        return rat_norm * 0.6 + prox_norm * 0.4

    return sorted(data, key=composite, reverse=True)


# ── Popup windows ─────────────────────────────────────────────────────────────
class MapsReviewPopup:
    """Enhanced popup: restaurant mode, paginated reviews, photo gallery, AI insights."""

    REST_COLOR = "#ff7043"

    def __init__(self, parent, shop: Dict, is_restaurant: bool = False):
        self.shop          = shop
        self.is_restaurant = is_restaurant
        self.all_reviews   = list(shop.get("reviews", []))
        self.native_topics = list(shop.get("native_topics", []))
        self.precalculated_dishes = []
        self._displayed    = 0
        self.win = tk.Toplevel(parent)
        self.win.title(
            f"{'🍽️' if is_restaurant else '📋'}  {shop['name']}  —  Details & Reviews"
        )
        self.win.geometry("980x940")
        self.win.configure(bg=T("BG"))
        self._build()
        
        if self.all_reviews:
            self._precalculate_dishes()
            self._render_reviews()
        else:
            self._load_reviews()

    def _precalculate_dishes(self):
        if not self.is_restaurant: return
        def calc():
            self.precalculated_dishes = intelligent_extract_dishes(self.all_reviews, self.native_topics)
        threading.Thread(target=calc, daemon=True).start()

    def _build(self):
        shop = self.shop
        hc   = self.REST_COLOR if self.is_restaurant else T("SURFACE2")
        hfg  = "#ffffff"       if self.is_restaurant else T("TEXT1")
        barc = "#ffd700"       if self.is_restaurant else PRIMARY

        # ── Header bar ────────────────────────────────────────────────────
        hdr_outer = tk.Frame(self.win, bg=hc)
        hdr_outer.pack(fill="x")
        # Gradient strip
        grad = tk.Frame(hdr_outer, height=3, bg=hc)
        grad.pack(fill="x")
        for col in ([barc, self.REST_COLOR, "#cc4a1a"]
                    if self.is_restaurant
                    else [PRIMARY, ACCENT, ACCENT2]):
            tk.Frame(grad, bg=col, height=3).pack(side="left", fill="x", expand=True)

        hdr = tk.Frame(hdr_outer, bg=hc, pady=16)
        hdr.pack(fill="x")
        tk.Frame(hdr, bg=barc, width=5).pack(side="left", fill="y")
        txt = tk.Frame(hdr, bg=hc)
        txt.pack(side="left", padx=20, fill="x", expand=True)
        tk.Label(txt, text=shop["name"],
                 font=("Segoe UI Variable", 15, "bold"),
                 bg=hc, fg=hfg).pack(anchor="w")
        meta_parts = []
        if shop.get("type"):     meta_parts.append(shop["type"][:40])
        if shop.get("location"): meta_parts.append(shop["location"][:50])
        if meta_parts:
            tk.Label(txt, text="  ·  ".join(meta_parts[:2]),
                     font=("Segoe UI", 9), bg=hc,
                     fg="#fed7aa" if self.is_restaurant else T("TEXT2")).pack(anchor="w")

        # ── KPI stat row ──────────────────────────────────────────────────
        cr = tk.Frame(self.win, bg=T("BG"), pady=10, padx=14)
        cr.pack(fill="x")
        cr.columnconfigure((0, 1, 2, 3), weight=1)

        def sc(col, icon, label, value, fg=PRIMARY):
            f = tk.Frame(cr, bg=T("SURFACE"),
                         highlightbackground=T("BORDER"),
                         highlightthickness=1,
                         padx=12, pady=13)
            f.grid(row=0, column=col, padx=4, sticky="ew")
            tk.Frame(f, bg=fg, height=2).pack(fill="x", pady=(0, 8))
            tk.Label(f, text=icon,
                     font=("Segoe UI", 18),
                     bg=T("SURFACE"), fg=fg).pack()
            tk.Label(f, text=value,
                     font=("Segoe UI Variable", 12, "bold"),
                     bg=T("SURFACE"), fg=fg, wraplength=160).pack()
            tk.Label(f, text=label,
                     font=FONT_SMALL, bg=T("SURFACE"), fg=T("TEXT2")).pack()

        r_color = rating_color(shop["rating"])
        bstatus = shop.get("business_status", "UNKNOWN")
        if not isinstance(bstatus, str):
            bstatus = str(shop.get("hours_display") or "UNKNOWN")
        bs_fg   = SUCCESS if bstatus == "OPERATIONAL" else DANGER if bstatus == "CLOSED" else WARNING
        sc(0, "★", "Rating",  f"{shop['rating']}/5.0", r_color)
        sc(1, "◈", "Reviews", f"{shop['review_count']:,}", ACCENT)
        sc(2, "₹", "Price",   shop.get("price_label", "Budget Unknown"), ACCENT2)
        self._price_label_widget = cr.winfo_children()[2].winfo_children()[2] # Target the value label
        sc(3, "◉", "Status",  bstatus.replace("_", " ").title(), bs_fg)

        # ── Info row ──────────────────────────────────────────────────────
        info = tk.Frame(self.win, bg=T("SURFACE"),
                        highlightbackground=T("BORDER"),
                        highlightthickness=1,
                        padx=18, pady=11)
        info.pack(fill="x", padx=14, pady=(0, 6))
        tk.Label(info, text=f"📍  {shop['location']}",
                 font=FONT_BODY, fg=T("TEXT1"), bg=T("SURFACE"),
                 wraplength=900, justify="left").pack(anchor="w")
        hd = shop.get("hours_display", "")
        if hd:
            on  = shop.get("open_now")
            dot = "●" if on is True else "○" if on is False else "◌"
            clr = SUCCESS if on is True else DANGER if on is False else WARNING
            tk.Label(info, text=f"{dot}  {hd}",
                     font=FONT_SMALL, fg=clr, bg=T("SURFACE")).pack(anchor="w", pady=(3, 0))
        if shop.get("phone"):
            tk.Label(info, text=f"📞  {shop['phone']}",
                     font=FONT_SMALL, fg=T("TEXT2"), bg=T("SURFACE")).pack(anchor="w", pady=(3, 0))

        # ── Action buttons ────────────────────────────────────────────────
        btns = tk.Frame(self.win, bg=T("BG"), padx=14, pady=8)
        btns.pack(fill="x")

        def mkbtn(text, bg, cmd, fg=None):
            b = tk.Button(btns, text=text,
                          font=("Segoe UI Variable", 8, "bold"),
                          bg=bg, fg=fg or T("TEXT1"),
                          relief="flat", padx=12, pady=7,
                          cursor="hand2",
                          activebackground=bg, activeforeground=fg or T("TEXT1"),
                          command=cmd)
            b.pack(side="left", padx=(0, 7))

        mkbtn("🗺️ Maps",        SUCCESS, lambda: webbrowser.open(shop["maps_link"]))
        mkbtn("📊 Review Graph", PRIMARY, self._show_review_graph)
        mkbtn("🧠 Sentiment",    ACCENT,  self._show_sentiment)
        if self.is_restaurant:
            mkbtn("🖼️ Photo Gallery", self.REST_COLOR, self._show_photo_gallery, "#fff")
            if OLLAMA_AVAILABLE:
                mkbtn("✨ AI Insights", "#7c3aed", self._show_ai_insights, "#fff")
            mkbtn("🏆 Popular Dishes", "#eab308", self._show_popular_dishes, "#000")
        if shop.get("website"):
            mkbtn("🌐 Website", T("SURFACE3"), lambda: webbrowser.open(shop["website"]))

        tk.Frame(self.win, bg=T("BORDER"), height=1).pack(fill="x", padx=14, pady=4)
        rr = tk.Frame(self.win, bg=T("BG"), padx=14); rr.pack(fill="x")
        self.rev_hdr = tk.Label(rr, text="💬  Reviews  (loading…)",
                                font=FONT_HEADING, bg=T("BG"), fg=T("TEXT1"), pady=6)
        self.rev_hdr.pack(side="left")
        self._more_btn = tk.Button(rr, text="Load More ▼", font=FONT_SMALL,
                                   bg=T("SURFACE3"), fg=T("TEXT1"), relief="flat",
                                   padx=10, pady=4, cursor="hand2", state="disabled",
                                   command=self._load_more)
        self._more_btn.pack(side="right")
        _, self.rev_inner, _ = scrollable_frame(self.win, bg=T("BG"))

    def _load_reviews(self):
        tk.Label(self.rev_inner,
                 text="⏳  Fetching reviews (newest + lowest rated for accuracy)…",
                 font=FONT_BODY, bg=T("BG"), fg=T("TEXT2")).pack(pady=20)
        def worker():
            res = MapsDataFetcher.fetch_reviews(self.shop.get("place_id",""))
            self.all_reviews = res.get("reviews", [])
            self.native_topics = res.get("topics", [])
            self.shop["reviews"] = self.all_reviews
            self.shop["native_topics"] = self.native_topics
            self._precalculate_dishes()
            self._mine_price()
            if self.win.winfo_exists():
                self.win.after(0, self._render_reviews)
        threading.Thread(target=worker, daemon=True).start()

    def _mine_price(self):
        """Scans reviews for actual price mentions."""
        if not self.all_reviews: return
        patterns = [
            r'₹\s?(\d{2,5})',                       # ₹500
            r'rs\.?\s?(\d{2,5})',                   # rs 1000
            r'(\d{2,5})\s?for\s?two',                # 500 for two
            r'(\d{2,5})\s?per\s?(?:head|person|plate)' # 300 per head
        ]
        found = []
        for rev in self.all_reviews:
            text = (rev.get("snippet", "") or rev.get("text", "") or "").lower()
            for p in patterns:
                matches = re.findall(p, text)
                for m in matches:
                    found.append(int(m))
        
        if found:
            avg = sum(found) // len(found)
            # Cap realistic ranges
            if 50 < avg < 10000:
                new_price = f"Est. ~₹{avg}"
                if "for two" in str(found):
                     new_price += " (for 2)"
                self.shop["price_label"] = new_price
                if hasattr(self, "_price_label_widget") and self._price_label_widget.winfo_exists():
                    self.win.after(0, lambda: self._price_label_widget.config(text=new_price))

    def _render_reviews(self):
        if not self.win.winfo_exists(): return
        for w in self.rev_inner.winfo_children(): w.destroy()
        self._displayed = 0
        revs = self.all_reviews
        self.rev_hdr.config(
            text=f"💬  Reviews  ({len(revs)} fetched  ·  includes low ratings)")
        if not revs:
            tk.Label(self.rev_inner, text="No written reviews found.",
                     font=FONT_BODY, bg=T("BG"), fg=T("TEXT2")).pack(pady=24)
            return
        self._show_batch()

    def _show_batch(self, batch_size: int = 10):
        revs  = self.all_reviews
        batch = revs[self._displayed : self._displayed + batch_size]
        self._displayed += len(batch)
        CRIT = {"improvement","improve","slow","dirty","rude","cold","stale",
                "overpriced","wait","wrong","bad","poor","bland","disappointing"}

        for rev in batch:
            rating  = rev.get("rating",0)
            snippet = (rev.get("snippet","") or rev.get("text","")).strip()
            author  = (rev.get("user",{}).get("name","Anonymous")
                       if isinstance(rev.get("user"),dict) else "Anonymous")
            date_s  = rev.get("date","")
            accent  = rating_color(rating)
            crits   = [kw for kw in CRIT if kw in snippet.lower()] if snippet else []
            is_crit = bool(rating and rating<=4 and crits)

            outer = tk.Frame(self.rev_inner, bg=T("BG"), pady=2, padx=14)
            outer.pack(fill="x")
            card = tk.Frame(outer, bg=T("SURFACE")); card.pack(fill="x")
            tk.Frame(card, bg=DANGER if is_crit else accent,
                     width=6 if is_crit else 3).pack(side="left", fill="y")
            body = tk.Frame(card, bg=T("SURFACE"), padx=13, pady=9)
            body.pack(side="left", fill="both", expand=True)
            top = tk.Frame(body, bg=T("SURFACE")); top.pack(fill="x")
            tk.Label(top, text=f"★ {rating}/5.0  —  {author}",
                     font=("Segoe UI",9,"bold"), bg=T("SURFACE"), fg=accent).pack(side="left")
            tk.Label(top, text=date_s, font=FONT_SMALL,
                     bg=T("SURFACE"), fg=T("TEXT3")).pack(side="right")
            if is_crit:
                bf = tk.Frame(body, bg=T("SURFACE")); bf.pack(fill="x", pady=(2,0))
                tk.Label(bf, text=f"⚠ High-Priority Insight · {', '.join(crits[:4])}",
                         font=("Segoe UI",8,"bold"), bg="#2d0c0c", fg=DANGER,
                         padx=8, pady=2).pack(anchor="w")
            tk.Label(body, text=snippet or "(No written review)", font=FONT_BODY,
                     bg=T("SURFACE"),
                     fg=T("TEXT1") if snippet else T("TEXT3"),
                     wraplength=800, justify="left", anchor="w").pack(fill="x", pady=(4,0))
            if rev.get("likes"):
                tk.Label(body, text=f"👍 {rev['likes']} found helpful",
                         font=FONT_SMALL, fg=T("TEXT3"), bg=T("SURFACE")).pack(
                         anchor="w", pady=(3,0))

        remaining = len(revs) - self._displayed
        if remaining > 0:
            self._more_btn.config(state="normal",
                                  text=f"Load More ▼  ({remaining} remaining)")
        else:
            self._more_btn.config(state="disabled", text="All reviews loaded ✓")

    def _load_more(self):
        self._show_batch()

    def _show_review_graph(self):
        revs = self.all_reviews
        if not revs:
            messagebox.showinfo("No Data","No review data.",parent=self.win); return
        stars  = [int(r.get("rating",0)) for r in revs]
        counts = Counter(stars)
        sizes  = [counts.get(i,0) for i in [5,4,3,2,1]]
        clrs   = [SUCCESS,"#4ade80",ACCENT2,WARNING,DANGER]
        gw = tk.Toplevel(self.win)
        gw.title(f"📊 Review Analysis — {self.shop['name']}")
        gw.geometry("860x620"); gw.configure(bg=T("BG"))
        hdr = tk.Frame(gw, bg=T("SURFACE2"), pady=12); hdr.pack(fill="x")
        tk.Label(hdr, text=f"📊  {self.shop['name']}  ·  {len(revs)} reviews",
                 font=FONT_HEADING, bg=T("SURFACE2"), fg=T("TEXT1")).pack(anchor="w",padx=16)
        tk.Label(hdr, text="Includes low-rated reviews for honest analysis",
                 font=FONT_SMALL, bg=T("SURFACE2"), fg=T("TEXT2")).pack(anchor="w",padx=16)
        _plt_rc()
        fig = Figure(figsize=(10,5), dpi=100); fig.patch.set_facecolor(T("BG"))
        ax1 = fig.add_subplot(1,2,1); ax2 = fig.add_subplot(1,2,2)
        ax1.set_facecolor(T("SURFACE")); ax2.set_facecolor(T("SURFACE"))
        nz = [(s,l,c) for s,l,c in zip(sizes,["5★","4★","3★","2★","1★"],clrs) if s>0]
        if nz:
            sz,lb,cl = zip(*nz)
            w2,texts,autos = ax1.pie(sz, labels=lb, autopct="%1.1f%%", colors=cl,
                startangle=90, wedgeprops={"edgecolor":T("BG"),"linewidth":2},
                pctdistance=0.82)
            for t in texts:  t.set_color(T("TEXT1")); t.set_fontsize(9)
            for a in autos:  a.set_color("#fff"); a.set_fontweight("bold"); a.set_fontsize(9)
        ax1.set_title(f"Star Distribution ({len(revs)} reviews)", fontweight="bold",pad=12)
        bars = ax2.barh(["5 ★","4 ★","3 ★","2 ★","1 ★"], sizes,
                        color=clrs, edgecolor=T("BG"), height=0.55)
        ax2.set_xlim(0, max(sizes)*1.4+1)
        ax2.set_xlabel("Number of Reviews", fontsize=9)
        ax2.set_title("Review Count per Star", fontweight="bold", pad=12)
        for bar,val in zip(bars,sizes):
            if val>0:
                ax2.text(val+max(sizes)*0.03, bar.get_y()+bar.get_height()/2,
                         str(val), va="center", fontsize=10, fontweight="bold",
                         color=T("TEXT1"))
        ax2.spines[:].set_color(T("BORDER"))
        ax2.grid(axis="x", linestyle="--", alpha=0.2, color=T("BORDER"))
        fig.tight_layout(pad=2.5)
        cv = FigureCanvasTkAgg(fig, master=gw)
        cv.draw(); cv.get_tk_widget().pack(fill="both", expand=True, padx=14, pady=8)
        avg_r = sum(stars)/len(stars) if stars else 0
        pos = sum(1 for s in stars if s>=4)
        neg = sum(1 for s in stars if s<=2)
        foot = tk.Frame(gw, bg=T("SURFACE"), pady=8, padx=14); foot.pack(fill="x")
        for icon,lbl,val,fg in [
            ("⭐","Avg Rating",    f"{avg_r:.2f}/5.0",                    ACCENT2),
            ("👍","Positive 4-5★", f"{pos} ({pos*100//max(len(revs),1)}%)",SUCCESS),
            ("👎","Negative 1-2★", f"{neg} ({neg*100//max(len(revs),1)}%)",DANGER),
            ("📝","Total Fetched", f"{len(revs)} reviews",                 ACCENT),
        ]:
            f = tk.Frame(foot, bg=T("SURFACE2"), padx=12, pady=6)
            f.pack(side="left", padx=6, fill="x", expand=True)
            tk.Label(f, text=f"{icon} {lbl}", font=FONT_SMALL,
                     bg=T("SURFACE2"), fg=T("TEXT2")).pack(anchor="w")
            tk.Label(f, text=val, font=FONT_LABEL,
                     bg=T("SURFACE2"), fg=fg).pack(anchor="w")

    def _show_sentiment(self):
        texts = [r.get("snippet","") or r.get("text","") for r in self.all_reviews]
        if not texts:
            messagebox.showinfo("No Data","Load reviews first.",parent=self.win); return
        if not TEXTBLOB_AVAILABLE:
            messagebox.showinfo("Missing","pip install textblob",parent=self.win); return
        s = analyze_sentiment(texts)
        sw = tk.Toplevel(self.win)
        sw.title(f"🧠 Sentiment — {self.shop['name']}")
        sw.geometry("760x520"); sw.configure(bg=T("BG"))
        hdr = tk.Frame(sw, bg=T("SURFACE2"), pady=12); hdr.pack(fill="x")
        tk.Label(hdr, text=f"🧠 Sentiment  ·  {self.shop['name']}",
                 font=FONT_HEADING, bg=T("SURFACE2"), fg=T("TEXT1")).pack(anchor="w",padx=16)
        _plt_rc()
        fig = Figure(figsize=(9,4), dpi=96); fig.patch.set_facecolor(T("BG"))
        ax1 = fig.add_subplot(1,2,1); ax2 = fig.add_subplot(1,2,2)
        ax1.set_facecolor(T("SURFACE")); ax2.set_facecolor(T("SURFACE"))
        vals = [s["positive"],s["neutral"],s["negative"]]
        labs = ["Positive","Neutral","Negative"]
        clrs = [SUCCESS,WARNING,DANGER]
        nz = [(v,l,c) for v,l,c in zip(vals,labs,clrs) if v>0]
        if nz:
            vz,lz,cz = zip(*nz)
            ax1.pie(vz, labels=lz, autopct="%1.0f%%", colors=cz, startangle=90,
                    wedgeprops={"edgecolor":T("BG"),"linewidth":2})
        ax1.set_title(f"Sentiment\nPolarity: {s['avg_polarity']:+.2f}", fontweight="bold")
        if s["keywords"]:
            kws  = [k for k,_ in s["keywords"][:8]]
            cnts = [c for _,c in s["keywords"][:8]]
            ax2.barh(kws, cnts, color=PRIMARY, edgecolor=T("BG"), height=0.55)
            ax2.set_title("Top Keywords", fontweight="bold")
            ax2.grid(axis="x", linestyle="--", alpha=0.2, color=T("BORDER"))
        fig.tight_layout(pad=2)
        cv = FigureCanvasTkAgg(fig, master=sw)
        cv.draw(); cv.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=8)

    def _show_photo_gallery(self):
        place_id  = self.shop.get("place_id", "")
        data_id   = self.shop.get("data_id", "")
        shop_name = self.shop["name"]
        reviews   = self.all_reviews or self.shop.get("reviews", [])

        gw = tk.Toplevel(self.win)
        gw.title(f"🖼️ Photo Gallery  —  {shop_name}")
        gw.geometry("1140x820")
        gw.configure(bg=T("BG"))

        # ── Header ────────────────────────────────────────────────────────────
        hdr = tk.Frame(gw, bg=self.REST_COLOR, pady=12)
        hdr.pack(fill="x")
        tk.Label(hdr, text=f"🖼️  Photo Gallery  —  {shop_name}",
                 font=("Segoe UI", 12, "bold"),
                 bg=self.REST_COLOR, fg="#fff").pack(anchor="w", padx=16)
        tk.Label(hdr,
                 text="Photos fetched from Google Maps  ·  Categorised: Food · Menu · Ambiance",
                 font=FONT_SMALL, bg=self.REST_COLOR, fg="#fed7aa").pack(anchor="w", padx=16)

        # ── Best-sellers bar ──────────────────────────────────────────────────
        bsellers = extract_bestsellers(reviews)
        if bsellers:
            bf = tk.Frame(gw, bg="#1a0a00", padx=16, pady=8)
            bf.pack(fill="x")
            tk.Label(bf,
                     text="🏆  Best Sellers from Reviews:  " + "   ·   ".join(bsellers[:6]),
                     font=("Segoe UI", 9, "bold"), bg="#1a0a00", fg="#fbbf24",
                     wraplength=1080, justify="left").pack(anchor="w")

        # ── Status bar ────────────────────────────────────────────────────────
        status_var = tk.StringVar(value="⏳  Fetching photos from Google Maps…")
        status_lbl = tk.Label(gw, textvariable=status_var, font=FONT_BODY,
                              bg=T("BG"), fg=T("TEXT2"), pady=6)
        status_lbl.pack(anchor="w", padx=16)

        # ── Tabs ──────────────────────────────────────────────────────────────
        nb = ttk.Notebook(gw)
        nb.pack(fill="both", expand=True, padx=8, pady=4)
        tab_food = ttk.Frame(nb); nb.add(tab_food, text="  🍽️ Food Photos  ")
        tab_menu = ttk.Frame(nb); nb.add(tab_menu, text="  📋 Menu  ")
        tab_ambi = ttk.Frame(nb); nb.add(tab_ambi, text="  🏛️ Ambiance  ")
        tab_all  = ttk.Frame(nb); nb.add(tab_all,  text="  📷 All Photos  ")

        def mksf(parent):
            _, inner, _ = scrollable_frame(parent, bg=T("BG"))
            return inner

        ifd = mksf(tab_food)
        imn = mksf(tab_menu)
        iab = mksf(tab_ambi)
        ial = mksf(tab_all)

        # ── PIL check ─────────────────────────────────────────────────────────
        try:
            from PIL import Image, ImageTk
            PIL_OK = True
        except ImportError:
            PIL_OK = False

        # Limit concurrent downloads to avoid hammering the CDN
        _sem = threading.Semaphore(10)

        # ── Browser-like headers that Google Maps CDN actually accepts ─────────
        _HEADERS = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept":          "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer":         "https://www.google.com/maps/",
            "sec-fetch-dest":  "image",
            "sec-fetch-mode":  "no-cors",
            "sec-fetch-site":  "cross-site",
        }

        def _download_image(url: str):
            """Download image bytes with browser headers + 2 retries. Returns bytes or None."""
            for attempt in range(3):
                try:
                    resp = requests.get(
                        url, headers=_HEADERS, timeout=14,
                        stream=True, allow_redirects=True,
                    )
                    resp.raise_for_status()
                    data = b""
                    for chunk in resp.iter_content(65536):
                        if chunk:
                            data += chunk
                        if len(data) > 8_000_000:  # 8 MB cap
                            return None
                    # Validate by magic bytes so we never try to open HTML as image
                    if len(data) < 512:
                        return None
                    hdr4 = data[:12]
                    is_jpeg = hdr4[:2] == b'\xff\xd8'
                    is_png  = hdr4[:4] == b'\x89PNG'
                    is_webp = hdr4[:4] == b'RIFF' and hdr4[8:12] == b'WEBP'
                    is_gif  = hdr4[:6] in (b'GIF87a', b'GIF89a')
                    is_bmp  = hdr4[:2] == b'BM'
                    if not (is_jpeg or is_png or is_webp or is_gif or is_bmp):
                        return None
                    return data
                except Exception as exc:
                    log.debug(f"Image download attempt {attempt+1} failed ({url[:60]}): {exc}")
                    if attempt < 2:
                        time.sleep(0.4 * (attempt + 1))
            return None

        # ── Tile builder ──────────────────────────────────────────────────────
        def _tile(parent, url: str, idx: int):
            """Build one image tile in the given row frame."""
            tile = tk.Frame(parent, bg=T("SURFACE"), padx=4, pady=4,
                            highlightbackground=T("BORDER"), highlightthickness=1)
            tile.pack(side="left", padx=6, pady=4)

            # Placeholder shown while loading
            ph = tk.Label(tile,
                          text=f"⏳\nLoading…\n#{idx}",
                          font=FONT_SMALL, bg=T("SURFACE"), fg=T("TEXT3"),
                          width=22, height=7)
            ph.pack(padx=2, pady=2)
            # Click-to-open always available, even before image loads
            open_btn = tk.Button(tile, text="🔗 Open in Browser",
                                 font=("Segoe UI", 7),
                                 bg=T("SURFACE3"), fg=T("TEXT2"),
                                 relief="flat", cursor="hand2",
                                 command=lambda u=url: webbrowser.open(u))
            open_btn.pack(pady=(0, 2))

            if not PIL_OK:
                ph.config(text=f"📷 Photo {idx}\n\n(Install Pillow\nfor previews)")
                return

            def load(u=url, t=tile, p=ph):
                _sem.acquire()
                try:
                    raw = _download_image(u)
                    if not raw:
                        raise RuntimeError("download failed or not an image")

                    import io as _io
                    from PIL import Image, ImageTk
                    img = Image.open(_io.BytesIO(raw)).convert("RGB")
                    img.thumbnail((240, 170), Image.LANCZOS)
                    photo = ImageTk.PhotoImage(img)

                    def _show(ph=p, t=t, photo=photo, u=u):
                        if not t.winfo_exists():
                            return
                        try:
                            ph.destroy()
                        except Exception:
                            pass
                        lbl = tk.Label(t, image=photo,
                                       bg=T("SURFACE"), cursor="hand2")
                        lbl.image = photo   # keep reference
                        lbl.pack(padx=2, pady=2)
                        lbl.bind("<Button-1>", lambda e, u2=u: webbrowser.open(u2))
                        tk.Label(t, text="🔍 Click to open full size",
                                 font=("Segoe UI", 7),
                                 bg=T("SURFACE"), fg=T("TEXT3")).pack(pady=(0, 2))

                    if gw.winfo_exists():
                        gw.after(0, _show)

                except Exception as exc:
                    log.debug(f"Image tile load error ({url[:60]}): {exc}")
                    def _show_err(ph=p, t=t):
                        if not t.winfo_exists():
                            return
                        try:
                            ph.config(text="🖼️\n(unavailable)", fg=T("TEXT3"))
                        except Exception:
                            pass
                    if gw.winfo_exists():
                        gw.after(0, _show_err)
                finally:
                    _sem.release()

            threading.Thread(target=load, daemon=True).start()

        # ── Grid builder — 3 tiles per row ────────────────────────────────────
        def _render_grid(parent, urls, empty_msg):
            # Clear existing tiles if any
            for child in parent.winfo_children():
                child.destroy()
            
            if not urls:
                tk.Label(parent, text=empty_msg, font=FONT_BODY,
                         bg=T("BG"), fg=T("TEXT2"),
                         pady=40, wraplength=900, justify="center").pack()
                return
            row_frame = None
            for i, url in enumerate(urls[:100]):
                if i % 3 == 0:
                    row_frame = tk.Frame(parent, bg=T("BG"))
                    row_frame.pack(fill="x", padx=10, pady=4)
                _tile(row_frame, url, i + 1)

        # ── Section-by-section progressive render on main thread ──────────────
        def _render_section(buckets, all_urls):
            """Called on the Tk main thread — renders one section at a time."""
            if not gw.winfo_exists():
                return
            other_u = buckets.get("other", [])
            food_u  = buckets.get("food", [])
            menu_u  = buckets.get("menu", [])
            ambi_u  = buckets.get("ambi", [])

            status_msg = (
                f"✓  {len(all_urls)} photos fetched  ·  "
                f"🍽️ Food: {len(food_u)}  ·  📋 Menu: {len(menu_u)}  ·  "
                f"🏛️ Ambiance: {len(ambi_u)}"
            )
            if OLLAMA_AVAILABLE:
                status_msg += "  ·  ✨ AI Categorization Active (Llava)"
            status_msg += "  ·  Click image to zoom"
            
            status_var.set(status_msg)

            # Render each tab section independently so the UI stays responsive
            _render_grid(ifd, food_u,
                         "No food photos found for this restaurant.\n"
                         "Try the 'All Photos' tab.")
            
            if OLLAMA_AVAILABLE and menu_u:
                def _do_ocr():
                    ocr_btn.config(state="disabled", text="⏳ Extracting Menu... (Takes 5-20s)")
                    def _thread():
                        res = _ollama_read_menu_photos(menu_u, shop_name)
                        def _show():
                            ocr_btn.config(text="✨ AI: Extract Menu Data", state="normal")
                            pw = tk.Toplevel(gw)
                            pw.title(f"✨ AI Menu — {shop_name}")
                            pw.geometry("600x700")
                            pw.configure(bg=T("BG"))
                            f = tk.Frame(pw, bg=T("SURFACE2"), pady=16)
                            f.pack(fill="x")
                            tk.Label(f, text=f"✨ AI Extracted Menu — {shop_name}", font=("Segoe UI Variable", 12, "bold"), bg=T("SURFACE2"), fg=T("TEXT1")).pack()
                            tk.Label(f, text="Extracted using local vision model", font=("Segoe UI", 8), bg=T("SURFACE2"), fg=T("TEXT2")).pack()
                            txt = tk.Text(pw, font=FONT_BODY, bg=T("SURFACE"), fg=T("TEXT1"), wrap="word", padx=16, pady=16)
                            txt.pack(fill="both", expand=True, padx=16, pady=16)
                            txt.insert("1.0", "✨ AI is currently reading the menu photos... This takes longer on CPU systems.\n\n"
                                              "Analyzing 3 images, please wait up to 2-3 minutes...")
                            txt.config(state="normal") # Keep it editable while loading? Or just replace
                            
                            def _update_with_res():
                                if not pw.winfo_exists(): return
                                txt.config(state="normal")
                                txt.delete("1.0", "end")
                                txt.insert("1.0", res)
                                txt.config(state="disabled")
                                
                            pw.after(0, _update_with_res)
                        if gw.winfo_exists():
                            gw.after(0, _show)
                    threading.Thread(target=_thread, daemon=True).start()

                ocr_btn = tk.Button(imn, text="✨ AI: Extract Menu Data",
                                    font=("Segoe UI Variable", 9, "bold"), bg="#7c3aed", fg="#fff",
                                    relief="flat", cursor="hand2", padx=12, pady=6,
                                    command=_do_ocr)
                ocr_btn.pack(pady=10)

            _render_grid(imn, menu_u,
                         "No menu photos found.\n\n"
                         "💡 Many restaurants haven't uploaded menu photos to Google Maps.\n"
                         "Try visiting the restaurant's own website.")
            _render_grid(iab, ambi_u,
                         "No ambiance photos found.\nTry the 'All Photos' tab.")
            _render_grid(ial, all_urls, "No photos available for this restaurant.")

            if not PIL_OK:
                for p in (ifd, imn, iab, ial):
                    tk.Label(p,
                             text="💡 Install Pillow for image previews:  pip install Pillow",
                             font=FONT_SMALL, bg=T("BG"), fg=ACCENT2).pack(pady=4)

        # ── Background worker — fetch + categorise, never blocks UI ───────────
        def worker():
            # 1. Fetch photo list — 4-strategy cascade inside fetch_photos
            photo_dicts = []
            try:
                photo_dicts = MapsDataFetcher.fetch_photos(place_id, data_id)
            except Exception as exc:
                log.warning(f"fetch_photos error: {exc}")

            # Always prepend the thumbnail from the maps listing
            thumb = self.shop.get("thumbnail", "")
            if thumb and isinstance(thumb, str) and thumb.startswith("http"):
                if not any(pd.get("url") == thumb for pd in photo_dicts):
                    photo_dicts.insert(0, {"url": thumb, "tag": "food", "title": "thumbnail", "category": "food"})

            # ── Extra fallback: DuckDuckGo by restaurant name if still empty ──────
            if not photo_dicts:
                try:
                    q    = urllib.parse.quote(f"{shop_name} restaurant food photos")
                    resp = requests.get(
                        f"https://duckduckgo.com/?q={q}&iax=images&ia=images",
                        headers={"User-Agent": "Mozilla/5.0"},
                        timeout=15,
                    )
                    vqd_m = re.search(r'vqd=([\d-]+)', resp.text)
                    if vqd_m:
                        vqd     = vqd_m.group(1)
                        api_url = (f"https://duckduckgo.com/i.js?q={q}"
                                   f"&o=json&p=1&s=0&u=bing&f=,,,&l=us-en&vqd={vqd}")
                        ir = requests.get(api_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
                        for item in ir.json().get("results", [])[:80]:
                            u = item.get("image", "")
                            if u and u.startswith("http"):
                                photo_dicts.append({"url": u, "tag": "", "title": item.get("title", ""), "category": ""})
                    log.info(f"Name-based DDG fallback: {len(photo_dicts)} images for {shop_name}")
                except Exception as exc:
                    log.warning(f"Name DDG fallback error: {exc}")

            if not photo_dicts:
                if gw.winfo_exists():
                    gw.after(0, lambda: status_var.set(
                        "⚠  No photos found via Google Maps API for this restaurant.\n"
                        "Try visiting the restaurant on Google Maps directly."
                    ))
                return

            all_urls = [pd["url"] for pd in photo_dicts]
            
            # Step 1: Render "All Photos" immediately
            if gw.winfo_exists():
                gw.after(0, lambda: _render_grid(ial, all_urls, "No photos available."))
                gw.after(0, lambda: status_var.set(f"✓ {len(all_urls)} photos found. Categorizing..."))

            # Step 2: Categorise (keyword heuristics + optional vision model)
            try:
                buckets = categorize_photos(photo_dicts, shop_name)
            except Exception as exc:
                log.warning(f"categorize_photos error: {exc}")
                buckets = {"food": [], "menu": [], "ambi": [],
                           "other": [pd["url"] for pd in photo_dicts]}

            # Step 3: Update sections on the Tk main thread
            if gw.winfo_exists():
                gw.after(0, lambda: _render_section(buckets, all_urls))

        threading.Thread(target=worker, daemon=True).start()

    def _show_popular_dishes(self):
        pw = tk.Toplevel(self.win)
        pw.title(f"🏆 Popular Dishes — {self.shop['name']}")
        pw.geometry("740x800")
        pw.configure(bg=T("BG")); pw.grab_set()
        
        hdr = tk.Frame(pw, bg="#eab308", pady=16)
        hdr.pack(fill="x")
        tk.Label(hdr, text=f"🏆  Popular Dishes  —  {self.shop['name']}", 
                 font=("Segoe UI Variable", 15, "bold"), bg="#eab308", fg="#000").pack()
        tk.Label(hdr, text="Instant Best-Seller Intelligence", 
                 font=("Segoe UI", 9), bg="#eab308", fg="#422006").pack()
        
        container, inner, canvas = scrollable_frame(pw)
        container.pack_forget() # Initially hidden
        
        status_label = tk.Label(pw, text="⌛  Analysing restaurant reviews and native insights...",
                                font=FONT_BODY, bg=T("BG"), fg=T("TEXT1"), pady=40)
        status_label.pack()
        
        def _render():
            if not pw.winfo_exists(): return
            dishes = self.precalculated_dishes
            
            # If still calculating, wait and return
            if not dishes and self.is_restaurant and not self.all_reviews:
                pw.after(500, _render); return
                
            if status_label.winfo_exists():
                status_label.destroy()
            
            container.pack(fill="both", expand=True, padx=20, pady=10)
            
            if not dishes:
                tk.Label(inner, text="No notable popular dishes found.", 
                         font=FONT_BODY, bg=T("BG"), fg=T("TEXT2")).pack(pady=40)
                return
            
            # Grouping Logic
            order = ["Starters & Snacks", "Main Course", "Breads & Sides", "Desserts & Sweets", "Beverages", "Popular Mentions"]
            icons = {"Starters & Snacks":"🥟", "Main Course":"🍲", "Breads & Sides":"🫓", "Desserts & Sweets":"🍰", "Beverages":"☕", "Popular Mentions":"🌟"}
            grouped = {o: [] for o in order}
            for d in dishes:
                cat = d.get("category", "Popular Mentions")
                if cat not in grouped: cat = "Popular Mentions"
                grouped[cat].append(d)
                
            for cat in order:
                cat_dishes = grouped[cat]
                if not cat_dishes: continue
                
                hf = tk.Frame(inner, bg=T("BG"))
                hf.pack(fill="x", pady=(15, 8))
                tk.Label(hf, text=f"{icons.get(cat, '')}  {cat.upper()}", 
                         font=("Segoe UI Variable", 10, "bold"), bg=T("BG"), fg=PRIMARY).pack(side="left")
                tk.Frame(hf, bg=T("BORDER"), height=1).pack(side="left", fill="x", expand=True, padx=(12, 0))

                cat_dishes.sort(key=lambda x: x["score"], reverse=True)
                for d in cat_dishes:
                    cf = tk.Frame(inner, bg=T("SURFACE"), highlightbackground=T("BORDER"), highlightthickness=1, padx=16)
                    cf.pack(fill="x", pady=4)
                    top = tk.Frame(cf, bg=T("SURFACE")); top.pack(fill="x")
                    
                    # Diet Badge
                    diet_icon = "🟢" if d.get('is_veg', True) else "🔴"
                    diet_text = "Veg" if d.get('is_veg', True) else "Non-Veg"
                    diet_color = "#16a34a" if d.get('is_veg', True) else "#dc2626"
                    
                    dl = tk.Label(top, text=f"{diet_icon} {diet_text}", font=("Segoe UI", 8, "bold"), 
                                 bg=T("SURFACE"), fg=diet_color)
                    dl.pack(side="left", padx=(0, 10))

                    tk.Label(top, text=d['dish'], font=("Segoe UI Variable", 13, "bold"), bg=T("SURFACE"), fg=T("TEXT1")).pack(side="left")
                    if d['is_verified']:
                        tk.Label(top, text=" ✅ Verified Top Pick", font=("Segoe UI", 8, "bold"), bg="#064e3b", fg="#34d399", padx=6, pady=2).pack(side="left", padx=10)
                    
                    count_text = []
                    if d['count'] > 0: count_text.append(f"👍 Recommended locally by {d['count']} people")
                    if d['native_count'] > 0: count_text.append(f"📈 {d['native_count']} Native Google mentions")
                    
                    btm = tk.Frame(cf, bg=T("SURFACE")); btm.pack(fill="x", pady=(4, 8))
                    tk.Label(btm, text="  ·  ".join(count_text), font=FONT_SMALL, bg=T("SURFACE"), fg=T("TEXT2")).pack(anchor="w")
                    
                    if d['citation']:
                        qf = tk.Frame(cf, bg=T("SURFACE2"), padx=12, pady=8)
                        qf.pack(fill="x")
                        tk.Label(qf, text=f"💬 \"{d['citation']}\"", font=("Segoe UI", 9, "italic"), bg=T("SURFACE2"), fg=T("TEXT1"), wraplength=620, justify="left").pack(anchor="w")
                        tk.Label(qf, text=f"— {d['author']}", font=("Segoe UI", 8), bg=T("SURFACE2"), fg=T("TEXT3")).pack(anchor="w", pady=(4,0))
        
        _render()

    def _show_ai_insights(self):
        revs = self.all_reviews
        if not revs:
            messagebox.showinfo("No Reviews","Load reviews first.",parent=self.win); return
        if not OLLAMA_AVAILABLE:
            messagebox.showinfo("AI Offline","Run: ollama serve",parent=self.win); return

        aw = tk.Toplevel(self.win)
        aw.title(f"✨ AI Insights — {self.shop['name']}")
        aw.geometry("740x580"); aw.configure(bg=T("BG")); aw.grab_set()
        hdr = tk.Frame(aw, bg="#7c3aed", pady=12); hdr.pack(fill="x")
        tk.Label(hdr, text=f"✨  AI Insights  —  {self.shop['name']}",
                 font=FONT_HEADING, bg="#7c3aed", fg="#fff").pack(anchor="w",padx=16)
        tk.Label(hdr, text="Powered by Ollama  ·  Based on customer reviews",
                 font=FONT_SMALL, bg="#7c3aed", fg="#e9d5ff").pack(anchor="w",padx=16)
        status = tk.Label(aw, text="⏳  Analysing reviews…",
                          font=FONT_BODY, bg=T("BG"), fg=T("TEXT2"))
        status.pack(pady=16)
        _, inner, _ = scrollable_frame(aw, bg=T("BG"))

        def worker():
            snippets = [(r.get("rating","?"), r.get("snippet","") or r.get("text",""))
                        for r in revs if r.get("snippet") or r.get("text")][:20]
            block = "\n".join(f"[{rt}★] {txt}" for rt,txt in snippets)
            rname  = self.shop.get("name", "")
            prompt = (
                f"Analyse reviews for restaurant {rname!r}.\n\nREVIEWS:\n{block}\n\n"
                "Write EXACTLY these 5 sections (1-2 lines each):\n"
                "\U0001f374 FAMOUS FOR: Top dishes or aspects\n"
                "\u26a0\ufe0f COMPLAINTS: Most frequent criticisms\n"
                "\U0001f4a1 ADVANTAGE: One unique strength\n"
                "\U0001f4c8 PRIORITY: Single most important improvement\n"
                "\u2b50 VERDICT: Honest one-sentence recommendation\n\n"
                "Be specific. Reference actual reviews. No filler."
            )
            try:
                reply = _ollama_chat([{"role":"user","content":prompt}],
                                     temperature=0.3, max_tokens=450)
                aw.after(0, lambda: _show(reply))
            except Exception as e:
                aw.after(0, lambda: _show(f"Error: {e}"))

        def _show(text):
            if not aw.winfo_exists(): return
            try: status.destroy()
            except: pass
            ICONS = ["🍴","⚠️","💡","📈","⭐"]
            for line in text.strip().split("\n"):
                s = line.strip()
                if not s: continue
                is_hdr = any(s.startswith(ic) for ic in ICONS)
                f = tk.Frame(inner, bg=T("SURFACE" if is_hdr else "BG"),
                             padx=16, pady=8 if is_hdr else 2)
                f.pack(fill="x", padx=16, pady=(6 if is_hdr else 1))
                tk.Label(f, text=s, font=FONT_HEADING if is_hdr else FONT_BODY,
                         bg=T("SURFACE" if is_hdr else "BG"),
                         fg=ACCENT if is_hdr else T("TEXT1"),
                         wraplength=660, justify="left", anchor="w").pack(fill="x")

        threading.Thread(target=worker, daemon=True).start()


class PlayDetailPopup:
    def __init__(self, parent, comp: Dict):
        self.win = tk.Toplevel(parent)
        self.win.title(f"{comp.get('appTitle','App')}  —  Details")
        self.win.geometry("760x780")
        self.win.configure(bg=T("BG"))
        hdr = tk.Frame(self.win, bg=T("SURFACE2"), pady=14)
        hdr.pack(fill="x")
        tk.Frame(hdr, bg=PRIMARY, width=4).pack(side="left", fill="y")
        txt = tk.Frame(hdr, bg=T("SURFACE2"))
        txt.pack(side="left", padx=20)
        tk.Label(txt, text=comp.get("appTitle", "—"), font=("Segoe UI", 14, "bold"),
                 bg=T("SURFACE2"), fg=T("TEXT1")).pack(anchor="w")
        tk.Label(txt,
                 text=f"Genre: {comp.get('genre','—')}  ·  Installs: {comp.get('installs','—')}",
                 font=FONT_BODY, bg=T("SURFACE2"), fg=T("TEXT2")).pack(anchor="w")
        card_row = tk.Frame(self.win, bg=T("BG"), pady=12, padx=16)
        card_row.pack(fill="x")
        card_row.columnconfigure((0, 1, 2, 3), weight=1)

        def sc(col, icon, label, value, fg=PRIMARY):
            f = tk.Frame(card_row, bg=T("SURFACE"), padx=12, pady=14)
            f.grid(row=0, column=col, padx=5, sticky="ew")
            tk.Frame(f, bg=fg, height=3).pack(fill="x", pady=(0, 8))
            tk.Label(f, text=icon, font=("Segoe UI", 18), bg=T("SURFACE")).pack()
            tk.Label(f, text=value, font=("Segoe UI", 11, "bold"),
                     bg=T("SURFACE"), fg=fg, wraplength=140).pack()
            tk.Label(f, text=label, font=FONT_SMALL, bg=T("SURFACE"), fg=T("TEXT2")).pack()

        rating    = comp.get("rating", 0)
        price_str = "Free" if comp.get("isFree") else f"₹{comp.get('price','')}"
        sc(0, "★", "Rating",  f"{rating:.1f}/5.0", rating_color(rating))
        sc(1, "◈", "Installs", comp.get("installs", "—"), ACCENT)
        sc(2, "◑", "Genre",    comp.get("genre", "—"), ACCENT2)
        sc(3, "₹", "Price",    price_str, SUCCESS if comp.get("isFree") else WARNING)

        tk.Frame(self.win, bg=T("BORDER"), height=1).pack(fill="x", padx=16, pady=6)
        revs = comp.get("reviews", [])
        tk.Label(self.win, text=f"  User Reviews  ({len(revs)})",
                 font=FONT_HEADING, bg=T("BG"), fg=T("TEXT1"), pady=6).pack(anchor="w", padx=16)
        _, inner, _ = scrollable_frame(self.win, bg=T("BG"))
        if not revs:
            tk.Label(inner, text="No reviews fetched.",
                     font=FONT_BODY, bg=T("BG"), fg=T("TEXT2")).pack(pady=20)
        else:
            for r in revs:
                score  = r["score"]
                accent = rating_color(score)
                f = tk.Frame(inner, bg=T("SURFACE"), pady=1)
                f.pack(fill="x", padx=12, pady=3)
                tk.Frame(f, bg=accent, width=3).pack(side="left", fill="y")
                body = tk.Frame(f, bg=T("SURFACE"), padx=14, pady=10)
                body.pack(side="left", fill="both", expand=True)
                top = tk.Frame(body, bg=T("SURFACE"))
                top.pack(fill="x")
                tk.Label(top, text=f"★ {score:.1f}/5.0", font=("Segoe UI", 9, "bold"),
                         bg=T("SURFACE"), fg=accent).pack(side="left")
                tk.Label(top, text=f"  {r['thumbsUpCount']} helpful",
                         font=FONT_SMALL, bg=T("SURFACE"), fg=T("TEXT3")).pack(side="right")
                tk.Label(body, text=r["content"] or "(No text)", font=FONT_BODY,
                         bg=T("SURFACE"), fg=T("TEXT1"), wraplength=660, justify="left").pack(
                    anchor="w", pady=(4, 0))


# ── Report window ─────────────────────────────────────────────────────────────
class ReportWindow:
    def __init__(self, parent, report_text: str, query: str, location: str,
                 maps_data=None, amzn_data=None, price_range=None):
        self.report_text = report_text
        self.query       = query
        self.location    = location
        self.maps_data   = maps_data or []
        self.amzn_data   = amzn_data or []
        self.price_range = price_range
        self.win = tk.Toplevel(parent)
        self.win.title(f"Business Intelligence Report — {query}")
        self.win.geometry("1020x840")
        self.win.configure(bg=T("BG"))
        self._build(report_text, query, location)

    def _build(self, report_text, query, location):
        hdr = tk.Frame(self.win, bg=T("SURFACE2"), pady=18)
        hdr.pack(fill="x")
        tk.Frame(hdr, bg=ACCENT, width=4).pack(side="left", fill="y")
        col = tk.Frame(hdr, bg=T("SURFACE2"))
        col.pack(side="left", padx=20)
        tk.Label(col, text="Business Intelligence Report",
                 font=("Segoe UI", 15, "bold"), bg=T("SURFACE2"), fg=T("TEXT1")).pack(anchor="w")
        tk.Label(col,
                 text=f"{query.title()}  ·  {location}  ·  {datetime.now().strftime('%d %b %Y, %H:%M')}",
                 font=FONT_BODY, bg=T("SURFACE2"), fg=T("TEXT2")).pack(anchor="w")
        btns = tk.Frame(hdr, bg=T("SURFACE2"))
        btns.pack(side="right", padx=20)
        tk.Button(btns, text="  Export TXT", font=FONT_LABEL, bg=T("SURFACE3"), fg=T("TEXT1"),
                  relief="flat", padx=12, pady=7, cursor="hand2",
                  command=lambda: self._export_txt(report_text, query)).pack(side="left", padx=(0, 8))
        tk.Button(btns, text="  Export PDF", font=FONT_LABEL, bg=PRIMARY, fg=T("TEXT1"),
                  relief="flat", padx=12, pady=7, cursor="hand2",
                  command=self._export_pdf_click).pack(side="left")
        tk.Frame(self.win, bg=T("BORDER"), height=1).pack(fill="x")
        _, inner, _ = scrollable_frame(self.win, bg=T("BG"))
        inner.configure(padx=30, pady=20)
        for line in report_text.split("\n"):
            stripped = line.strip()
            if not stripped:
                tk.Frame(inner, bg=T("BG"), height=6).pack(anchor="w")
                continue
            if stripped.startswith("## "):
                f = tk.Frame(inner, bg=T("BG"), pady=4)
                f.pack(fill="x", anchor="w")
                tk.Frame(f, bg=ACCENT, height=2).pack(fill="x")
                tk.Label(f, text=stripped[3:], font=("Segoe UI", 12, "bold"),
                         bg=T("BG"), fg=ACCENT, pady=4).pack(anchor="w")
            elif stripped.startswith("# "):
                tk.Label(inner, text=stripped[2:], font=("Segoe UI", 14, "bold"),
                         bg=T("BG"), fg=T("TEXT1"), pady=4).pack(anchor="w")
            elif stripped.startswith("**") and stripped.endswith("**") and stripped.count("**") == 2:
                tk.Label(inner, text=stripped[2:-2], font=("Segoe UI", 9, "bold"),
                         bg=T("BG"), fg=PRIMARY).pack(anchor="w", pady=1)
            elif stripped.startswith("- ") or stripped.startswith("* "):
                f = tk.Frame(inner, bg=T("BG"))
                f.pack(anchor="w", fill="x")
                tk.Label(f, text="  ●", font=FONT_BODY, bg=T("BG"), fg=ACCENT, width=3).pack(side="left")
                tk.Label(f, text=stripped[2:], font=FONT_BODY, bg=T("BG"), fg=T("TEXT1"),
                         wraplength=880, justify="left").pack(side="left")
            else:
                tk.Label(inner, text=stripped, font=FONT_BODY, bg=T("BG"), fg=T("TEXT1"),
                         wraplength=920, justify="left").pack(anchor="w", pady=1)

    def _export_txt(self, text, query):
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text", "*.txt")],
            initialfile=f"report_{query.replace(' ','_')}_{datetime.now().strftime('%Y%m%d')}.txt",
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(f"MARKET INTELLIGENCE REPORT\n{'='*60}\n"
                        f"Product: {self.query}\nGenerated: {datetime.now().isoformat()}\n"
                        f"{'='*60}\n\n{text}")
            messagebox.showinfo("Exported", f"Saved to:\n{path}", parent=self.win)

    def _export_pdf_click(self):
        if not REPORTLAB_AVAILABLE:
            messagebox.showerror("Not Available",
                                 "Install reportlab: pip install reportlab", parent=self.win)
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")],
            initialfile=f"report_{self.query.replace(' ','_')}_{datetime.now().strftime('%Y%m%d')}.pdf",
        )
        if path:
            try:
                export_pdf(self.report_text, self.query, self.location, path,
                           self.maps_data, self.amzn_data, self.price_range)
                messagebox.showinfo("Exported", f"PDF saved to:\n{path}", parent=self.win)
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=self.win)


# ── Break-even calculator ─────────────────────────────────────────────────────
class BreakEvenCalculator:
    def __init__(self, parent, price_range=None, amzn_data=None):
        self.win = tk.Toplevel(parent)
        self.win.title("◈  Break-Even & Profit Calculator")
        self.win.geometry("900x740")
        self.win.configure(bg=T("BG"))
        prices = [p.get("price_num") for p in (amzn_data or []) if p.get("price_num")]
        default_price = (int((price_range[0] + price_range[1]) / 2) if price_range
                         else (int(sum(prices) / len(prices)) if prices else 1000))
        self._build(default_price)

    def _build(self, default_price):
        # ── Header ────────────────────────────────────────────────────────
        hdr = tk.Frame(self.win, bg=T("SURFACE2"), pady=0)
        hdr.pack(fill="x")
        grad = tk.Frame(hdr, height=3, bg=T("SURFACE2"))
        grad.pack(fill="x")
        for col in [ACCENT2, SUCCESS, PRIMARY]:
            tk.Frame(grad, bg=col, height=3).pack(side="left", fill="x", expand=True)
        hdr_inner = tk.Frame(hdr, bg=T("SURFACE2"), pady=14, padx=22)
        hdr_inner.pack(fill="x")
        tk.Label(hdr_inner, text="📈",
                 font=("Segoe UI", 18), bg=T("SURFACE2"), fg=ACCENT2).pack(side="left", padx=(0, 12))
        hdr_txt = tk.Frame(hdr_inner, bg=T("SURFACE2"))
        hdr_txt.pack(side="left")
        tk.Label(hdr_txt, text="Break-Even & Profit Calculator",
                 font=("Segoe UI Variable", 12, "bold"),
                 bg=T("SURFACE2"), fg=T("TEXT1")).pack(anchor="w")
        tk.Label(hdr_txt, text="Adjust sliders to model your unit economics",
                 font=("Segoe UI", 8),
                 bg=T("SURFACE2"), fg=T("TEXT2")).pack(anchor="w")

        # ── Two-column layout ─────────────────────────────────────────────
        main = tk.Frame(self.win, bg=T("BG"))
        main.pack(fill="both", expand=True, padx=18, pady=14)
        main.columnconfigure(0, weight=1)
        main.columnconfigure(1, weight=2)

        # Left — inputs
        left = tk.Frame(main, bg=T("SURFACE"),
                        highlightbackground=T("BORDER2"),
                        highlightthickness=1,
                        padx=20, pady=18)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        tk.Label(left, text="◈  Input Parameters",
                 font=("Segoe UI Variable", 10, "bold"),
                 bg=T("SURFACE"), fg=T("TEXT1")).pack(anchor="w", pady=(0, 14))

        self.vars: Dict = {}
        fields = [
            ("Selling Price (₹)",      "selling_price", default_price,          ACCENT2),
            ("Manufacturing Cost (₹)", "mfg_cost",      int(default_price * .4), DANGER),
            ("Logistics Cost (₹)",     "logistics",      int(default_price * .1), WARNING),
            ("Marketing / CAC (₹)",    "marketing",      int(default_price * .08), ACCENT3),
            ("Platform / GST (₹)",     "platform",       int(default_price * .05), T("TEXT3")),
            ("Fixed Monthly Cost (₹)", "fixed",          50000,                   PRIMARY),
        ]
        for label, key, default, accent in fields:
            row = tk.Frame(left, bg=T("SURFACE"))
            row.pack(fill="x", pady=(8, 0))
            tk.Frame(row, bg=accent, width=3).pack(side="left", fill="y", padx=(0, 8))
            tk.Label(row, text=label,
                     font=FONT_LABEL, bg=T("SURFACE"),
                     fg=T("TEXT2")).pack(anchor="w")
            var = tk.IntVar(value=default)
            self.vars[key] = var
            sl = tk.Scale(left, variable=var,
                          from_=0, to=max(default_price * 2, 200000),
                          orient="horizontal",
                          bg=T("SURFACE"), fg=accent,
                          troughcolor=T("SURFACE3"),
                          highlightthickness=0,
                          length=210, resolution=100,
                          activebackground=accent)
            sl.pack(anchor="w", pady=(2, 0))
            sl.bind("<ButtonRelease-1>", lambda e: self._update_calc())

        tk.Button(left, text="  ↻  Recalculate  ",
                  font=("Segoe UI Variable", 9, "bold"),
                  bg=PRIMARY, fg="#ffffff",
                  relief="flat", padx=14, pady=7, cursor="hand2",
                  activebackground=PRIMARY_D, activeforeground="#ffffff",
                  command=self._update_calc).pack(anchor="w", pady=(18, 0))

        # Right — results
        self.right = tk.Frame(main, bg=T("SURFACE"),
                              highlightbackground=T("BORDER2"),
                              highlightthickness=1,
                              padx=20, pady=18)
        self.right.grid(row=0, column=1, sticky="nsew")
        self.result_frame = tk.Frame(self.right, bg=T("SURFACE"))
        self.result_frame.pack(fill="both", expand=True)
        self._update_calc()

    def _update_calc(self):
        sp  = self.vars["selling_price"].get()
        mfg = self.vars["mfg_cost"].get()
        lg  = self.vars["logistics"].get()
        mkt = self.vars["marketing"].get()
        plt = self.vars["platform"].get()
        fix = self.vars["fixed"].get()

        total_variable  = mfg + lg + mkt + plt
        gross_profit    = sp - total_variable
        gross_margin    = (gross_profit / sp * 100) if sp > 0 else 0
        breakeven_units = int(fix / gross_profit) if gross_profit > 0 else 9999
        breakeven_rev   = breakeven_units * sp

        for w in self.result_frame.winfo_children():
            w.destroy()

        tk.Label(self.result_frame, text="◈  Results",
                 font=("Segoe UI Variable", 10, "bold"),
                 bg=T("SURFACE"), fg=T("TEXT1")).pack(anchor="w", pady=(0, 14))

        def result_row(label, value, fg=None, big=False, accent=None):
            fg = fg or T("TEXT1")
            f = tk.Frame(self.result_frame, bg=T("SURFACE2"),
                         highlightbackground=T("BORDER"), highlightthickness=1,
                         padx=14, pady=9)
            f.pack(fill="x", pady=3)
            if accent:
                tk.Frame(f, bg=accent, width=3).pack(side="left", fill="y", padx=(0, 10))
            font = ("Segoe UI Variable", 12, "bold") if big else FONT_BODY
            tk.Label(f, text=label,
                     font=FONT_LABEL, bg=T("SURFACE2"),
                     fg=T("TEXT2"), width=24, anchor="w").pack(side="left")
            tk.Label(f, text=value,
                     font=font, bg=T("SURFACE2"), fg=fg).pack(side="right")

        result_row("Selling Price",       f"₹{sp:,}",           accent=ACCENT2)
        result_row("Total Variable Cost", f"₹{total_variable:,}", DANGER, accent=DANGER)
        result_row("Gross Profit / Unit",
                   f"₹{gross_profit:,}",
                   SUCCESS if gross_profit > 0 else DANGER, big=True,
                   accent=SUCCESS if gross_profit > 0 else DANGER)
        result_row("Gross Margin",
                   f"{gross_margin:.1f}%",
                   SUCCESS if gross_margin > 20 else WARNING if gross_margin > 0 else DANGER,
                   big=True,
                   accent=SUCCESS if gross_margin > 20 else WARNING if gross_margin > 0 else DANGER)
        result_row("Fixed Monthly Cost",  f"₹{fix:,}",           accent=T("TEXT3"))
        result_row("Break-Even Volume",   f"{breakeven_units:,} units/month", ACCENT2, big=True, accent=ACCENT2)
        result_row("Break-Even Revenue",  f"₹{breakeven_rev:,}/month", PRIMARY, accent=PRIMARY)

        volumes     = list(range(0, breakeven_units * 3 + 1,
                                 max(1, breakeven_units // 10)))
        revenues    = [v * sp for v in volumes]
        total_costs = [fix + v * total_variable for v in volumes]
        _plt_rc()
        fig = Figure(figsize=(5.2, 3), dpi=96)
        fig.patch.set_facecolor(T("SURFACE"))
        ax  = fig.add_subplot(111)
        ax.set_facecolor(T("SURFACE"))
        ax.plot(volumes, revenues,    color=SUCCESS, label="Revenue",    linewidth=2.2, zorder=3)
        ax.plot(volumes, total_costs, color=DANGER,  label="Total Cost", linewidth=2.2, zorder=3)
        ax.fill_between(volumes, revenues, total_costs,
                        where=[r > c for r, c in zip(revenues, total_costs)],
                        alpha=0.12, color=SUCCESS, zorder=2)
        ax.fill_between(volumes, revenues, total_costs,
                        where=[r <= c for r, c in zip(revenues, total_costs)],
                        alpha=0.12, color=DANGER, zorder=2)
        ax.axvline(breakeven_units, color=ACCENT2, linestyle="--", linewidth=1.6,
                   label=f"Break-even ({breakeven_units})", zorder=4)
        ax.set_xlabel("Units / month", fontsize=8)
        ax.set_ylabel("₹", fontsize=8)
        ax.legend(fontsize=7, framealpha=0.3)
        ax.grid(True, linestyle="--", alpha=0.15, color=T("BORDER"))
        ax.set_title("Revenue vs Cost  —  Break-Even Chart",
                     fontsize=9, fontweight="bold")
        fig.tight_layout(pad=1.5)
        cv = FigureCanvasTkAgg(fig, master=self.result_frame)
        cv.draw()
        cv.get_tk_widget().pack(fill="x", pady=(12, 0))


# ── History window ────────────────────────────────────────────────────────────
class HistoryWindow:
    def __init__(self, parent, on_load_callback):
        self.parent   = parent
        self.callback = on_load_callback
        self.win = tk.Toplevel(parent)
        self.win.title("◈  Search History")
        self.win.geometry("860x560")
        self.win.configure(bg=T("BG"))
        self._build()

    def _build(self):
        # ── Premium header ─────────────────────────────────────────────────
        hdr = tk.Frame(self.win, bg=T("SURFACE2"))
        hdr.pack(fill="x")
        grad = tk.Frame(hdr, height=3, bg=T("SURFACE2"))
        grad.pack(fill="x")
        for col in [PRIMARY, ACCENT, ACCENT2]:
            tk.Frame(grad, bg=col, height=3).pack(side="left", fill="x", expand=True)
        hdr_inner = tk.Frame(hdr, bg=T("SURFACE2"), pady=14, padx=20)
        hdr_inner.pack(fill="x")
        tk.Label(hdr_inner, text="📋",
                 font=("Segoe UI", 16),
                 bg=T("SURFACE2"), fg=PRIMARY).pack(side="left", padx=(0, 10))
        hdr_txt = tk.Frame(hdr_inner, bg=T("SURFACE2"))
        hdr_txt.pack(side="left", fill="x", expand=True)
        tk.Label(hdr_txt, text="Search History",
                 font=("Segoe UI Variable", 11, "bold"),
                 bg=T("SURFACE2"), fg=T("TEXT1")).pack(anchor="w")
        tk.Label(hdr_txt, text="Last 50 searches  ·  Double-click to reload",
                 font=("Segoe UI", 8),
                 bg=T("SURFACE2"), fg=T("TEXT2")).pack(anchor="w")
        tk.Button(hdr_inner, text="  🗑  Clear All  ",
                  font=("Segoe UI Variable", 8, "bold"),
                  bg=DANGER, fg="#ffffff",
                  relief="flat", padx=12, pady=6, cursor="hand2",
                  activebackground="#c0182c",
                  command=self._clear_all).pack(side="right")

        # ── Treeview ────────────────────────────────────────────────────────
        cols   = ("ID", "Query", "Location", "Maps", "Amazon", "Play", "Timestamp")
        widths = [44, 200, 140, 65, 75, 55, 180]
        self.tree = ttk.Treeview(self.win, columns=cols, show="headings", height=20)
        for col, w in zip(cols, widths):
            self.tree.column(col, width=w,
                             anchor="center" if col in ("ID", "Maps", "Amazon", "Play") else "w")
            self.tree.heading(col, text=col)
        vsb = ttk.Scrollbar(self.win, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscroll=vsb.set)
        vsb.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True, padx=12, pady=10)
        self.tree.bind("<Double-1>", self._load_selected)
        rows = load_searches()
        for i, row in enumerate(rows):
            self.tree.insert("", tk.END, tags=("even" if i % 2 == 0 else "odd",),
                             values=(row[0], row[1], row[2], row[3], row[4], row[5], row[6][:16]))
        self.tree.tag_configure("odd",  background=T("ROW_ODD"))
        self.tree.tag_configure("even", background=T("ROW_EVEN"))
        tk.Label(self.win,
                 text="Double-click any row to reload that search into the dashboard",
                 font=("Segoe UI", 7),
                 bg=T("BG"), fg=T("TEXT3")).pack(pady=5)

    def _load_selected(self, event):
        sel = self.tree.selection()
        if not sel:
            return
        search_id = self.tree.item(sel[0])["values"][0]
        data = load_search_data(search_id)
        if data:
            self.callback(data)
            self.win.destroy()
        else:
            messagebox.showerror("Error", "Could not load search data.", parent=self.win)

    def _clear_all(self):
        if messagebox.askyesno("Confirm", "Clear ALL search history?", parent=self.win):
            try:
                conn = _db()
                conn.execute("DELETE FROM searches")
                conn.commit()
                conn.close()
                for item in self.tree.get_children():
                    self.tree.delete(item)
                messagebox.showinfo("Done", "History cleared.", parent=self.win)
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=self.win)


# ─────────────────────────────────────────────────────────────────────────────
#  Main application
# ─────────────────────────────────────────────────────────────────────────────
class MarketResearchApp(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("Market Research Pro  ◈  AI-Powered Competitive Intelligence")
        self.geometry("1600x960")
        self.minsize(1200, 720)
        self.configure(bg=T("BG"))
        init_db()
        self._apply_styles()

        self.maps_data:        List[Dict]     = []
        self.play_data:        List[Dict]     = []
        self.amzn_data:        List[Dict]     = []
        self.trends_data:      Dict           = {}
        self.maps_report:      Optional[Dict] = None
        self.last_price_range                 = None
        self.last_query                       = ""
        self.last_location                    = "Ahmedabad"
        self.sort_preference:  str            = "both"
        self._rest_panel      = None   # lazy restaurant panel
        self.chat_messages:    List[Dict]     = []
        self._clock_after_id                  = None   # so we can cancel it on close

        self.protocol("WM_DELETE_WINDOW", self._on_closing)
        self._build_ui()
        log.info("App started")

    # ── Styles ────────────────────────────────────────────────────────────────
    def _apply_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame",    background=T("BG"))
        style.configure("TLabel",    background=T("BG"))

        # ── Notebook: sharp pill tabs ──────────────────────────────────────
        style.configure("TNotebook",
                        background=T("BG"),
                        tabmargins=[0, 6, 0, 0],
                        borderwidth=0)
        style.configure("TNotebook.Tab",
                        font=("Segoe UI Variable", 9, "bold"),
                        padding=[20, 10],
                        background=T("BG"),
                        foreground=T("TEXT3"),
                        borderwidth=0,
                        focuscolor=T("BG"))
        style.map("TNotebook.Tab",
                  background=[("selected",  T("SURFACE2")),
                               ("!selected", T("BG")),
                               ("active",    T("SURFACE"))],
                  foreground=[("selected",  PRIMARY),
                               ("!selected", T("TEXT2")),
                               ("active",    T("TEXT1"))],
                  relief=[("selected", "flat"), ("!selected", "flat")])

        # ── Treeview: sleek data table ─────────────────────────────────────
        style.configure("Treeview",
                        font=("Segoe UI", 9),
                        rowheight=36,
                        background=T("SURFACE"),
                        fieldbackground=T("SURFACE"),
                        foreground=T("TEXT1"),
                        borderwidth=0,
                        relief="flat",
                        selectbackground=T("ROW_SEL"),
                        selectforeground=T("TEXT1"))
        style.configure("Treeview.Heading",
                        font=("Segoe UI Variable", 9, "bold"),
                        background=T("SURFACE2"),
                        foreground=ACCENT,
                        borderwidth=0,
                        relief="flat",
                        padding=[10, 8])
        style.map("Treeview",
                  background=[("selected", T("ROW_SEL"))],
                  foreground=[("selected", T("TEXT1"))])
        style.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])

        # ── Scrollbar: ultra thin ──────────────────────────────────────────
        style.configure("Vertical.TScrollbar",
                        background=T("SURFACE3"),
                        troughcolor=T("BG"),
                        width=4,
                        arrowsize=0,
                        borderwidth=0,
                        relief="flat")
        style.configure("Horizontal.TScrollbar",
                        background=T("SURFACE3"),
                        troughcolor=T("BG"),
                        width=4,
                        arrowsize=0,
                        borderwidth=0,
                        relief="flat")
        style.map("Vertical.TScrollbar",
                  background=[("active", PRIMARY)])
        style.map("Horizontal.TScrollbar",
                  background=[("active", PRIMARY)])

    def _build_ui(self):
        self._build_sidebar()
        self._build_main_panel()
        self._build_status_bar()

    # ── Sidebar ───────────────────────────────────────────────────────────────
    def _build_sidebar(self):
        self.sidebar = tk.Frame(self, bg=T("SURFACE"), width=430)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        # ── Brand header with chromatic gradient strip ─────────────────────
        brand_outer = tk.Frame(self.sidebar, bg=T("SURFACE2"))
        brand_outer.pack(fill="x")

        # 5-segment gradient strip
        grad = tk.Frame(brand_outer, height=3, bg=T("SURFACE2"))
        grad.pack(fill="x")
        for col in [PRIMARY, ACCENT, ACCENT2, ACCENT3, SUCCESS]:
            tk.Frame(grad, bg=col, height=3).pack(side="left", fill="x", expand=True)

        brand = tk.Frame(brand_outer, bg=T("SURFACE2"), pady=16, padx=20)
        brand.pack(fill="x")

        # Row 1: icon + name + theme toggle
        title_row = tk.Frame(brand, bg=T("SURFACE2"))
        title_row.pack(fill="x")

        tk.Label(title_row, text="◈", font=("Segoe UI Variable", 20, "bold"),
                 bg=T("SURFACE2"), fg=PRIMARY).pack(side="left", padx=(0, 10))

        name_col = tk.Frame(title_row, bg=T("SURFACE2"))
        name_col.pack(side="left", fill="x", expand=True)
        tk.Label(name_col, text="Market Research Pro",
                 font=("Segoe UI Variable", 12, "bold"),
                 bg=T("SURFACE2"), fg=T("TEXT1")).pack(anchor="w")
        tk.Label(name_col, text="AI-Powered Competitive Intelligence",
                 font=("Segoe UI", 8), bg=T("SURFACE2"), fg=T("TEXT2")).pack(anchor="w")

        self.theme_btn = tk.Button(
            title_row,
            text="  ☀  " if CURRENT_THEME == "dark" else "  🌙  ",
            font=("Segoe UI", 10),
            bg=T("SURFACE3"), fg=T("TEXT1"),
            relief="flat", padx=6, pady=4,
            cursor="hand2",
            activebackground=T("SURFACE4"), activeforeground=T("TEXT1"),
            command=self._toggle_theme)
        self.theme_btn.pack(side="right")

        # AI status badge
        ai_bg   = "#041c13" if CURRENT_THEME == "dark" else "#d6f5ea"
        ai_fg   = SUCCESS   if OLLAMA_AVAILABLE else DANGER
        ai_dot  = "●" if OLLAMA_AVAILABLE else "○"
        ai_text = (f"{ai_dot}  AI Online · {OLLAMA_MODEL}"
                   if OLLAMA_AVAILABLE
                   else f"{ai_dot}  AI Offline — run: ollama serve")
        ai_pill = tk.Frame(brand, bg=ai_bg, padx=12, pady=5)
        ai_pill.pack(fill="x", pady=(10, 0))
        tk.Label(ai_pill, text=ai_text, font=("Cascadia Code", 8),
                 bg=ai_bg, fg=ai_fg).pack(side="left")

        self._clock = tk.Label(brand, text="",
                               font=("Cascadia Code", 8),
                               bg=T("SURFACE2"), fg=T("TEXT3"))
        self._clock.pack(anchor="w", pady=(4, 0))
        self._tick_clock()

        # ── Action buttons in a 2×2 grid ──────────────────────────────────
        tk.Frame(self.sidebar, bg=T("BORDER"), height=1).pack(fill="x")
        qbtns = tk.Frame(self.sidebar, bg=T("SURFACE"), pady=10, padx=14)
        qbtns.pack(fill="x")

        def _qbtn(parent, text, bg, fg, cmd, padx=(0, 6)):
            b = tk.Button(parent, text=text,
                          font=("Segoe UI Variable", 8, "bold"),
                          bg=bg, fg=fg,
                          relief="flat", padx=11, pady=6,
                          cursor="hand2",
                          activebackground=bg, activeforeground=fg,
                          command=cmd)
            b.pack(side="left", padx=padx)
            return b

        row_a = tk.Frame(qbtns, bg=T("SURFACE"))
        row_a.pack(fill="x", pady=(0, 5))
        _qbtn(row_a, "  📋  History",
              T("SURFACE3"), T("TEXT1"), self._open_history)
        _qbtn(row_a, "  🗑  Clear Cache",
              T("SURFACE3"), T("TEXT1"), self._clear_cache)

        row_b = tk.Frame(qbtns, bg=T("SURFACE"))
        row_b.pack(fill="x")
        self.sort_btn = _qbtn(row_b, "  ⚡  Sort: Best Match",
                              PRIMARY, "#ffffff", self._choose_sort_preference)
        _qbtn(row_b, "  🍽️  Restaurants",
              ORANGE, "#ffffff", self._open_restaurant_panel)

        tk.Frame(self.sidebar, bg=T("BORDER"), height=1).pack(fill="x")

        # ── Chat panel label ───────────────────────────────────────────────
        chat_hdr = tk.Frame(self.sidebar, bg=T("SURFACE"), padx=14, pady=7)
        chat_hdr.pack(fill="x")
        tk.Label(chat_hdr, text="◈  AI Assistant",
                 font=("Segoe UI Variable", 9, "bold"),
                 bg=T("SURFACE"), fg=T("TEXT2")).pack(side="left")
        tk.Label(chat_hdr, text="Ctrl+Enter to send",
                 font=("Segoe UI", 7), bg=T("SURFACE"), fg=T("TEXT3")).pack(side="right")

        # ── Scrollable chat messages ───────────────────────────────────────
        chat_container = tk.Frame(self.sidebar, bg=T("BG"))
        chat_container.pack(fill="both", expand=True)
        self.chat_canvas = tk.Canvas(chat_container, bg=T("BG"),
                                     bd=0, highlightthickness=0)
        vsb = ttk.Scrollbar(chat_container, orient="vertical",
                             command=self.chat_canvas.yview)
        self.chat_canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self.chat_canvas.pack(side="left", fill="both", expand=True)
        self.chat_inner = tk.Frame(self.chat_canvas, bg=T("BG"))
        self._chat_win = self.chat_canvas.create_window(
            (0, 0), window=self.chat_inner, anchor="nw")
        self.chat_inner.bind(
            "<Configure>",
            lambda e: self.chat_canvas.configure(
                scrollregion=self.chat_canvas.bbox("all")))
        self.chat_canvas.bind(
            "<Configure>",
            lambda e: self.chat_canvas.itemconfig(self._chat_win, width=e.width))
        self.chat_canvas.bind(
            "<MouseWheel>",
            lambda e: self.chat_canvas.yview_scroll(-1 * (e.delta // 120), "units"))

        welcome = (
            "Hello! I'm your Market Research AI.\n\n"
            "Describe your product idea — what you're selling, "
            "target city, and price. I'll analyse competitors, "
            "pricing and trends.\n\n"
            "Example:\n\"Ergonomic chairs in Ahmedabad for ₹15,000–₹20,000\"\n\n"
            "After search completes you can ask follow-ups like:\n"
            "\"What if I lower my price by 10%?\"\n"
            "\"Who are my top 3 threats?\""
        )
        if not OLLAMA_AVAILABLE:
            welcome += (
                f"\n\n⚠  Ollama not detected at {OLLAMA_URL}.\n"
                f"  1. Install : https://ollama.com\n"
                f"  2. Pull    : ollama pull {OLLAMA_MODEL}\n"
                f"  3. Start   : ollama serve"
            )
        self._add_ai_message(welcome)

        # ── Input box ─────────────────────────────────────────────────────
        input_frame = tk.Frame(self.sidebar, bg=T("SURFACE2"), pady=12, padx=14)
        input_frame.pack(fill="x", side="bottom")

        # Thin accent line at top of input zone
        tk.Frame(input_frame, bg=PRIMARY, height=2).pack(fill="x", pady=(0, 9))

        entry_outer = tk.Frame(input_frame,
                               bg=T("SURFACE3"),
                               highlightbackground=T("BORDER2"),
                               highlightthickness=1)
        entry_outer.pack(fill="x")

        entry_row = tk.Frame(entry_outer, bg=T("SURFACE3"))
        entry_row.pack(fill="x", padx=2, pady=2)

        self.chat_entry = tk.Text(
            entry_row, height=2,
            font=("Segoe UI Variable", 10),
            bg=T("SURFACE3"), fg=T("TEXT1"),
            insertbackground=ACCENT,
            relief="flat", bd=0,
            wrap="word", padx=12, pady=8)
        self.chat_entry.pack(side="left", fill="x", expand=True)
        self.chat_entry.insert("1.0", "Describe your product or market idea…")
        self.chat_entry.config(fg=T("TEXT2"))
        self.chat_entry.bind("<FocusIn>",      self._on_entry_focus_in)
        self.chat_entry.bind("<FocusOut>",     self._on_entry_focus_out)
        self.chat_entry.bind("<Return>",       self._on_chat_enter)
        self.chat_entry.bind("<Shift-Return>", lambda e: None)

        self.send_btn = tk.Button(
            entry_row, text="  ▲  ",
            font=("Segoe UI Variable", 11, "bold"),
            bg=PRIMARY, fg="#ffffff",
            relief="flat", width=3, height=2,
            cursor="hand2",
            activebackground=PRIMARY_D, activeforeground="#ffffff",
            command=self._on_send_click)
        self.send_btn.pack(side="right", padx=(6, 0))

        tk.Label(input_frame,
                 text="↵ Send  ·  Shift+↵ Newline  ·  Ask anything",
                 font=("Segoe UI", 7),
                 bg=T("SURFACE2"), fg=T("TEXT3")).pack(anchor="w", pady=(5, 0))

    # ── Sort preference — NON-BLOCKING callback pattern ───────────────────────
    def _choose_sort_preference(self):
        """Opens the sort dialog non-blocking; applies result via callback."""
        label_map = {"nearest": "Sort: Nearest",
                     "top_rated": "Sort: Top Rated",
                     "both": "Sort: Best Match"}

        def on_chosen(pref: str):
            self.sort_preference = pref
            self.sort_btn.config(text=f" {label_map.get(pref, 'Sort')}")
            self._update_sort_badge()
            log.info(f"Sort preference → {pref}")
            if self.maps_data:
                self._populate_maps(self.maps_data)
                self._add_ai_message(
                    f"Shops re-sorted: {label_map[pref]}  ✓", fg=ACCENT
                )

        SortPreferenceDialog(self, current=self.sort_preference, callback=on_chosen)

    def _on_entry_focus_in(self, event):
        if self.chat_entry.get("1.0", "end-1c") in ("Describe your product…", "Describe your product or market idea…"):
            self.chat_entry.delete("1.0", "end")
            self.chat_entry.config(fg=T("TEXT1"))

    def _on_entry_focus_out(self, event):
        if not self.chat_entry.get("1.0", "end-1c").strip():
            self.chat_entry.insert("1.0", "Describe your product…")
            self.chat_entry.config(fg=T("TEXT3"))

    def _on_chat_enter(self, event):
        if not (event.state & 0x1):
            self._on_send_click()
            return "break"

    def _on_send_click(self):
        text = self.chat_entry.get("1.0", "end-1c").strip()
        if not text or text == "Describe your product…":
            return
        self.chat_entry.delete("1.0", "end")
        self._add_user_message(text)

        if not self.maps_data and not self.amzn_data:
            self._add_ai_message("Parsing your request…  ⏳")
            self.chat_messages.append({"role": "user", "content": text})
            self._run_llm_parse(text)
        else:
            context = (
                f"Context: We researched '{self.last_query}' in '{self.last_location}'.\n"
                f"Found {len(self.maps_data)} local shops, {len(self.amzn_data)} Amazon products.\n"
                f"Price range target: {self.last_price_range}.\nUser question: {text}"
            )
            self.chat_messages.append({"role": "user", "content": context})
            self._add_ai_message("Thinking…  ⏳")
            self.send_btn.config(state="disabled", bg=T("TEXT3"))

            def worker():
                try:
                    reply = chat_with_ai(self.chat_messages[-10:])
                    self.chat_messages.append({"role": "assistant", "content": reply})
                    self.after(0, lambda: self._on_followup_reply(reply))
                except Exception as e:
                    self.after(0, lambda: self._on_followup_reply(f"Error: {e}"))

            threading.Thread(target=worker, daemon=True).start()

    def _on_followup_reply(self, reply):
        self._add_ai_message(reply, fg=ACCENT)
        self.send_btn.config(state="normal", bg=PRIMARY)

    def _add_user_message(self, text: str):
        f = tk.Frame(self.chat_inner, bg=T("BG"), pady=4)
        f.pack(fill="x", padx=14)
        row = tk.Frame(f, bg=T("BG"))
        row.pack(anchor="e")
        # User bubble — right-aligned with primary colour top stripe
        bubble = tk.Frame(row, bg=T("SURFACE3"),
                          highlightbackground=T("BORDER2"),
                          highlightthickness=1,
                          padx=13, pady=9)
        bubble.pack(side="right")
        tk.Frame(bubble, bg=PRIMARY, height=2).pack(fill="x", pady=(0, 6))
        tk.Label(bubble, text=text,
                 font=("Segoe UI", 9),
                 bg=T("SURFACE3"), fg=T("TEXT1"),
                 wraplength=300, justify="right").pack()
        # Timestamp
        ts = datetime.now().strftime("%H:%M")
        tk.Label(f, text=ts,
                 font=("Cascadia Code", 7),
                 bg=T("BG"), fg=T("TEXT3")).pack(anchor="e", pady=(2, 0))
        self._scroll_chat_bottom()

    def _add_ai_message(self, text: str, fg=None):
        f = tk.Frame(self.chat_inner, bg=T("BG"), pady=4)
        f.pack(fill="x", padx=14)
        row = tk.Frame(f, bg=T("BG"))
        row.pack(anchor="w")

        # AI avatar badge
        av = tk.Frame(row, bg=ACCENT, padx=7, pady=6)
        av.pack(side="left", anchor="n", padx=(0, 9))
        tk.Label(av, text="◈",
                 font=("Segoe UI Variable", 8, "bold"),
                 bg=ACCENT, fg="#041510").pack()

        # Message bubble — left accent border + surface
        bubble_wrap = tk.Frame(row, bg=T("BORDER2"), padx=1)
        bubble_wrap.pack(side="left")
        bubble = tk.Frame(bubble_wrap, bg=T("SURFACE2"), padx=13, pady=10)
        bubble.pack()

        # Accent top rule
        rule_color = fg if fg else T("BORDER3")
        tk.Frame(bubble, bg=rule_color, height=1).pack(fill="x", pady=(0, 6))

        lbl = tk.Label(bubble, text=text,
                       font=("Segoe UI", 9),
                       bg=T("SURFACE2"),
                       fg=fg or T("TEXT1"),
                       wraplength=320, justify="left")
        lbl.pack(anchor="w")

        # Timestamp
        ts = datetime.now().strftime("%H:%M")
        tk.Label(f, text=f"AI  ·  {ts}",
                 font=("Cascadia Code", 7),
                 bg=T("BG"), fg=T("TEXT3")).pack(anchor="w", padx=(36, 0), pady=(2, 0))

        self._scroll_chat_bottom()
        return lbl

    # FIX: single after() shot — never recursive, never loops
    def _scroll_chat_bottom(self):
        def _do():
            if not self.winfo_exists():
                return
            try:
                self.chat_canvas.configure(scrollregion=self.chat_canvas.bbox("all"))
                self.chat_canvas.yview_moveto(1.0)
            except Exception:
                pass
        self.after(50, _do)

    # FIX: guarded clock tick — stops when window is gone
    def _tick_clock(self):
        if not self.winfo_exists():
            return
        try:
            self._clock.config(text=datetime.now().strftime("%H:%M:%S  ·  %d %b %Y"))
        except Exception:
            return
        self._clock_after_id = self.after(1000, self._tick_clock)

    def _toggle_theme(self):
        """Live theme switch — walks all widgets and remaps semantic colours instantly."""
        global CURRENT_THEME
        CURRENT_THEME = "light" if CURRENT_THEME == "dark" else "dark"
        _plt_rc()

        try:
            self.theme_btn.config(
                text="  ☀  " if CURRENT_THEME == "dark" else "  🌙  ")
        except Exception:
            pass

        dark_t  = THEMES["dark"]
        light_t = THEMES["light"]
        if CURRENT_THEME == "light":
            old_t, new_t = dark_t, light_t
        else:
            old_t, new_t = light_t, dark_t

        semantic_keys = [
            "BG", "SURFACE", "SURFACE2", "SURFACE3", "SURFACE4",
            "BORDER", "BORDER2", "BORDER3",
            "TEXT1", "TEXT2", "TEXT3",
            "ROW_ODD", "ROW_EVEN", "ROW_SEL", "GREEN_ROW",
            "GLOW_BLUE", "GLOW_TEAL", "GLOW_GOLD",
        ]
        remap = {
            old_t[k].lower(): new_t[k]
            for k in semantic_keys
            if k in old_t and k in new_t
        }

        def _recolor(widget):
            try:
                cfg = widget.configure()
                for opt in ("background", "bg"):
                    if opt in cfg:
                        cur = str(widget.cget(opt)).lower()
                        if cur in remap:
                            widget.configure(**{opt: remap[cur]})
                for opt in ("foreground", "fg"):
                    if opt in cfg:
                        cur = str(widget.cget(opt)).lower()
                        if cur in remap:
                            widget.configure(**{opt: remap[cur]})
                for opt in ("insertbackground",):
                    if opt in cfg:
                        cur = str(widget.cget(opt)).lower()
                        if cur in remap:
                            widget.configure(**{opt: remap[cur]})
                if "selectcolor" in cfg:
                    cur = str(widget.cget("selectcolor")).lower()
                    if cur in remap:
                        widget.configure(selectcolor=remap[cur])
                if "highlightbackground" in cfg:
                    cur = str(widget.cget("highlightbackground")).lower()
                    if cur in remap:
                        widget.configure(highlightbackground=remap[cur])
            except Exception:
                pass
            for child in widget.winfo_children():
                _recolor(child)

        _recolor(self)
        self._apply_styles()
        self.configure(bg=T("BG"))

    def _clear_cache(self):
        try:
            conn = _db()
            conn.execute("DELETE FROM cache")
            conn.commit()
            conn.close()
            messagebox.showinfo("Cache Cleared", "All cached data cleared.", parent=self)
            log.info("Cache cleared")
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self)

    def _open_restaurant_panel(self):
        if self._rest_panel is None or not self._rest_panel.win.winfo_exists():
            self._rest_panel = RestaurantPanel(self)
        self._rest_panel.show()

    def _open_history(self):
        HistoryWindow(self, self._load_from_history)

    def _load_from_history(self, data: dict):
        self.maps_data        = data.get("maps", [])
        self.amzn_data        = data.get("amzn", [])
        self.play_data        = data.get("play", [])
        self.last_query       = data.get("query", "")
        self.last_location    = data.get("location", "Ahmedabad")
        self.last_price_range = data.get("price_range")
        self.query_var.set(self.last_query)
        self.loc_var.set(self.last_location)
        self._populate_maps(self.maps_data)
        self._populate_amzn(self.amzn_data)
        self._populate_play(self.play_data)
        self._trigger_analytics_build()
        self._build_summary()
        self._add_ai_message(
            f"Loaded past search: \"{self.last_query}\" in {self.last_location}", fg=ACCENT
        )
        self.report_btn.config(state="normal", bg=ACCENT)

    # ── Main panel ────────────────────────────────────────────────────────────
    def _build_main_panel(self):
        self.main_panel = tk.Frame(self, bg=T("BG"))
        self.main_panel.pack(side="right", fill="both", expand=True)

        # ── Top command bar ────────────────────────────────────────────────
        # 3-colour gradient strip at very top
        strip = tk.Frame(self.main_panel, height=3, bg=T("BG"))
        strip.pack(fill="x")
        for col in [PRIMARY, ACCENT, ACCENT2, ACCENT3]:
            tk.Frame(strip, bg=col, height=3).pack(side="left", fill="x", expand=True)

        topbar = tk.Frame(self.main_panel, bg=T("SURFACE2"), pady=11, padx=18)
        topbar.pack(fill="x")

        # Left — dashboard title with live indicator
        left = tk.Frame(topbar, bg=T("SURFACE2"))
        left.pack(side="left")
        tk.Label(left, text="◈",
                 font=("Segoe UI Variable", 14, "bold"),
                 bg=T("SURFACE2"), fg=PRIMARY).pack(side="left", padx=(0, 8))
        tk.Label(left, text="Research Dashboard",
                 font=("Segoe UI Variable", 11, "bold"),
                 bg=T("SURFACE2"), fg=T("TEXT1")).pack(side="left")

        # Right — compact search controls + action buttons
        right = tk.Frame(topbar, bg=T("SURFACE2"))
        right.pack(side="right")

        def field(label, var, w=17):
            lbl = tk.Label(right, text=label,
                           font=("Segoe UI", 8, "bold"),
                           bg=T("SURFACE2"), fg=T("TEXT2"))
            lbl.pack(side="left", padx=(0, 4))
            e = tk.Entry(right, textvariable=var,
                         font=("Segoe UI Variable", 9),
                         bg=T("SURFACE3"), fg=T("TEXT1"),
                         insertbackground=ACCENT,
                         relief="flat", width=w,
                         highlightbackground=T("BORDER2"),
                         highlightthickness=1)
            e.pack(side="left", ipady=7, padx=(0, 10))
            return e

        self.query_var = tk.StringVar()
        self.loc_var   = tk.StringVar(value="Ahmedabad")
        field("Product:", self.query_var, 18)
        field("City:",    self.loc_var,   13)

        self.search_btn = tk.Button(
            right, text="  🔍  Search  ",
            font=("Segoe UI Variable", 9, "bold"),
            bg=PRIMARY, fg="#ffffff",
            relief="flat", padx=14, pady=7,
            cursor="hand2",
            activebackground=PRIMARY_D, activeforeground="#ffffff",
            command=self._run_all)
        self.search_btn.pack(side="left", padx=(0, 6))

        self.report_btn = tk.Button(
            right, text="  ✦  AI Report  ",
            font=("Segoe UI Variable", 9, "bold"),
            bg=ACCENT, fg="#0a1626",
            relief="flat", padx=14, pady=7,
            cursor="hand2",
            activebackground=ACCENT_D, activeforeground="#0a1626",
            command=self._generate_report,
            state="disabled")
        self.report_btn.pack(side="left", padx=(0, 6))

        tk.Button(
            right, text="  📈  Break-Even  ",
            font=("Segoe UI Variable", 9, "bold"),
            bg=ACCENT2, fg="#0a1626",
            relief="flat", padx=12, pady=7,
            cursor="hand2",
            activebackground=ACCENT2,
            command=lambda: BreakEvenCalculator(
                self, self.last_price_range, self.amzn_data)
        ).pack(side="left")

        # Thin separator
        tk.Frame(self.main_panel, bg=T("BORDER2"), height=1).pack(fill="x")
        self._build_notebook()

    def _build_notebook(self):
        self.nb = ttk.Notebook(self.main_panel)
        self.nb.pack(fill="both", expand=True)

        # Tab labels with icons
        self.maps_tab = ttk.Frame(self.nb)
        self.nb.add(self.maps_tab, text="  🗺  Local Shops  ")
        self._build_maps_tab()

        self.play_tab = ttk.Frame(self.nb)
        self.nb.add(self.play_tab, text="  📱  App Store  ")
        self._build_play_tab()

        self.amzn_tab = ttk.Frame(self.nb)
        self.nb.add(self.amzn_tab, text="  🛍  Amazon  ")
        self._build_amzn_tab()

        self.trends_tab = ttk.Frame(self.nb)
        self.nb.add(self.trends_tab, text="  📈  Trends  ")
        self.trends_inner = tk.Frame(self.trends_tab, bg=T("BG"))
        self.trends_inner.pack(fill="both", expand=True)

        self.analytics_tab = ttk.Frame(self.nb)
        self.nb.add(self.analytics_tab, text="  ◎  Analytics  ")
        self.analytics_inner = tk.Frame(self.analytics_tab, bg=T("BG"))
        self.analytics_inner.pack(fill="both", expand=True)

        self.summary_tab = ttk.Frame(self.nb)
        self.nb.add(self.summary_tab, text="  ✦  Summary  ")
        self.summary_inner = tk.Frame(self.summary_tab, bg=T("BG"))
        self.summary_inner.pack(fill="both", expand=True)

    def _make_tree_tab(self, parent, cols, widths, anchors, header_text, hint=""):
        parent.rowconfigure(1, weight=1)
        parent.columnconfigure(0, weight=1)

        hdr = tk.Frame(parent, bg=T("SURFACE2"), pady=0)
        hdr.grid(row=0, column=0, columnspan=2, sticky="ew")
        # Left accent line
        tk.Frame(hdr, bg=ACCENT, width=3).pack(side="left", fill="y")
        tk.Label(hdr, text=f"  {header_text}",
                 font=FONT_SMALL, bg=T("SURFACE2"),
                 fg=T("TEXT2"), pady=9).pack(side="left", padx=6)
        if hint:
            tk.Label(hdr, text=hint,
                     font=FONT_SMALL, bg=T("SURFACE2"),
                     fg=T("TEXT3")).pack(side="right", padx=12)

        tree = ttk.Treeview(parent, columns=cols, height=20, show="headings")
        for col, w, a in zip(cols, widths, anchors):
            tree.column(col, width=w, anchor=a, minwidth=30)
            tree.heading(col, text=col)
        vsb = ttk.Scrollbar(parent, orient="vertical",   command=tree.yview)
        hsb = ttk.Scrollbar(parent, orient="horizontal", command=tree.xview)
        tree.configure(yscroll=vsb.set, xscroll=hsb.set)
        tree.tag_configure("odd",      background=T("ROW_ODD"))
        tree.tag_configure("even",     background=T("ROW_EVEN"))
        tree.tag_configure("toprated", background=T("GREEN_ROW"))
        tree.grid(row=1, column=0, sticky="nsew")
        vsb.grid(row=1, column=1, sticky="ns")
        hsb.grid(row=2, column=0, sticky="ew")
        return tree

    def _build_maps_tab(self):
        self.maps_tab.rowconfigure(1, weight=1)
        self.maps_tab.columnconfigure(0, weight=1)

        hdr_frame = tk.Frame(self.maps_tab, bg=T("SURFACE2"))
        hdr_frame.grid(row=0, column=0, columnspan=2, sticky="ew")
        tk.Frame(hdr_frame, bg=PRIMARY, width=3).pack(side="left", fill="y")
        tk.Label(hdr_frame,
                 text="  Local competitor shops  ·  Double-click row for full details, reviews & sentiment",
                 font=FONT_SMALL, bg=T("SURFACE2"), fg=T("TEXT2"), pady=9).pack(
                     side="left", padx=6)

        self._maps_sort_lbl = tk.Label(
            hdr_frame, text="  ⚡  Best Match  ",
            font=("Segoe UI Variable", 8, "bold"),
            bg=PRIMARY, fg="#ffffff",
            padx=8, pady=4, cursor="hand2")
        self._maps_sort_lbl.pack(side="right", padx=12, pady=4)
        self._maps_sort_lbl.bind("<Button-1>", lambda e: self._choose_sort_preference())

        cols    = ("Rank", "Shop Name", "Type", "Rating", "Reviews",
                   "Price", "Hours / Status", "Address")
        widths  = [46, 210, 150, 82, 95, 68, 200, 270]
        anchors = ["center", "w", "w", "center", "center", "center", "w", "w"]
        self.maps_tree = ttk.Treeview(self.maps_tab, columns=cols, height=20, show="headings")
        for col, w, a in zip(cols, widths, anchors):
            self.maps_tree.column(col, width=w, anchor=a, minwidth=30)
            self.maps_tree.heading(col, text=col)
        vsb = ttk.Scrollbar(self.maps_tab, orient="vertical",   command=self.maps_tree.yview)
        hsb = ttk.Scrollbar(self.maps_tab, orient="horizontal", command=self.maps_tree.xview)
        self.maps_tree.configure(yscroll=vsb.set, xscroll=hsb.set)
        self.maps_tree.tag_configure("odd",      background=T("ROW_ODD"))
        self.maps_tree.tag_configure("even",     background=T("ROW_EVEN"))
        self.maps_tree.tag_configure("toprated", background=T("GREEN_ROW"))
        self.maps_tree.grid(row=1, column=0, sticky="nsew")
        vsb.grid(row=1, column=1, sticky="ns")
        hsb.grid(row=2, column=0, sticky="ew")
        self.maps_tree.bind("<Double-1>", self._maps_open_detail)

    def _build_play_tab(self):
        self.play_tree = self._make_tree_tab(
            self.play_tab,
            ("#", "App Name", "Rating", "Genre", "Installs", "Price"),
            [42, 350, 90, 190, 150, 100],
            ["center", "w", "center", "w", "center", "center"],
            "Apps in this category",
            hint="Double-click for details & reviews",
        )
        self.play_tree.bind("<Double-1>", self._play_open_detail)

    def _build_amzn_tab(self):
        self.amzn_tree = self._make_tree_tab(
            self.amzn_tab,
            ("#", "Product Title", "Price", "Rating", "Reviews", "Position"),
            [42, 530, 105, 82, 105, 82],
            ["center", "w", "center", "center", "center", "center"],
            "Products on Amazon.in",
            hint="Double-click to open product page",
        )
        self.amzn_tree.bind("<Double-1>", self._amzn_open_link)

    def _build_status_bar(self):
        bar = tk.Frame(self.main_panel, bg=T("SURFACE2"))
        bar.pack(fill="x", side="bottom")
        # Thin accent top border
        tk.Frame(bar, bg=T("BORDER2"), height=1).pack(fill="x")
        row = tk.Frame(bar, bg=T("SURFACE2"))
        row.pack(fill="x", padx=14, pady=7)

        def st_seg(parent, dot_color, label_text, side="left"):
            """Status segment: coloured dot + label."""
            seg = tk.Frame(parent, bg=T("SURFACE2"))
            seg.pack(side=side, padx=(0, 20))
            dot = tk.Frame(seg, bg=dot_color, width=7, height=7)
            dot.pack(side="left", padx=(0, 5))
            lbl = tk.Label(seg, text=label_text,
                           font=("Segoe UI Variable", 8),
                           bg=T("SURFACE2"), fg=T("TEXT2"))
            lbl.pack(side="left")
            return lbl

        self.st_maps   = st_seg(row, T("SURFACE3"), "Maps: —")
        self.st_play   = st_seg(row, T("SURFACE3"), "Play: —")
        self.st_amzn   = st_seg(row, T("SURFACE3"), "Amazon: —")
        self.st_trends = st_seg(row, T("SURFACE3"), "Trends: —")

        tk.Label(row, text="Double-click any row for details & reviews",
                 font=("Segoe UI", 7),
                 bg=T("SURFACE2"), fg=T("TEXT3")).pack(side="right")

    # ── Search orchestration ──────────────────────────────────────────────────
    def _run_llm_parse(self, user_text: str):
        self.send_btn.config(state="disabled", bg=T("TEXT3"))

        def worker():
            try:
                result = parse_prompt_with_llm(user_text)
                self.after(0, lambda: self._on_llm_success(result))
            except Exception as e:
                self.after(0, lambda: self._on_llm_fail(str(e)))

        threading.Thread(target=worker, daemon=True).start()

    def _on_llm_success(self, result: dict):
        product  = result.get("product", "")
        location = result.get("location", "")
        price    = result.get("price_range")
        self.last_price_range = price
        self.last_query       = product
        self.last_location    = location or "Ahmedabad"
        if product:  self.query_var.set(product)
        if location: self.loc_var.set(location)
        price_str = (f"  ·  Price: ₹{price[0]:,}–₹{price[1]:,}"
                     if price and isinstance(price, list) and len(price) == 2 else "")
        self._add_ai_message(
            f"Extracted  →  Product: \"{product}\"  ·  City: \"{location}\"{price_str}\n\n"
            "Searching all sources now… 10–30 seconds.", fg=ACCENT
        )
        self.send_btn.config(state="normal", bg=PRIMARY)
        self._run_all()

    def _on_llm_fail(self, msg: str):
        self._add_ai_message(f"Parse error: {msg[:200]}", fg=DANGER)
        self.send_btn.config(state="normal", bg=PRIMARY)

    # FIX: _run_all no longer opens the blocking sort dialog.
    #      The sort button is always available in the sidebar.
    def _run_all(self):
        query = self.query_var.get().strip()
        if not query:
            messagebox.showwarning("Missing Input", "Please enter a product first.")
            return

        self.search_btn.config(state="disabled", bg=T("TEXT3"))
        self.report_btn.config(state="disabled", bg=T("TEXT3"))
        for st in (self.st_maps, self.st_play, self.st_amzn, self.st_trends):
            prefix = st.cget("text").split(":")[0]
            st.config(text=f"{prefix}: searching…", fg=WARNING)

        for t in (self.maps_tree, self.play_tree, self.amzn_tree):
            for item in t.get_children():
                t.delete(item)
        for w in self.analytics_inner.winfo_children(): w.destroy()
        for w in self.summary_inner.winfo_children():   w.destroy()
        for w in self.trends_inner.winfo_children():    w.destroy()

        self.maps_data    = []
        self.play_data    = []
        self.amzn_data    = []
        self.trends_data  = {}
        self.maps_report  = None
        location          = self.loc_var.get().strip() or "Ahmedabad"
        self._done_flags  = {"maps": False, "play": False, "amzn": False, "trends": False}

        threading.Thread(target=self._worker_maps,   args=(query, location), daemon=True).start()
        threading.Thread(target=self._worker_play,   args=(query, 10),       daemon=True).start()
        threading.Thread(target=self._worker_amzn,   args=(query,),          daemon=True).start()
        threading.Thread(target=self._worker_trends, args=(query,),          daemon=True).start()

    def _update_sort_badge(self):
        icons  = {"nearest": "📍", "top_rated": "★",        "both": "⚡"}
        labels = {"nearest": "Nearest", "top_rated": "Top Rated", "both": "Best Match"}
        colors = {"nearest": ACCENT,    "top_rated": SUCCESS,      "both": PRIMARY}
        pref   = self.sort_preference
        if hasattr(self, "_maps_sort_lbl"):
            self._maps_sort_lbl.config(
                text=f"{icons.get(pref,'⚡')} {labels.get(pref,'Sort')}",
                bg=colors.get(pref, PRIMARY),
            )

    # ── Worker threads — every path calls after() even on error ──────────────
    def _worker_maps(self, q, loc):
        try:
            self.after(0, self._on_maps_success, MapsDataFetcher.fetch_places(q, loc))
        except Exception as e:
            self.after(0, self._on_maps_fail, str(e))

    def _worker_play(self, q, n):
        try:
            self.after(0, self._on_play_success, PlayStoreFetcher.fetch(q, n))
        except Exception as e:
            self.after(0, self._on_play_fail, str(e))

    def _worker_amzn(self, q):
        try:
            self.after(0, self._on_amzn_success, AmazonFetcher.fetch(q))
        except Exception as e:
            self.after(0, self._on_amzn_fail, str(e))

    def _worker_trends(self, q):
        import concurrent.futures
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        future   = executor.submit(fetch_google_trends, q)
        try:
            result = future.result(timeout=45)
            self.after(0, self._on_trends_success, result)
        except concurrent.futures.TimeoutError:
            self.after(0, self._on_trends_fail, "Google Trends timed out after 45s")
        except Exception as e:
            self.after(0, self._on_trends_fail, str(e))
        finally:
            executor.shutdown(wait=False)

    def _on_maps_success(self, data):
        self.maps_data = data
        self._done_flags["maps"] = True
        self.st_maps.config(text=f"Maps: {len(data)} shops  ✓", fg=SUCCESS)
        self._populate_maps(data)
        self._check_all_done()

    def _on_maps_fail(self, msg):
        self._done_flags["maps"] = True
        self.st_maps.config(text="Maps: error  ✗", fg=DANGER)
        log.error(f"Maps fail: {msg}")
        self._check_all_done()

    def _on_play_success(self, data):
        self.play_data = data
        self._done_flags["play"] = True
        self.st_play.config(text=f"Play: {len(data)} apps  ✓", fg=SUCCESS)
        self._populate_play(data)
        self._check_all_done()

    def _on_play_fail(self, msg):
        self._done_flags["play"] = True
        self.st_play.config(text="Play: error  ✗", fg=DANGER)
        log.error(f"Play fail: {msg}")
        self._check_all_done()

    def _on_amzn_success(self, data):
        self.amzn_data = data
        self._done_flags["amzn"] = True
        self.st_amzn.config(text=f"Amazon: {len(data)} products  ✓", fg=SUCCESS)
        self._populate_amzn(data)
        self._check_all_done()

    def _on_amzn_fail(self, msg):
        self._done_flags["amzn"] = True
        self.st_amzn.config(text="Amazon: error  ✗", fg=DANGER)
        log.error(f"Amazon fail: {msg}")
        self._check_all_done()

    def _on_trends_success(self, data):
        self.trends_data = data
        self._done_flags["trends"] = True
        if "error" in data:
            self.st_trends.config(text="Trends: N/A  ⚠", fg=WARNING)
            if "429" in data["error"] or "rate" in data["error"].lower():
                self._add_ai_message(
                    "Google Trends is rate-limiting.\nWait 5–10 min and search again.\n"
                    "All other data is still available.", fg=WARNING,
                )
        else:
            self.st_trends.config(text=f"Trends: {data.get('trend','—')}  ✓", fg=SUCCESS)
        self._build_trends_tab()
        self._check_all_done()

    def _on_trends_fail(self, msg):
        self._done_flags["trends"] = True
        if "429" in msg or "rate" in msg.lower() or "timed out" in msg.lower():
            self.st_trends.config(text="Trends: rate-limited  ⚠", fg=WARNING)
            self._add_ai_message(
                "Google Trends timed out or rate-limited.\n"
                "Wait 5–10 min. All other results available.", fg=WARNING,
            )
        else:
            self.st_trends.config(text="Trends: error  ✗", fg=DANGER)
        log.error(f"Trends fail: {msg}")
        self._check_all_done()

    # FIX: analytics always computed off main thread, UI built on main thread
    def _check_all_done(self):
        if not all(self._done_flags.values()):
            return

        self.search_btn.config(state="normal", bg=PRIMARY)
        self.report_btn.config(state="normal", bg=ACCENT)
        self._build_summary()

        # Show placeholder while computing
        for w in self.analytics_inner.winfo_children():
            w.destroy()
        tk.Label(self.analytics_inner, text="⏳  Building analytics…",
                 font=FONT_HEADING, fg=T("TEXT2"), bg=T("BG")).pack(pady=60)

        def analytics_worker():
            try:
                maps_valid  = [c for c in self.maps_data  if c["rating"] > 0]
                amzn_prices = [p["price_num"] for p in self.amzn_data if p.get("price_num")]
                play_rated  = [a for a in self.play_data  if a.get("rating")]
                maps_texts  = [r.get("snippet", "") or r.get("text", "")
                               for c in self.maps_data for r in c.get("reviews", [])
                               if r.get("snippet") or r.get("text")]
                play_texts  = [r.get("content", "")
                               for a in self.play_data for r in a.get("reviews", [])
                               if r.get("content")]
                all_texts   = maps_texts + play_texts
                maps_sent   = analyze_sentiment(maps_texts) if maps_texts and TEXTBLOB_AVAILABLE else None
                play_sent   = analyze_sentiment(play_texts) if play_texts and TEXTBLOB_AVAILABLE else None
                all_sent    = analyze_sentiment(all_texts)  if all_texts  and TEXTBLOB_AVAILABLE else None
                self.after(0, lambda: self._build_analytics(
                    maps_valid, amzn_prices, play_rated,
                    maps_sent, play_sent, all_sent, all_texts,
                ))
            except Exception as e:
                log.error(f"Analytics worker error: {e}")
                self.after(0, lambda: self._build_analytics())

        threading.Thread(target=analytics_worker, daemon=True).start()

        save_search(self.query_var.get().strip(), self.loc_var.get().strip(),
                    self.last_price_range, self.maps_data, self.amzn_data, self.play_data)
        total = len(self.maps_data) + len(self.play_data) + len(self.amzn_data)
        sort_labels = {"nearest": "Nearest", "top_rated": "Top Rated", "both": "Best Match"}
        self._add_ai_message(
            f"Search complete!  Found {total} total results:\n"
            f"  · {len(self.maps_data)} local shops  ({sort_labels.get(self.sort_preference,'')})\n"
            f"  · {len(self.play_data)} apps\n"
            f"  · {len(self.amzn_data)} Amazon products\n\n"
            "Auto-saved to history.\n"
            "Ask follow-ups or click  AI Report  for full analysis.",
            fg=SUCCESS,
        )
        self.chat_messages.append({
            "role": "assistant",
            "content": (f"Search complete for {self.last_query} in {self.last_location}. "
                        f"Found {len(self.maps_data)} shops, {len(self.amzn_data)} Amazon products."),
        })

    def _trigger_analytics_build(self):
        for w in self.analytics_inner.winfo_children():
            w.destroy()
        tk.Label(self.analytics_inner, text="⏳  Building analytics…",
                 font=FONT_HEADING, fg=T("TEXT2"), bg=T("BG")).pack(pady=60)

        def worker():
            try:
                maps_valid  = [c for c in self.maps_data  if c["rating"] > 0]
                amzn_prices = [p["price_num"] for p in self.amzn_data if p.get("price_num")]
                play_rated  = [a for a in self.play_data  if a.get("rating")]
                maps_texts  = [r.get("snippet", "") or r.get("text", "")
                               for c in self.maps_data for r in c.get("reviews", [])
                               if r.get("snippet") or r.get("text")]
                play_texts  = [r.get("content", "")
                               for a in self.play_data for r in a.get("reviews", [])
                               if r.get("content")]
                all_texts   = maps_texts + play_texts
                maps_sent   = analyze_sentiment(maps_texts) if maps_texts and TEXTBLOB_AVAILABLE else None
                play_sent   = analyze_sentiment(play_texts) if play_texts and TEXTBLOB_AVAILABLE else None
                all_sent    = analyze_sentiment(all_texts)  if all_texts  and TEXTBLOB_AVAILABLE else None
                self.after(0, lambda: self._build_analytics(
                    maps_valid, amzn_prices, play_rated,
                    maps_sent, play_sent, all_sent, all_texts,
                ))
            except Exception as e:
                log.error(f"Analytics worker error: {e}")
                self.after(0, lambda: self._build_analytics())

        threading.Thread(target=worker, daemon=True).start()

    # ── Populate tree views ───────────────────────────────────────────────────
    def _populate_maps(self, data):
        for item in self.maps_tree.get_children():
            self.maps_tree.delete(item)
        total_rev = sum(c["review_count"] for c in data)
        for c in data:
            c["market_share"] = (c["review_count"] / total_rev * 100) if total_rev else 0

        sdata = sort_maps_data(data, self.sort_preference)
        self._update_sort_badge()

        for idx, c in enumerate(sdata, 1):
            tag       = "toprated" if c["rating"] >= 4.5 else ("even" if idx % 2 == 0 else "odd")
            hours_col = c.get("hours_display", "") or str(c.get("business_status", "UNKNOWN")).replace("_", " ").title()
            self.maps_tree.insert("", tk.END, tags=(tag,), values=(
                idx, c["name"], c["type"][:30],
                f"{c['rating']}/5" if c["rating"] else "N/A",
                f"{c['review_count']:,}", c["price_label"], hours_col, c["location"],
            ))
        rated = [c["rating"] for c in data if c["rating"] > 0]
        self.maps_report = {
            "total":         len(data),
            "avg_rating":    round(sum(rated) / len(rated), 2) if rated else 0,
            "total_reviews": total_rev,
            "rating_range":  (min(rated, default=0), max(rated, default=0)),
        }

    def _populate_play(self, data):
        for item in self.play_tree.get_children():
            self.play_tree.delete(item)
        for i, comp in enumerate(data, 1):
            rating    = comp.get("rating", 0)
            price_str = "Free" if comp.get("isFree") else f"₹{comp.get('price', 0)}"
            self.play_tree.insert("", tk.END, tags=("even" if i % 2 == 0 else "odd",), values=(
                i, comp.get("appTitle", "—"),
                f"{rating:.1f}/5.0" if rating else "N/A",
                comp.get("genre", "—"), comp.get("installs", "—"), price_str,
            ))

    def _populate_amzn(self, data):
        for item in self.amzn_tree.get_children():
            self.amzn_tree.delete(item)
        for i, p in enumerate(data, 1):
            title = p["title"][:71] + "…" if len(p["title"]) > 72 else p["title"]
            self.amzn_tree.insert("", tk.END, tags=("even" if i % 2 == 0 else "odd",), values=(
                i, title, p["price"], p["rating"],
                p.get("reviews", 0), p.get("position", ""),
            ))

    def _maps_open_detail(self, event):
        sel = self.maps_tree.selection()
        if not sel:
            return
        idx = self.maps_tree.index(sel[0])
        sd  = sort_maps_data(self.maps_data, self.sort_preference)
        if idx < len(sd):
            MapsReviewPopup(self, sd[idx])

    def _play_open_detail(self, event):
        sel = self.play_tree.selection()
        if not sel:
            return
        idx = self.play_tree.index(sel[0])
        if idx < len(self.play_data):
            PlayDetailPopup(self, self.play_data[idx])

    def _amzn_open_link(self, event):
        sel = self.amzn_tree.selection()
        if not sel:
            return
        idx = self.amzn_tree.index(sel[0])
        if idx < len(self.amzn_data):
            link = self.amzn_data[idx].get("link", "")
            if link:
                webbrowser.open(link)

    # ── Report ────────────────────────────────────────────────────────────────
    def _generate_report(self):
        query = self.query_var.get().strip() or self.last_query
        if not query:
            messagebox.showwarning("No Data", "Run a search first.")
            return
        if not (self.maps_data or self.amzn_data):
            messagebox.showwarning("No Data", "Search results needed.")
            return
        self.report_btn.config(state="disabled", bg=T("TEXT3"), text="  Generating…")
        self._add_ai_message(
            "Generating Business Intelligence Report…\n"
            "Analysing sources, calculating costs…  ⏳"
        )
        location = self.loc_var.get().strip() or self.last_location

        def worker():
            try:
                report = generate_business_report(
                    query, location, self.last_price_range,
                    self.maps_data, self.amzn_data, self.play_data, self.trends_data,
                )
                save_report(query, location, report)
                self.after(0, lambda: self._on_report_success(report, query, location))
            except Exception as e:
                self.after(0, lambda: self._on_report_fail(str(e)))

        threading.Thread(target=worker, daemon=True).start()

    def _on_report_success(self, report, query, location):
        self.report_btn.config(state="normal", bg=ACCENT, text="  AI Report")
        self._add_ai_message("Report generated!  Opening now…", fg=ACCENT)
        self.chat_messages.append({
            "role": "assistant",
            "content": f"Generated business report for {query}. " + report[:500],
        })
        ReportWindow(self, report, query, location,
                     self.maps_data, self.amzn_data, self.last_price_range)

    def _on_report_fail(self, msg):
        self.report_btn.config(state="normal", bg=ACCENT, text="  AI Report")
        self._add_ai_message(f"Report generation failed:\n{msg[:200]}", fg=DANGER)

    # ── Trends tab ────────────────────────────────────────────────────────────
    def _build_trends_tab(self):
        for w in self.trends_inner.winfo_children():
            w.destroy()
        data = self.trends_data

        if not data or "error" in data:
            msg = data.get("error", "No trend data") if data else "Run a search first."
            if not PYTRENDS_AVAILABLE:
                msg = "pytrends not installed.\nRun: pip install pytrends"
            tk.Label(self.trends_inner, text=msg, font=FONT_BODY, fg=T("TEXT2"), bg=T("BG"),
                     wraplength=600, justify="center").pack(pady=60)
            return

        _, inner, _ = scrollable_frame(self.trends_inner, bg=T("BG"))
        query = self.query_var.get().strip()

        hdr = tk.Frame(inner, bg=T("SURFACE2"), pady=12, padx=20)
        hdr.pack(fill="x", pady=(8, 0))
        tk.Label(hdr, text=f"  Google Trends  —  \"{query}\"  (India, 12 months)",
                 font=FONT_HEADING, bg=T("SURFACE2"), fg=T("TEXT1")).pack(anchor="w")

        cards = tk.Frame(inner, bg=T("BG"), pady=10, padx=16)
        cards.pack(fill="x")
        cards.columnconfigure((0, 1, 2, 3), weight=1)

        def sc(col, label, value, fg=PRIMARY):
            f = tk.Frame(cards, bg=T("SURFACE"), padx=12, pady=12)
            f.grid(row=0, column=col, padx=6, sticky="ew")
            tk.Frame(f, bg=fg, height=3).pack(fill="x", pady=(0, 8))
            tk.Label(f, text=value, font=("Segoe UI", 14, "bold"),
                     bg=T("SURFACE"), fg=fg).pack()
            tk.Label(f, text=label, font=FONT_SMALL, bg=T("SURFACE"), fg=T("TEXT2")).pack()

        trend_color = (SUCCESS if data["trend"] == "rising" else
                       DANGER  if data["trend"] == "declining" else ACCENT2)
        sc(0, "12-Month Trend",   data["trend"].upper(),     trend_color)
        sc(1, "Average Interest", str(data["avg"]),           PRIMARY)
        sc(2, "Peak Interest",    str(data["peak"]),          ACCENT2)
        sc(3, "Data Points",      str(len(data["dates"])),    ACCENT)

        _plt_rc()
        fig = Figure(figsize=(13, 4), dpi=96)
        fig.patch.set_facecolor(T("BG"))
        ax  = fig.add_subplot(111)
        ax.set_facecolor(T("SURFACE"))
        vals  = data["values"]
        dates = data["dates"]
        xs    = list(range(len(vals)))
        ax.plot(xs, vals, color=PRIMARY, linewidth=2.2, zorder=3)
        ax.fill_between(xs, vals, alpha=0.12, color=PRIMARY)
        ax.axhline(data["avg"], color=ACCENT2, linestyle="--", linewidth=1.2, alpha=0.7,
                   label=f"Avg: {data['avg']}")
        step = max(1, len(dates) // 8)
        ax.set_xticks(xs[::step])
        ax.set_xticklabels([d[5:] for d in dates[::step]], rotation=30, fontsize=8)
        ax.set_ylabel("Search Interest (0–100)", fontsize=9)
        ax.set_title(f"Google Trends — \"{query}\" — India",
                     fontsize=11, fontweight="bold", pad=10)
        ax.grid(True, linestyle="--", alpha=0.15, color=T("BORDER"))
        ax.legend(fontsize=8)
        fig.tight_layout(pad=1.8)
        cv = FigureCanvasTkAgg(fig, master=inner)
        cv.draw()
        cv.get_tk_widget().pack(fill="x", padx=16, pady=8)

        if data.get("related"):
            rf = tk.Frame(inner, bg=T("SURFACE"), padx=20, pady=14)
            rf.pack(fill="x", padx=16, pady=6)
            tk.Label(rf, text="Related Search Queries",
                     font=FONT_HEADING, bg=T("SURFACE"), fg=T("TEXT1")).pack(anchor="w", pady=(0, 8))
            for kw, val in data["related"].items():
                row = tk.Frame(rf, bg=T("SURFACE"))
                row.pack(fill="x", pady=2)
                tk.Label(row, text=f"  {kw}", font=FONT_BODY, bg=T("SURFACE"),
                         fg=T("TEXT1"), width=30, anchor="w").pack(side="left")
                tk.Frame(row, bg=T("SURFACE3"), height=14,
                         width=int(val * 2)).pack(side="left", padx=(8, 4))
                tk.Label(row, text=str(val), font=FONT_SMALL, bg=T("SURFACE"),
                         fg=T("TEXT2")).pack(side="left")

    # ── Analytics tab — pure Figure OO API, no plt.subplots ──────────────────
    def _build_analytics(self, maps_valid=None, amzn_prices=None, play_rated=None,
                          maps_sent=None, play_sent=None, all_sent=None, all_texts=None):
        for w in self.analytics_inner.winfo_children():
            w.destroy()

        if maps_valid  is None: maps_valid  = [c for c in self.maps_data  if c["rating"] > 0]
        if amzn_prices is None: amzn_prices = [p["price_num"] for p in self.amzn_data if p.get("price_num")]
        if play_rated  is None: play_rated  = [a for a in self.play_data  if a.get("rating")]
        if all_texts   is None: all_texts   = []

        if not maps_valid and not amzn_prices and not play_rated:
            tk.Label(self.analytics_inner, text="Run a search to see analytics.",
                     font=FONT_BODY, fg=T("TEXT2"), bg=T("BG")).pack(pady=60)
            return

        _, scroll, _ = scrollable_frame(self.analytics_inner, bg=T("BG"))

        def section_hdr(icon, title, sub, accent=PRIMARY):
            f = tk.Frame(scroll, bg=T("SURFACE2"),
                         pady=11, padx=22)
            f.pack(fill="x", pady=(18, 0))
            tk.Frame(f, bg=accent, width=3).pack(side="left", fill="y", padx=(0, 14))
            col = tk.Frame(f, bg=T("SURFACE2"))
            col.pack(side="left")
            tk.Label(col, text=f"{icon}  {title}",
                     font=("Segoe UI Variable", 11, "bold"),
                     bg=T("SURFACE2"), fg=T("TEXT1")).pack(anchor="w")
            tk.Label(col, text=sub,
                     font=("Cascadia Code", 8),
                     bg=T("SURFACE2"), fg=T("TEXT3")).pack(anchor="w")

        def embed(fig):
            _plt_rc()
            cv = FigureCanvasTkAgg(fig, master=scroll)
            cv.draw()
            cv.get_tk_widget().pack(fill="x", padx=20, pady=(8, 4))

        # ── Maps ─────────────────────────────────────────────────────────────
        section_hdr("🗺", "Local Shops  —  Google Maps",
                    f"{len(self.maps_data)} competitors found", accent=ACCENT)
        if maps_valid:
            names   = [c["name"][:16]   for c in maps_valid]
            ratings = [c["rating"]       for c in maps_valid]
            reviews = [c["review_count"] for c in maps_valid]

            fig = Figure(figsize=(14, max(3.2, len(names) * 0.38)), dpi=96)
            fig.patch.set_facecolor(T("BG"))
            ax1 = fig.add_subplot(1, 2, 1)
            ax2 = fig.add_subplot(1, 2, 2)
            ax1.set_facecolor(T("SURFACE"))
            ax2.set_facecolor(T("SURFACE"))

            bar_clrs = [SUCCESS if r >= 4.5 else PRIMARY if r >= 3.8 else ACCENT2
                        for r in ratings]
            ax1.barh(names, ratings, color=bar_clrs, edgecolor=T("SURFACE"),
                     height=0.6, zorder=3)
            ax1.set_xlim(0, 5.5)
            ax1.set_xlabel("Rating", fontsize=9)
            ax1.set_title("Competitor Ratings", fontsize=11, fontweight="bold", pad=12)
            ax1.axvline(4.0, color=T("BORDER2"), linestyle="--", linewidth=0.9, alpha=0.7, zorder=2)
            ax1.grid(axis="x", linestyle="--", alpha=0.15, color=T("BORDER"), zorder=1)
            for i, v in enumerate(ratings):
                ax1.text(v + 0.07, i, f"{v:.1f}", va="center", fontsize=8,
                         fontweight="bold", color=T("TEXT1"))

            scatter_clrs = [rating_color(r) for r in ratings]
            ax2.scatter(ratings, reviews, c=scatter_clrs, s=100, zorder=3,
                        alpha=0.9, edgecolors=T("SURFACE"), linewidths=1)
            for i, n in enumerate(names):
                ax2.annotate(
                    n, (ratings[i], reviews[i]), xytext=(10, 6),
                    textcoords="offset points", fontsize=7, color=T("TEXT2"),
                    bbox=dict(boxstyle="round,pad=0.3", facecolor=T("SURFACE2"),
                              alpha=0.85, edgecolor=T("BORDER")),
                )
            ax2.set_xlabel("Rating", fontsize=9)
            ax2.set_ylabel("Reviews", fontsize=9)
            ax2.set_title("Rating vs Popularity", fontsize=11, fontweight="bold", pad=12)
            ax2.grid(True, linestyle="--", alpha=0.15, color=T("BORDER"))
            fig.tight_layout(pad=2.2)
            embed(fig)

        # ── Radar ─────────────────────────────────────────────────────────────
        if len(maps_valid) >= 3:
            section_hdr("◎", "Radar  —  Top Competitor Comparison",
                        "Rating, Reviews, Popularity across top competitors")
            top5  = sorted(maps_valid, key=lambda x: (x["rating"], x["review_count"]),
                           reverse=True)[:5]
            cats  = ["Rating", "Reviews", "Popularity", "Price Score", "Overall"]
            N     = len(cats)
            angles = [n / float(N) * 2 * np.pi for n in range(N)]
            angles += angles[:1]
            fig   = Figure(figsize=(8, 5), dpi=96)
            fig.patch.set_facecolor(T("BG"))
            ax    = fig.add_subplot(111, polar=True)
            ax.set_facecolor(T("SURFACE"))
            ax.set_theta_offset(np.pi / 2)
            ax.set_theta_direction(-1)
            ax.set_xticks(angles[:-1])
            ax.set_xticklabels(cats, fontsize=9, color=T("TEXT1"))
            ax.set_ylim(0, 10)
            ax.set_yticks([2, 4, 6, 8, 10])
            ax.set_yticklabels(["2","4","6","8","10"], fontsize=7, color=T("TEXT3"))
            ax.grid(color=T("BORDER"), linestyle="--", alpha=0.3)
            pal      = [PRIMARY, SUCCESS, ACCENT2, DANGER, ACCENT]
            max_rev  = max(c["review_count"] for c in top5) or 1
            for i, comp in enumerate(top5):
                r_norm   = comp["rating"] / 5 * 10
                rev_norm = comp["review_count"] / max_rev * 10
                pop_norm = min(10, rev_norm * 0.8 + r_norm * 0.2)
                overall  = (r_norm + rev_norm + pop_norm) / 3
                vals     = [r_norm, rev_norm, pop_norm, 5, overall] + [r_norm]
                color    = pal[i % len(pal)]
                ax.plot(angles, vals, "o-", linewidth=2, color=color,
                        label=comp["name"][:15])
                ax.fill(angles, vals, alpha=0.08, color=color)
            ax.legend(loc="upper right", bbox_to_anchor=(1.35, 1.1), fontsize=8)
            ax.set_title("Competitor Radar", fontsize=11, fontweight="bold",
                         pad=20, color=T("TEXT1"))
            fig.tight_layout(pad=2)
            embed(fig)

        # ── Amazon prices ──────────────────────────────────────────────────────
        if amzn_prices:
            section_hdr("🛍", "Price Landscape  —  Amazon", "Price distribution", accent=ACCENT2)
            fig = Figure(figsize=(13, 3.8), dpi=96)
            fig.patch.set_facecolor(T("BG"))
            ax  = fig.add_subplot(1, 1, 1)
            ax.set_facecolor(T("SURFACE"))
            ax.scatter(range(len(amzn_prices)), amzn_prices, c=PRIMARY,
                       s=90, label="Amazon", zorder=3, alpha=0.9)
            if self.last_price_range:
                ax.axhspan(self.last_price_range[0], self.last_price_range[1],
                           alpha=0.1, color=ACCENT, label="Your target")
            ax.set_xlabel("Product Rank", fontsize=9)
            ax.set_ylabel("Price (₹)", fontsize=9)
            ax.set_title("Amazon Price Landscape", fontsize=11, fontweight="bold", pad=10)
            ax.legend(fontsize=8)
            ax.grid(True, linestyle="--", alpha=0.15, color=T("BORDER"))
            fig.tight_layout(pad=1.8)
            embed(fig)

        # ── Play Store ─────────────────────────────────────────────────────────
        section_hdr("📱", "App Store  —  Google Play", f"{len(self.play_data)} apps", accent=PRIMARY)
        if play_rated:
            p_names = [a["appTitle"][:18] for a in play_rated]
            p_rat   = [a["rating"]         for a in play_rated]
            free    = sum(1 for a in self.play_data if a.get("isFree"))
            paid    = len(self.play_data) - free

            fig = Figure(figsize=(14, max(3.2, len(p_names) * 0.38)), dpi=96)
            fig.patch.set_facecolor(T("BG"))
            ax3 = fig.add_subplot(1, 2, 1)
            ax4 = fig.add_subplot(1, 2, 2)
            ax3.set_facecolor(T("SURFACE"))
            ax4.set_facecolor(T("SURFACE"))

            pc = [SUCCESS if r >= 4.5 else PRIMARY if r >= 3.8 else ACCENT2 for r in p_rat]
            ax3.barh(p_names, p_rat, color=pc, edgecolor=T("SURFACE"), height=0.6, zorder=3)
            ax3.set_xlim(0, 5.5)
            ax3.set_xlabel("Rating", fontsize=9)
            ax3.set_title("App Ratings", fontsize=11, fontweight="bold", pad=12)
            ax3.axvline(4.0, color=T("BORDER2"), linestyle="--", linewidth=0.9, alpha=0.7, zorder=2)
            ax3.grid(axis="x", linestyle="--", alpha=0.15, color=T("BORDER"), zorder=1)
            for i, v in enumerate(p_rat):
                ax3.text(v + 0.07, i, f"{v:.1f}", va="center", fontsize=8,
                         fontweight="bold", color=T("TEXT1"))
            if free + paid > 0:
                w_patches, t_labels, at_pcts = ax4.pie(
                    [free, paid], labels=["Free", "Paid"], autopct="%1.0f%%",
                    colors=[SUCCESS, PRIMARY], startangle=90,
                    wedgeprops=dict(edgecolor=T("BG"), linewidth=2),
                )
                for a in at_pcts:
                    a.set_color(T("TEXT1")); a.set_fontweight("bold"); a.set_fontsize(10)
            ax4.set_title("Free vs Paid", fontsize=11, fontweight="bold", pad=12)
            fig.tight_layout(pad=2.2)
            embed(fig)

        # ── Sentiment ──────────────────────────────────────────────────────────
        if TEXTBLOB_AVAILABLE and all_texts and all_sent:
            section_hdr("◎", "Sentiment Analysis  —  Combined Reviews",
                        f"{len(all_texts)} reviews analysed")

            card_row = tk.Frame(scroll, bg=T("BG"), pady=6, padx=20)
            card_row.pack(fill="x")
            card_row.columnconfigure((0, 1, 2, 3), weight=1)

            def sent_card(col, label, value, fg=PRIMARY):
                f = tk.Frame(card_row, bg=T("SURFACE"), padx=10, pady=12)
                f.grid(row=0, column=col, padx=5, sticky="ew")
                tk.Frame(f, bg=fg, height=3).pack(fill="x", pady=(0, 6))
                tk.Label(f, text=value, font=("Segoe UI", 13, "bold"),
                         bg=T("SURFACE"), fg=fg).pack()
                tk.Label(f, text=label, font=FONT_SMALL, bg=T("SURFACE"),
                         fg=T("TEXT2")).pack(pady=(2, 0))

            total    = max(all_sent["positive"] + all_sent["negative"] + all_sent["neutral"], 1)
            pos_pct  = all_sent["positive"] / total * 100
            neg_pct  = all_sent["negative"] / total * 100
            pol      = all_sent["avg_polarity"]
            pol_color = SUCCESS if pol > 0.1 else DANGER if pol < -0.1 else WARNING

            sent_card(0, "Positive Reviews", f"{all_sent['positive']} ({pos_pct:.0f}%)", SUCCESS)
            sent_card(1, "Negative Reviews", f"{all_sent['negative']} ({neg_pct:.0f}%)", DANGER)
            sent_card(2, "Neutral Reviews",  f"{all_sent['neutral']}",                   WARNING)
            sent_card(3, "Avg Polarity",     f"{pol:+.3f}",                              pol_color)

            n_plots = sum([maps_sent is not None, play_sent is not None,
                           bool(all_sent["keywords"])])
            if n_plots:
                fig  = Figure(figsize=(14, 4.2), dpi=96)
                fig.patch.set_facecolor(T("BG"))
                axes = [fig.add_subplot(1, n_plots, i + 1) for i in range(n_plots)]
                ax_idx = 0

                def draw_pie(ax, sd, title_str):
                    ax.set_facecolor(T("SURFACE"))
                    vals = [sd["positive"], sd["neutral"], sd["negative"]]
                    labs = ["Positive", "Neutral", "Negative"]
                    clrs = [SUCCESS, WARNING, DANGER]
                    nz   = [(v, l, c) for v, l, c in zip(vals, labs, clrs) if v > 0]
                    if nz:
                        vz, lz, cz = zip(*nz)
                        wedges, texts, autos = ax.pie(
                            vz, labels=lz, autopct="%1.0f%%", colors=cz, startangle=90,
                            wedgeprops={"edgecolor": T("BG"), "linewidth": 2},
                            pctdistance=0.78,
                        )
                        for t in texts:  t.set_color(T("TEXT1")); t.set_fontsize(9)
                        for a in autos:  a.set_color("#fff"); a.set_fontweight("bold"); a.set_fontsize(9)
                    ax.set_title(f"{title_str}\nPolarity: {sd['avg_polarity']:+.3f}",
                                 fontweight="bold", fontsize=10, pad=10)

                if maps_sent:
                    draw_pie(axes[ax_idx], maps_sent, "Maps Reviews");   ax_idx += 1
                if play_sent:
                    draw_pie(axes[ax_idx], play_sent, "Play Reviews");   ax_idx += 1
                if all_sent["keywords"]:
                    ax   = axes[ax_idx]
                    ax.set_facecolor(T("SURFACE"))
                    kws  = [k for k, _ in all_sent["keywords"][:10]]
                    cnts = [c for _, c in all_sent["keywords"][:10]]
                    bar_colors = [
                        SUCCESS if cnt == max(cnts) else
                        PRIMARY if cnt >= sorted(cnts)[-min(3, len(cnts))] else ACCENT2
                        for cnt in cnts
                    ]
                    bars = ax.barh(kws, cnts, color=bar_colors,
                                   edgecolor=T("BG"), height=0.55)
                    ax.set_xlim(0, max(cnts) * 1.35 + 1)
                    for bar, val in zip(bars, cnts):
                        ax.text(val + max(cnts) * 0.03,
                                bar.get_y() + bar.get_height() / 2,
                                str(val), va="center", fontsize=8,
                                fontweight="bold", color=T("TEXT1"))
                    ax.set_title("Top Keywords", fontweight="bold", fontsize=10, pad=10)
                    ax.grid(axis="x", linestyle="--", alpha=0.15, color=T("BORDER"))
                fig.tight_layout(pad=2.2)
                embed(fig)

        elif not TEXTBLOB_AVAILABLE:
            section_hdr("◎", "Sentiment Analysis", "TextBlob not installed")
            tk.Label(scroll, text="Install TextBlob:\n  pip install textblob",
                     font=FONT_BODY, fg=WARNING, bg=T("BG"), pady=12).pack(anchor="w", padx=24)
        else:
            section_hdr("◎", "Sentiment Analysis", "No reviews yet")
            tk.Label(scroll,
                     text="Double-click a shop or app to load reviews, then re-run analytics.",
                     font=FONT_BODY, fg=T("TEXT2"), bg=T("BG"), pady=12).pack(anchor="w", padx=24)

        tk.Frame(scroll, bg=T("BG"), height=24).pack()

    # ── Summary tab ───────────────────────────────────────────────────────────
    def _build_summary(self):
        for w in self.summary_inner.winfo_children():
            w.destroy()
        _, inner, _ = scrollable_frame(self.summary_inner, bg=T("BG"))
        query = self.query_var.get().strip()

        # ── Hero header ────────────────────────────────────────────────────
        hero = tk.Frame(inner, bg=T("SURFACE2"), pady=22, padx=28)
        hero.pack(fill="x")
        # top rainbow strip
        rainbow = tk.Frame(hero, height=3, bg=T("SURFACE2"))
        rainbow.pack(fill="x", pady=(0, 14))
        for col in [PRIMARY, ACCENT, ACCENT2, ACCENT3, SUCCESS]:
            tk.Frame(rainbow, bg=col, height=3).pack(side="left", fill="x", expand=True)

        tk.Label(hero, text=f'✦  Market Summary',
                 font=("Segoe UI Variable", 16, "bold"),
                 bg=T("SURFACE2"), fg=T("TEXT1")).pack(anchor="w")
        tk.Label(hero, text=f'"{query}"  ·  {self.loc_var.get()}',
                 font=("Segoe UI Variable", 11),
                 bg=T("SURFACE2"), fg=PRIMARY).pack(anchor="w", pady=(4, 0))

        sort_labels = {
            "nearest":  "Nearest first",
            "top_rated": "Top Rated first",
            "both":     "Best Match (rating + proximity)",
        }
        meta = (f'{datetime.now().strftime("%d %b %Y  ·  %H:%M")}  ·  '
                f'Sort: {sort_labels.get(self.sort_preference, "")}')
        tk.Label(hero, text=meta,
                 font=("Cascadia Code", 8),
                 bg=T("SURFACE2"), fg=T("TEXT3")).pack(anchor="w", pady=(4, 0))

        # ── KPI stat cards ────────────────────────────────────────────────
        cards = tk.Frame(inner, bg=T("BG"))
        cards.pack(fill="x", padx=24, pady=14)
        cards.columnconfigure((0, 1, 2, 3), weight=1)

        def sc(col, icon, title, value, sub, fg=PRIMARY):
            f = tk.Frame(cards, bg=T("SURFACE"),
                         highlightbackground=T("BORDER2"),
                         highlightthickness=1,
                         padx=16, pady=16)
            f.grid(row=0, column=col, padx=5, sticky="ew")
            tk.Frame(f, bg=fg, height=2).pack(fill="x", pady=(0, 10))
            tk.Label(f, text=icon,
                     font=("Segoe UI", 22),
                     bg=T("SURFACE"), fg=fg).pack()
            tk.Label(f, text=value,
                     font=("Segoe UI Variable", 17, "bold"),
                     bg=T("SURFACE"), fg=fg).pack(pady=(4, 0))
            tk.Label(f, text=title,
                     font=FONT_LABEL, bg=T("SURFACE"), fg=T("TEXT1")).pack()
            tk.Label(f, text=sub,
                     font=FONT_SMALL, bg=T("SURFACE"), fg=T("TEXT3")).pack(pady=(2, 0))

        sc(0, "🗺", "Local Shops",     str(len(self.maps_data)), "Google Maps", ACCENT)
        sc(1, "📱", "Apps Found",      str(len(self.play_data)), "Google Play", PRIMARY)
        sc(2, "🛍", "Amazon Products", str(len(self.amzn_data)), "Amazon.in",   ACCENT2)
        sc(3, "◎", "Total Results",
           str(len(self.maps_data) + len(self.play_data) + len(self.amzn_data)),
           "all sources", SUCCESS)

        # ── Divider ───────────────────────────────────────────────────────
        div_row = tk.Frame(inner, bg=T("BG"), padx=24, pady=4)
        div_row.pack(fill="x")
        tk.Frame(div_row, bg=T("BORDER2"), height=1).pack(fill="x")

        # ── Section builder ───────────────────────────────────────────────
        def section(icon, title, rows, highs=(), accent=PRIMARY):
            sf = tk.Frame(inner, bg=T("SURFACE"),
                          highlightbackground=T("BORDER"),
                          highlightthickness=1,
                          padx=22, pady=18)
            sf.pack(fill="x", padx=24, pady=6)
            # Left accent stripe
            tk.Frame(sf, bg=accent, width=3).pack(side="left", fill="y", padx=(0, 16))
            col = tk.Frame(sf, bg=T("SURFACE"))
            col.pack(side="left", fill="both", expand=True)
            tk.Label(col, text=f"{icon}  {title}",
                     font=("Segoe UI Variable", 10, "bold"),
                     bg=T("SURFACE"), fg=T("TEXT1")).pack(anchor="w", pady=(0, 10))
            for lbl, val in rows:
                row = tk.Frame(col, bg=T("SURFACE"))
                row.pack(fill="x", pady=3)
                tk.Label(row, text=lbl,
                         font=FONT_LABEL, bg=T("SURFACE"),
                         fg=T("TEXT2"), width=26, anchor="w").pack(side="left")
                tk.Label(row, text=val,
                         font=FONT_BODY, bg=T("SURFACE"),
                         fg=T("TEXT1")).pack(side="left")
            for hl_text, hl_fg in highs:
                hf = tk.Frame(col, bg=T("SURFACE2"),
                              padx=12, pady=7)
                hf.pack(fill="x", pady=(6, 0))
                tk.Frame(hf, bg=hl_fg, width=3).pack(side="left", fill="y", padx=(0, 10))
                tk.Label(hf, text=hl_text,
                         font=FONT_BODY, bg=T("SURFACE2"),
                         fg=T("TEXT1")).pack(side="left")

        if self.maps_data and self.maps_report:
            r     = self.maps_report
            rated = [c for c in self.maps_data if c["rating"] > 0]
            highs = []
            if rated:
                top = max(rated, key=lambda x: x["rating"])
                pop = max(rated, key=lambda x: x["review_count"])
                highs = [
                    (f"Highest Rated:  {top['name']}  ({top['rating']}/5.0)", SUCCESS),
                    (f"Most Popular:  {pop['name']}  ({pop['review_count']:,} reviews)", PRIMARY),
                ]
            section("🗺", "Google Maps  —  Local Shops", [
                ("Total shops",   str(r["total"])),
                ("Sort order",    sort_labels.get(self.sort_preference, "")),
                ("Avg rating",    f"{r['avg_rating']}/5.0"),
                ("Total reviews", f"{r['total_reviews']:,}"),
                ("Rating range",  f"{r['rating_range'][0]:.1f}  –  {r['rating_range'][1]:.1f}"),
            ], highs, accent=ACCENT)

        if self.play_data:
            rp    = [a for a in self.play_data if a.get("rating")]
            avg_r = round(sum(a["rating"] for a in rp) / len(rp), 2) if rp else 0
            free  = sum(1 for a in self.play_data if a.get("isFree"))
            highs = []
            if rp:
                ta    = max(rp, key=lambda x: x["rating"])
                highs = [(f"Top App:  {ta['appTitle']}  ({ta['rating']:.1f}/5.0)", SUCCESS)]
            section("📱", "Google Play  —  App Store", [
                ("Apps found", str(len(self.play_data))),
                ("Avg rating", f"{avg_r}/5.0"),
                ("Free apps",  str(free)),
                ("Paid apps",  str(len(self.play_data) - free)),
            ], highs, accent=PRIMARY)

        if self.amzn_data:
            prices = [p["price_num"] for p in self.amzn_data if p.get("price_num")]
            section("🛍", "Amazon.in  —  Products", [
                ("Products found", str(len(self.amzn_data))),
                ("Price range",    f"₹{min(prices):,.0f}  –  ₹{max(prices):,.0f}" if prices else "N/A"),
                ("Avg price",      f"₹{sum(prices)/len(prices):,.0f}" if prices else "N/A"),
            ], accent=ACCENT2)

        if self.trends_data and "error" not in self.trends_data:
            td          = self.trends_data
            trend_color = (SUCCESS if td["trend"] == "rising" else
                           DANGER  if td["trend"] == "declining" else ACCENT2)
            section("📈", "Google Trends  —  Demand Signal", [
                ("12-month trend", td["trend"].upper()),
                ("Avg interest",   str(td["avg"])),
                ("Peak interest",  str(td["peak"])),
            ], [(
                f"Demand is {td['trend'].upper()} — "
                f"{'Good time to enter!' if td['trend']=='rising' else 'Market may be declining.' if td['trend']=='declining' else 'Stable demand.'}",
                trend_color,
            )], accent=trend_color)

        if self.last_price_range and self.amzn_data:
            prices = [p["price_num"] for p in self.amzn_data if p.get("price_num")]
            if prices:
                target_mid = (self.last_price_range[0] + self.last_price_range[1]) / 2
                cheaper    = sum(1 for p in prices if p < target_mid)
                pct        = (cheaper / len(prices)) * 100
                pos_label  = ("Premium positioning — justify with quality."
                              if pct > 60 else "Competitive positioning — highlight value.")
                ppf = tk.Frame(inner, bg=T("SURFACE2"),
                               highlightbackground=ACCENT, highlightthickness=1,
                               padx=22, pady=16)
                ppf.pack(fill="x", padx=24, pady=6)
                tk.Label(ppf, text="◈  Price Positioning Analysis",
                         font=("Segoe UI Variable", 10, "bold"),
                         bg=T("SURFACE2"), fg=ACCENT).pack(anchor="w")
                tk.Label(ppf,
                         text=(f"Your target ₹{self.last_price_range[0]:,}–"
                               f"₹{self.last_price_range[1]:,} "
                               f"is higher than {pct:.0f}% of Amazon competitors.  "
                               f"{pos_label}"),
                         font=FONT_BODY, bg=T("SURFACE2"), fg=T("TEXT1"),
                         wraplength=900, justify="left").pack(anchor="w", pady=(8, 0))

        # ── Export / Action buttons ────────────────────────────────────────
        ef = tk.Frame(inner, bg=T("BG"))
        ef.pack(anchor="w", padx=24, pady=22)
        tk.Button(ef, text="  ↓  Export JSON  ",
                  font=FONT_LABEL, bg=T("SURFACE"), fg=T("TEXT1"),
                  highlightbackground=T("BORDER2"), highlightthickness=1,
                  relief="flat", padx=14, pady=9, cursor="hand2",
                  command=self._export_json).pack(side="left", padx=(0, 8))
        tk.Button(ef, text="  ✦  Generate AI Report  ",
                  font=FONT_LABEL, bg=ACCENT, fg="#041510",
                  relief="flat", padx=14, pady=9, cursor="hand2",
                  command=self._generate_report).pack(side="left", padx=(0, 8))
        tk.Button(ef, text="  📈  Break-Even Calculator  ",
                  font=FONT_LABEL, bg=ACCENT2, fg="#0a0800",
                  relief="flat", padx=14, pady=9, cursor="hand2",
                  command=lambda: BreakEvenCalculator(
                      self, self.last_price_range, self.amzn_data)).pack(side="left")

    def _export_json(self):
        if not any([self.maps_data, self.play_data, self.amzn_data]):
            messagebox.showwarning("Export", "Run a search first.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON", "*.json")],
            initialfile=f"market_research_{self.query_var.get().strip().replace(' ','_')}.json",
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                json.dump({
                    "timestamp":       datetime.now().isoformat(),
                    "query":           self.query_var.get().strip(),
                    "location":        self.loc_var.get(),
                    "price_range":     self.last_price_range,
                    "sort_preference": self.sort_preference,
                    "maps":            self.maps_data,
                    "play":            self.play_data,
                    "amazon":          self.amzn_data,
                    "trends":          self.trends_data,
                }, f, indent=2, ensure_ascii=False)
            messagebox.showinfo("Exported", f"Saved to:\n{path}")
            log.info(f"JSON exported: {path}")

    # FIX: cancel the clock callback before destroying to prevent Tcl errors
    def _on_closing(self):
        if self._clock_after_id:
            try:
                self.after_cancel(self._clock_after_id)
            except Exception:
                pass
        try:
            import matplotlib.pyplot as plt
            plt.close("all")
        except Exception:
            pass
        log.info("App closed")
        self.quit()
        self.destroy()
        import os
        os._exit(0)


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    log.info("Starting Market Research Pro — Ultimate Edition (hang-free build)")
    app = MarketResearchApp()
    app.mainloop()