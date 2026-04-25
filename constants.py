import os
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from dotenv import load_dotenv

load_dotenv()

SERPAPI_KEY = os.getenv("SERPAPI_KEY")

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen2.5:7b-instruct"

BG = "#0f172a"
PANEL = "#1e293b"
WHITE = "#ffffff"
PRIMARY = "#3b82f6"
PRI_DARK = "#2563eb"
PRI_LIGHT = "#1e3a5f"
ACCENT = "#06b6d4"
GOLD = "#f59e0b"
SUCCESS = "#22c55e"
WARNING = "#f97316"
DANGER = "#ef4444"
TEXT = "#f1f5f9"
SUBTEXT = "#94a3b8"
BORDER = "#334155"
ROW_ALT = "#1a2740"
ROW_SEL = "#1d4ed8"
GREEN_BG = "#14532d"

FONT_TITLE = ("Segoe UI", 17, "bold")
FONT_HEADING = ("Segoe UI", 12, "bold")
FONT_LABEL = ("Segoe UI", 10, "bold")
FONT_BODY = ("Segoe UI", 10)
FONT_SMALL = ("Segoe UI", 9)
FONT_TINY = ("Segoe UI", 8)

plt.rcParams.update({
    "axes.facecolor": PANEL,
    "figure.facecolor": BG,
    "axes.edgecolor": BORDER,
    "axes.labelcolor": "#cbd5e1",
    "xtick.color": SUBTEXT,
    "ytick.color": SUBTEXT,
    "text.color": TEXT,
    "grid.color": BORDER,
    "axes.titlecolor": TEXT,
})
