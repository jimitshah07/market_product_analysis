import tkinter as tk
from tkinter import ttk
from datetime import datetime
from constants import PANEL, SUBTEXT, SUCCESS, WARNING, DANGER


def rating_color(score) -> str:
    try:
        score = float(score)
    except (TypeError, ValueError):
        return SUBTEXT
    if score >= 4.0:
        return SUCCESS
    if score >= 3.0:
        return WARNING
    return DANGER


def scrollable_frame(parent, bg=PANEL):
    outer = tk.Frame(parent, bg=bg)
    outer.pack(fill="both", expand=True)
    canvas = tk.Canvas(outer, bg=bg, bd=0, highlightthickness=0)
    vsb = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=vsb.set)
    vsb.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)
    inner = tk.Frame(canvas, bg=bg)
    win_id = canvas.create_window((0, 0), window=inner, anchor="nw")
    inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.bind("<Configure>", lambda e: canvas.itemconfig(win_id, width=e.width))
    canvas.bind("<MouseWheel>", lambda e: canvas.yview_scroll(-1*(e.delta//120), "units"))
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
                day_str = entry.get("day", "")
                time_str = entry.get("hours", "")
                if now_day[:3].lower() in day_str.lower() or now_day.lower() in day_str.lower():
                    if "-" in time_str:
                        parts = time_str.split("-", 1)
                        return f"Opens {parts[0].strip()}  ·  Closes {parts[1].strip() if len(parts)>1 else ''}"
                    return time_str
            elif isinstance(entry, str):
                return entry
        first = hours_raw[0]
        if isinstance(first, dict):
            t = first.get("hours", "")
            if "-" in t:
                parts = t.split("-", 1)
                return f"Opens {parts[0].strip()}  ·  Closes {parts[1].strip() if len(parts)>1 else ''}"
            return t
        return str(first)
    return str(hours_raw)
