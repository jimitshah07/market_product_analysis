import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import json
import webbrowser
from datetime import datetime
from typing import List, Dict, Optional
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from constants import (
    BG, PANEL, PRIMARY, PRI_DARK, PRI_LIGHT, ACCENT, GOLD,
    SUCCESS, WARNING, DANGER, TEXT, SUBTEXT, BORDER, WHITE,
    ROW_ALT, ROW_SEL, GREEN_BG, FONT_TITLE, FONT_HEADING,
    FONT_LABEL, FONT_BODY, FONT_SMALL, FONT_TINY
)
from utils import scrollable_frame
from fetchers import MapsDataFetcher, PlayStoreFetcher, AmazonFetcher
from popups import MapsReviewPopup, PlayDetailPopup
from llm import parse_prompt_with_llm


class MarketResearchApp(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("Market Research Tool")
        self.geometry("1440x900")
        self.minsize(1100, 700)
        self.configure(bg=BG)

        self._apply_styles()

        self.maps_data: List[Dict] = []
        self.play_data: List[Dict] = []
        self.amzn_data: List[Dict] = []
        self.maps_report: Optional[Dict] = None

        self.protocol("WM_DELETE_WINDOW", self._on_closing)
        self._build_ui()

    def _apply_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, font=FONT_BODY)
        style.configure("TNotebook", background=BG, tabmargins=[2, 5, 2, 0])
        style.configure("TNotebook.Tab", font=FONT_LABEL, padding=[16, 8])
        style.map("TNotebook.Tab",
                  background=[("selected", PANEL), ("!selected", BG)],
                  foreground=[("selected", WHITE), ("!selected", SUBTEXT)])
        style.configure("Treeview",
                        font=FONT_BODY, rowheight=28,
                        background=PANEL, fieldbackground=PANEL, foreground=TEXT)
        style.configure("Treeview.Heading",
                        font=FONT_LABEL, background=PRI_LIGHT, foreground=ACCENT)
        style.map("Treeview",
                  background=[("selected", ROW_SEL)],
                  foreground=[("selected", WHITE)])
        style.configure("Vertical.TScrollbar", background=BORDER, troughcolor=BG)

    def _build_ui(self):
        self._build_header()
        self._build_llm_bar()
        self._build_search_bar()
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x")
        self._build_notebook()
        self._build_status_bar()

    def _build_header(self):
        hdr = tk.Frame(self, bg=PANEL, pady=14)
        hdr.pack(fill="x")
        tk.Frame(hdr, bg=PRIMARY, width=6).pack(side="left", fill="y", padx=(14, 14))
        blk = tk.Frame(hdr, bg=PANEL)
        blk.pack(side="left")
        tk.Label(blk, text="📊  Market Research Tool",
                 font=FONT_TITLE, bg=PANEL, fg=WHITE).pack(anchor="w")
        tk.Label(blk, text="Describe your product in plain English  →  AI extracts  →  auto-searches",
                 font=FONT_SMALL, bg=PANEL, fg=SUBTEXT).pack(anchor="w")
        self._clock = tk.Label(hdr, text="", font=FONT_SMALL, bg=PANEL, fg=SUBTEXT)
        self._clock.pack(side="right", padx=18)
        self._tick_clock()

    def _tick_clock(self):
        self._clock.config(text=datetime.now().strftime("%H:%M:%S   %d %b %Y"))
        self.after(1000, self._tick_clock)

    def _build_llm_bar(self):
        outer = tk.Frame(self, bg="#0c1a2e", pady=10, padx=16)
        outer.pack(fill="x")

        lbl_frame = tk.Frame(outer, bg="#0c1a2e")
        lbl_frame.pack(fill="x", pady=(0, 6))
        tk.Label(lbl_frame, text="🤖  Describe your product in plain English:",
                 font=FONT_LABEL, bg="#0c1a2e", fg=ACCENT).pack(side="left")
        tk.Label(lbl_frame,
                 text='e.g. "I want to sell gaming chairs in Hyderabad for 25000 to 35000"',
                 font=FONT_SMALL, bg="#0c1a2e", fg=SUBTEXT).pack(side="left", padx=10)

        input_row = tk.Frame(outer, bg="#0c1a2e")
        input_row.pack(fill="x")

        self.llm_var = tk.StringVar()
        self.llm_entry = tk.Entry(
            input_row, textvariable=self.llm_var, font=FONT_BODY,
            bg="#1e293b", fg=TEXT, insertbackground=TEXT,
            relief="solid", bd=1,
            highlightbackground=BORDER, highlightcolor=ACCENT, highlightthickness=1,
        )
        self.llm_entry.pack(side="left", fill="x", expand=True, ipady=7, padx=(0, 10))
        self.llm_entry.bind("<Return>", lambda e: self._run_llm_parse())

        self.llm_btn = tk.Button(
            input_row, text="🤖  Parse with AI",
            font=FONT_LABEL, bg=ACCENT, fg=WHITE,
            relief="flat", padx=18, pady=7, cursor="hand2",
            activebackground="#0891b2", activeforeground=WHITE,
            command=self._run_llm_parse,
        )
        self.llm_btn.pack(side="left")

        self.llm_status = tk.Label(
            outer, text="", font=FONT_SMALL, bg="#0c1a2e", fg=SUBTEXT
        )
        self.llm_status.pack(anchor="w", pady=(4, 0))

    def _run_llm_parse(self):
        user_text = self.llm_var.get().strip()
        if not user_text:
            messagebox.showwarning("Empty Prompt", "Please type something first.")
            return

        self.llm_btn.config(state="disabled", text="⏳ Parsing…", bg=SUBTEXT)
        self.llm_status.config(text="Contacting Ollama…", fg=WARNING)

        def worker():
            try:
                result = parse_prompt_with_llm(user_text)
                self.after(0, lambda: self._on_llm_success(result))
            except Exception as e:
                self.after(0, lambda: self._on_llm_fail(str(e)))

        threading.Thread(target=worker, daemon=True).start()

    def _on_llm_success(self, result: dict):
        product = result.get("product", "")
        location = result.get("location", "")
        price = result.get("price_range")

        if product:
            self.query_var.set(product)
        if location:
            self.loc_var.set(location)

        price_str = ""
        if price and isinstance(price, list) and len(price) == 2:
            price_str = f"  ·  Price range: ₹{price[0]:,} - ₹{price[1]:,}"

        self.llm_status.config(
            text=f"✅  Extracted → product: \"{product}\"  ·  location: \"{location}\"{price_str}  ·  Starting search…",
            fg=SUCCESS,
        )
        self.llm_btn.config(state="normal", text="🤖  Parse with AI", bg=ACCENT)
        self._run_all()

    def _on_llm_fail(self, msg: str):
        self.llm_status.config(text=f"❌  Error: {msg[:120]}", fg=DANGER)
        self.llm_btn.config(state="normal", text="🤖  Parse with AI", bg=ACCENT)
        messagebox.showerror("LLM Parse Error", msg)

    def _build_search_bar(self):
        self.query_var = tk.StringVar()
        self.loc_var = tk.StringVar(value="Ahmedabad")

        self.spin_hits = tk.Spinbox(self, from_=3, to=20, width=4)
        self.spin_hits.delete(0, "end")
        self.spin_hits.insert(0, "10")

    def _build_notebook(self):
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=12, pady=(8, 0))

        self.maps_tab = ttk.Frame(self.nb)
        self.nb.add(self.maps_tab, text="  🗺️  Local Shops  ")
        self._build_maps_tab()

        self.play_tab = ttk.Frame(self.nb)
        self.nb.add(self.play_tab, text="  📱  App Store  ")
        self._build_play_tab()

        self.amzn_tab = ttk.Frame(self.nb)
        self.nb.add(self.amzn_tab, text="  🛒  Amazon  ")
        self._build_amzn_tab()

        self.analytics_tab = ttk.Frame(self.nb)
        self.nb.add(self.analytics_tab, text="  📊  Analytics  ")
        self.analytics_inner = tk.Frame(self.analytics_tab, bg=BG)
        self.analytics_inner.pack(fill="both", expand=True)

        self.summary_tab = ttk.Frame(self.nb)
        self.nb.add(self.summary_tab, text="  📈  Summary  ")
        self.summary_inner = tk.Frame(self.summary_tab, bg=BG)
        self.summary_inner.pack(fill="both", expand=True)

    def _build_maps_tab(self):
        cols = ("Rank", "Shop Name", "Type", "Rating", "Reviews", "Price", "Hours / Status", "Address")
        widths = [45, 200, 150, 80, 90, 65, 200, 260]
        anchors = ["center", "w", "w", "center", "center", "center", "w", "w"]
        self.maps_tree = ttk.Treeview(self.maps_tab, columns=cols, height=20, show="headings")
        for col, w, a in zip(cols, widths, anchors):
            self.maps_tree.column(col, width=w, anchor=a, minwidth=40)
            self.maps_tree.heading(col, text=col)
        vsb = ttk.Scrollbar(self.maps_tab, orient="vertical", command=self.maps_tree.yview)
        hsb = ttk.Scrollbar(self.maps_tab, orient="horizontal", command=self.maps_tree.xview)
        self.maps_tree.configure(yscroll=vsb.set, xscroll=hsb.set)
        self.maps_tree.tag_configure("odd", background=ROW_ALT)
        self.maps_tree.tag_configure("even", background=PANEL)
        self.maps_tree.tag_configure("toprated", background=GREEN_BG)
        self.maps_tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        self.maps_tab.rowconfigure(0, weight=1)
        self.maps_tab.columnconfigure(0, weight=1)
        self.maps_tree.bind("<Double-1>", self._maps_open_detail)
        tk.Label(self.maps_tab, text="💡  Double-click a row → full reviews & Google Maps",
                 font=FONT_SMALL, fg=ACCENT, bg=BG).grid(row=2, column=0, sticky="w", padx=8, pady=4)

    def _build_play_tab(self):
        cols = ("#", "App Name", "Rating", "Genre", "Installs", "Price")
        widths = [40, 340, 90, 180, 140, 100]
        anchors = ["center", "w", "center", "w", "center", "center"]
        self.play_tree = ttk.Treeview(self.play_tab, columns=cols, height=20, show="headings")
        for col, w, a in zip(cols, widths, anchors):
            self.play_tree.column(col, width=w, anchor=a, minwidth=30)
            self.play_tree.heading(col, text=col)
        vsb = ttk.Scrollbar(self.play_tab, orient="vertical", command=self.play_tree.yview)
        hsb = ttk.Scrollbar(self.play_tab, orient="horizontal", command=self.play_tree.xview)
        self.play_tree.configure(yscroll=vsb.set, xscroll=hsb.set)
        self.play_tree.tag_configure("odd", background=ROW_ALT)
        self.play_tree.tag_configure("even", background=PANEL)
        self.play_tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        self.play_tab.rowconfigure(0, weight=1)
        self.play_tab.columnconfigure(0, weight=1)
        self.play_tree.bind("<Double-1>", self._play_open_detail)
        tk.Label(self.play_tab, text="💡  Double-click → app details & user reviews",
                 font=FONT_SMALL, fg=ACCENT, bg=BG).grid(row=2, column=0, sticky="w", padx=8, pady=4)

    def _build_amzn_tab(self):
        cols = ("#", "Product Title", "Price", "Rating", "Reviews", "Position")
        widths = [40, 520, 100, 80, 100, 80]
        anchors = ["center", "w", "center", "center", "center", "center"]
        self.amzn_tree = ttk.Treeview(self.amzn_tab, columns=cols, height=20, show="headings")
        for col, w, a in zip(cols, widths, anchors):
            self.amzn_tree.column(col, width=w, anchor=a, minwidth=30)
            self.amzn_tree.heading(col, text=col)
        vsb = ttk.Scrollbar(self.amzn_tab, orient="vertical", command=self.amzn_tree.yview)
        hsb = ttk.Scrollbar(self.amzn_tab, orient="horizontal", command=self.amzn_tree.xview)
        self.amzn_tree.configure(yscroll=vsb.set, xscroll=hsb.set)
        self.amzn_tree.tag_configure("odd", background=ROW_ALT)
        self.amzn_tree.tag_configure("even", background=PANEL)
        self.amzn_tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        self.amzn_tab.rowconfigure(0, weight=1)
        self.amzn_tab.columnconfigure(0, weight=1)
        self.amzn_tree.bind("<Double-1>", self._amzn_open_link)
        tk.Label(self.amzn_tab, text="💡  Double-click → open product on Amazon.in",
                 font=FONT_SMALL, fg=ACCENT, bg=BG).grid(row=2, column=0, sticky="w", padx=8, pady=4)

    def _build_status_bar(self):
        bar = tk.Frame(self, bg=PANEL)
        bar.pack(fill="x", side="bottom")
        tk.Frame(bar, bg=BORDER, height=1).pack(fill="x")
        row = tk.Frame(bar, bg=PANEL)
        row.pack(fill="x", padx=14, pady=5)
        self.st_maps = tk.Label(row, text="🗺️  Maps: —", font=FONT_SMALL, bg=PANEL, fg=SUBTEXT)
        self.st_play = tk.Label(row, text="📱  Play: —", font=FONT_SMALL, bg=PANEL, fg=SUBTEXT)
        self.st_amzn = tk.Label(row, text="🛒  Amazon: —", font=FONT_SMALL, bg=PANEL, fg=SUBTEXT)
        for lbl in (self.st_maps, self.st_play, self.st_amzn):
            lbl.pack(side="left", padx=(0, 30))
        tk.Label(row, text="💡  Double-click any row for full details",
                 font=FONT_TINY, bg=PANEL, fg=SUBTEXT).pack(side="right")

    def _run_all(self):
        query = self.query_var.get().strip()
        if not query:
            messagebox.showwarning("Missing input", "Please enter a product or niche.")
            return

        self.llm_btn.config(state="disabled", bg=SUBTEXT)
        self.st_maps.config(text="🗺️  Maps: searching…", fg=WARNING)
        self.st_play.config(text="📱  Play: searching…", fg=WARNING)
        self.st_amzn.config(text="🛒  Amazon: searching…", fg=WARNING)

        for t in (self.maps_tree, self.play_tree, self.amzn_tree):
            for item in t.get_children():
                t.delete(item)
        for w in self.analytics_inner.winfo_children():
            w.destroy()
        for w in self.summary_inner.winfo_children():
            w.destroy()

        self.maps_data = []
        self.play_data = []
        self.amzn_data = []
        self.maps_report = None

        location = self.loc_var.get().strip() or "Ahmedabad"
        try:
            n_hits = int(self.spin_hits.get())
        except ValueError:
            n_hits = 10

        threading.Thread(target=self._worker_maps, args=(query, location), daemon=True).start()
        threading.Thread(target=self._worker_play, args=(query, n_hits), daemon=True).start()
        threading.Thread(target=self._worker_amzn, args=(query,), daemon=True).start()

    def _worker_maps(self, query, location):
        try:
            self.after(0, self._on_maps_success, MapsDataFetcher.fetch_places(query, location))
        except Exception as e:
            self.after(0, self._on_maps_fail, str(e))

    def _worker_play(self, query, n_hits):
        try:
            self.after(0, self._on_play_success, PlayStoreFetcher.fetch(query, n_hits))
        except Exception as e:
            self.after(0, self._on_play_fail, str(e))

    def _worker_amzn(self, query):
        try:
            self.after(0, self._on_amzn_success, AmazonFetcher.fetch(query))
        except Exception as e:
            self.after(0, self._on_amzn_fail, str(e))

    def _on_maps_success(self, data):
        self.maps_data = data
        self.st_maps.config(text=f"🗺️  Maps: {len(data)} shops  ✓", fg=SUCCESS)
        self._populate_maps(data)
        self._check_all_done()

    def _on_maps_fail(self, msg):
        self.st_maps.config(text="🗺️  Maps: error  ✗", fg=DANGER)
        messagebox.showerror("Maps Error", msg)
        self._check_all_done()

    def _on_play_success(self, data):
        self.play_data = data
        self.st_play.config(text=f"📱  Play: {len(data)} apps  ✓", fg=SUCCESS)
        self._populate_play(data)
        self._check_all_done()

    def _on_play_fail(self, msg):
        self.st_play.config(text="📱  Play: error  ✗", fg=DANGER)
        messagebox.showerror("Play Store Error", msg)
        self._check_all_done()

    def _on_amzn_success(self, data):
        self.amzn_data = data
        self.st_amzn.config(text=f"🛒  Amazon: {len(data)} products  ✓", fg=SUCCESS)
        self._populate_amzn(data)
        self._check_all_done()

    def _on_amzn_fail(self, msg):
        self.st_amzn.config(text="🛒  Amazon: error  ✗", fg=DANGER)
        messagebox.showerror("Amazon Error", msg)
        self._check_all_done()

    def _check_all_done(self):
        def done(lbl):
            return "✓" in lbl.cget("text") or "✗" in lbl.cget("text")
        if all(done(l) for l in (self.st_maps, self.st_play, self.st_amzn)):
            self.llm_btn.config(state="normal", bg=ACCENT)
            self._build_analytics()
            self._build_summary()

    def _populate_maps(self, data):
        for item in self.maps_tree.get_children():
            self.maps_tree.delete(item)
        total_rev = sum(c["review_count"] for c in data)
        for c in data:
            c["market_share"] = (c["review_count"] / total_rev * 100) if total_rev else 0
        sdata = sorted(data, key=lambda x: (x["rating"], x["review_count"]), reverse=True)
        for idx, c in enumerate(sdata, 1):
            tag = "toprated" if c["rating"] >= 4.5 else ("even" if idx % 2 == 0 else "odd")
            hours_col = c.get("hours_display", "") or c["business_status"].replace("_", " ").title()
            self.maps_tree.insert("", tk.END, tags=(tag,), values=(
                idx, c["name"], c["type"][:30],
                f"{c['rating']}/5" if c["rating"] else "N/A",
                f"{c['review_count']:,}", c["price_label"], hours_col, c["location"],
            ))
        rated = [c["rating"] for c in data if c["rating"] > 0]
        self.maps_report = {
            "total": len(data),
            "avg_rating": round(sum(rated) / len(rated), 2) if rated else 0,
            "total_reviews": total_rev,
            "rating_range": (min(rated, default=0), max(rated, default=0)),
        }

    def _populate_play(self, data):
        for item in self.play_tree.get_children():
            self.play_tree.delete(item)
        for i, comp in enumerate(data, 1):
            rating = comp.get("rating", 0)
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
                i, title, p["price"], p["rating"], p.get("reviews", 0), p.get("position", ""),
            ))

    def _maps_open_detail(self, event):
        sel = self.maps_tree.selection()
        if not sel:
            return
        idx = self.maps_tree.index(sel[0])
        sd = sorted(self.maps_data, key=lambda x: (x["rating"], x["review_count"]), reverse=True)
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

    def _build_analytics(self):
        for w in self.analytics_inner.winfo_children():
            w.destroy()

        maps_valid = [c for c in self.maps_data if c["rating"] > 0]
        amzn_prices = [p["price_num"] for p in self.amzn_data if p.get("price_num")]
        play_rated = [a for a in self.play_data if a.get("rating")]

        if not maps_valid and not amzn_prices and not play_rated:
            tk.Label(self.analytics_inner, text="Run a search first to see analytics.",
                     font=FONT_BODY, fg=SUBTEXT, bg=BG).pack(pady=60)
            return

        _, scroll, _ = scrollable_frame(self.analytics_inner, bg=BG)

        def section_hdr(icon, title, sub):
            tk.Frame(scroll, bg=BORDER, height=1).pack(fill="x", pady=(18, 0))
            hf = tk.Frame(scroll, bg=PRI_LIGHT, pady=10, padx=20)
            hf.pack(fill="x")
            tk.Label(hf, text=f"{icon}  {title}", font=("Segoe UI", 13, "bold"),
                     bg=PRI_LIGHT, fg=ACCENT).pack(side="left")
            tk.Label(hf, text=sub, font=FONT_SMALL, bg=PRI_LIGHT, fg=SUBTEXT).pack(side="left", padx=14)

        def embed(fig):
            cv = FigureCanvasTkAgg(fig, master=scroll)
            cv.draw()
            cv.get_tk_widget().pack(fill="x", padx=20, pady=(6, 2))
            plt.close(fig)

        section_hdr("🗺️", "Google Maps — Local Shops", f"{len(self.maps_data)} shops")
        if maps_valid:
            names = [c["name"][:16] for c in maps_valid]
            ratings = [c["rating"] for c in maps_valid]
            reviews = [c["review_count"] for c in maps_valid]
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, max(3.2, len(names)*0.38)))
            bar_colors = [SUCCESS if r >= 4.5 else PRIMARY if r >= 4.0 else GOLD for r in ratings]
            ax1.barh(names, ratings, color=bar_colors, edgecolor=BG, height=0.6)
            ax1.set_xlim(0, 5.5)
            ax1.set_xlabel("Rating", fontweight="bold")
            ax1.set_title("Shop Ratings", fontweight="bold")
            ax1.axvline(4.0, color=BORDER, linestyle="--", linewidth=0.9, alpha=0.7)
            for i, v in enumerate(ratings):
                ax1.text(v+0.07, i, f"{v:.1f}", va="center", fontsize=8, fontweight="bold")
            ax2.scatter(ratings, reviews, color=DANGER, s=90, zorder=3, alpha=0.85)
            for i, n in enumerate(names):
                ax2.annotate(n, (ratings[i], reviews[i]), xytext=(10, 6), textcoords="offset points",
                             fontsize=7, color=TEXT,
                             bbox=dict(boxstyle="round,pad=0.3", facecolor=PANEL, alpha=0.85, edgecolor=BORDER))
            ax2.set_xlabel("Rating", fontweight="bold")
            ax2.set_ylabel("Reviews", fontweight="bold")
            ax2.set_title("Rating vs Popularity", fontweight="bold")
            ax2.grid(True, linestyle="--", alpha=0.3)
            fig.tight_layout(pad=2.0)
            embed(fig)

        section_hdr("📱", "Google Play — App Store", f"{len(self.play_data)} apps")
        if play_rated:
            p_names = [a["appTitle"][:18] for a in play_rated]
            p_rat = [a["rating"] for a in play_rated]
            free = sum(1 for a in self.play_data if a.get("isFree"))
            paid = len(self.play_data) - free
            fig, (ax3, ax4) = plt.subplots(1, 2, figsize=(14, max(3.2, len(p_names)*0.38)))
            pc = [SUCCESS if r >= 4.5 else PRIMARY if r >= 4.0 else GOLD for r in p_rat]
            ax3.barh(p_names, p_rat, color=pc, edgecolor=BG, height=0.6)
            ax3.set_xlim(0, 5.5)
            ax3.set_xlabel("Rating", fontweight="bold")
            ax3.set_title("App Ratings", fontweight="bold")
            ax3.axvline(4.0, color=BORDER, linestyle="--", linewidth=0.9, alpha=0.7)
            for i, v in enumerate(p_rat):
                ax3.text(v+0.07, i, f"{v:.1f}", va="center", fontsize=8, fontweight="bold")
            if free + paid > 0:
                w, t, at = ax4.pie([free, paid], labels=["Free", "Paid"], autopct="%1.0f%%",
                                   colors=[SUCCESS, PRIMARY], startangle=90,
                                   wedgeprops=dict(edgecolor=BG, linewidth=2))
                for a in at:
                    a.set_color(WHITE)
                    a.set_fontweight("bold")
                    a.set_fontsize(10)
            ax4.set_title("Free vs Paid", fontweight="bold")
            fig.tight_layout(pad=2.0)
            embed(fig)

        section_hdr("🛒", "Amazon Products", f"{len(self.amzn_data)} products")
        amzn_rated = []
        for p in self.amzn_data:
            try:
                rv = float(p["rating"])
            except Exception:
                rv = 0.0
            amzn_rated.append((p.get("title", "—")[:20], rv))

        if amzn_prices:
            fig_p, ax_p = plt.subplots(figsize=(13, 3.8))
            xs = list(range(1, len(amzn_prices) + 1))
            ax_p.plot(xs, amzn_prices, marker="o", color=PRIMARY, linewidth=2.2, markersize=7, zorder=3)
            ax_p.fill_between(xs, amzn_prices, alpha=0.12, color=PRIMARY)
            for x, y in zip(xs, amzn_prices):
                ax_p.annotate(f"₹{y:,.0f}", (x, y), textcoords="offset points", xytext=(0, 10),
                              ha="center", fontsize=7.5, color=TEXT, fontweight="bold")
            ax_p.set_xticks(xs)
            ax_p.set_xlabel("Product Rank", fontweight="bold")
            ax_p.set_ylabel("Price (₹)", fontweight="bold")
            ax_p.grid(True, linestyle="--", alpha=0.3)
            ax_p.set_title("Price Trend", fontweight="bold", pad=10)
            fig_p.tight_layout(pad=1.8)
            embed(fig_p)

        if amzn_rated:
            n_b = len(amzn_rated)
            fig_r, ax_r = plt.subplots(figsize=(13, max(3.0, n_b*0.38+1.2)))
            an = [t for t, _ in amzn_rated]
            av = [v for _, v in amzn_rated]
            ac = [SUCCESS if v >= 4.0 else GOLD if v >= 3.0 else DANGER for v in av]
            ys = list(range(n_b))
            ax_r.barh(ys, av, color=ac, edgecolor=BG, height=0.32)
            ax_r.set_yticks(ys)
            ax_r.set_yticklabels(an, fontsize=9)
            ax_r.set_ylim(-0.6, n_b-0.4)
            ax_r.set_xlim(0, 5.8)
            ax_r.set_xlabel("Rating", fontweight="bold")
            ax_r.axvline(4.0, color=BORDER, linestyle="--", linewidth=0.9, alpha=0.6)
            for pos, val in zip(ys, av):
                ax_r.text(val+0.08, pos, f"{val:.1f}", va="center", fontsize=8.5, fontweight="bold")
            ax_r.set_title("Product Ratings", fontweight="bold", pad=10)
            fig_r.tight_layout(pad=1.8)
            embed(fig_r)

        tk.Frame(scroll, bg=BG, height=20).pack()

    def _build_summary(self):
        for w in self.summary_inner.winfo_children():
            w.destroy()
        _, inner, _ = scrollable_frame(self.summary_inner, bg=BG)
        query = self.query_var.get().strip()

        tk.Label(inner, text=f'📈  Market Summary — "{query}"',
                 font=("Segoe UI", 15, "bold"), bg=BG, fg=WHITE, pady=14
                 ).pack(anchor="w", padx=24)

        cards = tk.Frame(inner, bg=BG)
        cards.pack(fill="x", padx=24, pady=8)
        cards.columnconfigure((0, 1, 2, 3), weight=1)

        def sc(col, icon, title, value, fg=PRIMARY, sub=None):
            f = tk.Frame(cards, bg=PANEL, padx=16, pady=16)
            f.grid(row=0, column=col, padx=6, sticky="ew")
            tk.Label(f, text=icon, font=("Segoe UI", 26), bg=PANEL).pack()
            tk.Label(f, text=value, font=("Segoe UI", 15, "bold"), bg=PANEL, fg=fg).pack()
            tk.Label(f, text=title, font=FONT_SMALL, bg=PANEL, fg=TEXT).pack()
            if sub:
                tk.Label(f, text=sub, font=FONT_TINY, bg=PANEL, fg=SUBTEXT).pack()

        sc(0, "🗺️", "Local Shops", str(len(self.maps_data)), ACCENT, "via Google Maps")
        sc(1, "📱", "Apps Found", str(len(self.play_data)), PRIMARY, "via Google Play")
        sc(2, "🛒", "Amazon Products", str(len(self.amzn_data)), GOLD, "via amazon.in")
        sc(3, "📦", "Total Results",
           str(len(self.maps_data)+len(self.play_data)+len(self.amzn_data)),
           SUCCESS, "all sources combined")

        tk.Frame(inner, bg=BORDER, height=1).pack(fill="x", padx=24, pady=(14, 0))

        def section(title, rows, highlights=()):
            sf = tk.Frame(inner, bg=PANEL, padx=18, pady=14)
            sf.pack(fill="x", padx=24, pady=8)
            tk.Label(sf, text=title, font=FONT_HEADING, bg=PANEL, fg=ACCENT).pack(anchor="w", pady=(0, 8))
            for lbl, val in rows:
                row = tk.Frame(sf, bg=PANEL)
                row.pack(fill="x", pady=2)
                tk.Label(row, text=lbl+":", font=FONT_LABEL, bg=PANEL, fg=SUBTEXT,
                         width=22, anchor="w").pack(side="left")
                tk.Label(row, text=val, font=FONT_BODY, bg=PANEL, fg=TEXT).pack(side="left")
            for hl_text, hl_fg in highlights:
                tk.Label(sf, text=hl_text, font=FONT_BODY, bg=PANEL, fg=hl_fg).pack(anchor="w", pady=2)

        if self.maps_data and self.maps_report:
            r = self.maps_report
            rated = [c for c in self.maps_data if c["rating"] > 0]
            highs = []
            if rated:
                top = max(rated, key=lambda x: x["rating"])
                pop = max(rated, key=lambda x: x["review_count"])
                highs = [
                    (f"🏆  Highest rated:  {top['name']}  ({top['rating']}/5.0)", SUCCESS),
                    (f"🔥  Most reviewed: {pop['name']}  ({pop['review_count']:,} reviews)", WARNING),
                ]
            section("🗺️  Google Maps — Local Shops", [
                ("Total shops", str(r["total"])),
                ("Avg rating", f"{r['avg_rating']}/5.0"),
                ("Total reviews", f"{r['total_reviews']:,}"),
                ("Rating range", f"{r['rating_range'][0]:.1f} - {r['rating_range'][1]:.1f}"),
            ], highs)

        if self.play_data:
            rp = [a for a in self.play_data if a.get("rating")]
            avg_r = round(sum(a["rating"] for a in rp) / len(rp), 2) if rp else 0
            free = sum(1 for a in self.play_data if a.get("isFree"))
            highs = []
            if rp:
                ta = max(rp, key=lambda x: x["rating"])
                highs = [(f"🏆  Top app:  {ta['appTitle']}  ({ta['rating']:.1f}/5.0)", SUCCESS)]
            section("📱  Google Play — App Store", [
                ("Apps found", str(len(self.play_data))),
                ("Avg rating", f"{avg_r}/5.0"),
                ("Free apps", str(free)),
                ("Paid apps", str(len(self.play_data) - free)),
            ], highs)

        if self.amzn_data:
            prices = [p["price_num"] for p in self.amzn_data if p.get("price_num")]
            section("🛒  Amazon Products", [
                ("Products found", str(len(self.amzn_data))),
                ("Price range", f"₹{min(prices):,.0f} - ₹{max(prices):,.0f}" if prices else "N/A"),
                ("Avg price", f"₹{sum(prices)/len(prices):,.0f}" if prices else "N/A"),
            ])

        ef = tk.Frame(inner, bg=BG)
        ef.pack(anchor="w", padx=24, pady=20)
        tk.Button(ef, text="💾  Export JSON", font=FONT_LABEL,
                  bg=PRIMARY, fg=WHITE, relief="flat", padx=14, pady=8,
                  cursor="hand2", activebackground=PRI_DARK,
                  command=self._export_json).pack(side="left", padx=(0, 10))

    def _export_json(self):
        if not any([self.maps_data, self.play_data, self.amzn_data]):
            messagebox.showwarning("Export", "Run a search first.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".json", filetypes=[("JSON", "*.json")],
            initialfile=f"market_research_{self.query_var.get().strip()}.json")
        if path:
            with open(path, "w", encoding="utf-8") as f:
                json.dump({
                    "timestamp": datetime.now().isoformat(),
                    "query": self.query_var.get().strip(),
                    "location": self.loc_var.get(),
                    "maps": self.maps_data,
                    "play": self.play_data,
                    "amazon": self.amzn_data,
                }, f, indent=2, ensure_ascii=False)
            messagebox.showinfo("Exported", f"Saved to:\n{path}")

    def _on_closing(self):
        try:
            plt.close("all")
        except Exception:
            pass
        self.quit()
        self.destroy()
        import os
        os._exit(0)
