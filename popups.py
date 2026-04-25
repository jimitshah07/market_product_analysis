import tkinter as tk
from tkinter import messagebox
from typing import Dict
import threading
import webbrowser
from collections import Counter
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from constants import (
    BG, PANEL, PRIMARY, ACCENT, GOLD, SUCCESS, WARNING, DANGER,
    TEXT, SUBTEXT, BORDER, WHITE, FONT_BODY, FONT_HEADING, FONT_LABEL, FONT_SMALL
)
from utils import rating_color, scrollable_frame
from fetchers import MapsDataFetcher


class MapsReviewPopup:

    def __init__(self, parent, shop: Dict):
        self.shop = shop
        self.all_reviews = list(shop.get("reviews", []))
        self.displayed_count = 0

        self.win = tk.Toplevel(parent)
        self.win.title(f"📋  {shop['name']}  —  Details & Reviews")
        self.win.geometry("860x900")
        self.win.configure(bg=PANEL)
        self.win.grab_set()
        self._build()
        if self.all_reviews:
            self._render_reviews()
        else:
            self._load_reviews()

    def _build(self):
        shop = self.shop

        hdr = tk.Frame(self.win, bg=PRIMARY, pady=16)
        hdr.pack(fill="x")
        tk.Label(hdr, text=shop["name"], font=("Segoe UI", 16, "bold"),
                 bg=PRIMARY, fg=WHITE).pack(anchor="w", padx=20)
        tk.Label(hdr, text=f"  {shop['type']}", font=FONT_BODY,
                 bg=PRIMARY, fg="#BBDEFB").pack(anchor="w", padx=20)

        card_row = tk.Frame(self.win, bg=PANEL)
        card_row.pack(fill="x", padx=16, pady=10)
        card_row.columnconfigure((0, 1, 2, 3), weight=1)

        def stat_card(col, icon, label, value, fg=PRIMARY):
            f = tk.Frame(card_row, bg=BG, padx=10, pady=10)
            f.grid(row=0, column=col, padx=5, sticky="ew")
            tk.Label(f, text=icon, font=("Segoe UI", 22), bg=BG).pack()
            tk.Label(f, text=value, font=("Segoe UI", 11, "bold"),
                     bg=BG, fg=fg, wraplength=160).pack()
            tk.Label(f, text=label, font=FONT_SMALL, bg=BG, fg=SUBTEXT).pack()

        r_color = rating_color(shop["rating"])
        stat_card(0, "⭐", "Rating", f"{shop['rating']}/5.0", r_color)
        stat_card(1, "💬", "Reviews", f"{shop['review_count']:,}", ACCENT)
        stat_card(2, "💰", "Price", shop.get("price_label", "N/A"), GOLD)
        bstatus = shop.get("business_status", "UNKNOWN")
        bs_color = SUCCESS if bstatus == "OPERATIONAL" else DANGER if bstatus == "CLOSED" else GOLD
        stat_card(3, "🏪", "Status", bstatus.replace("_", " ").title(), bs_color)

        info_frame = tk.Frame(self.win, bg=PANEL, padx=20, pady=8)
        info_frame.pack(fill="x")
        tk.Label(info_frame, text=f"📍  {shop['location']}",
                 font=FONT_BODY, fg=TEXT, bg=PANEL,
                 wraplength=780, justify="left", anchor="w").pack(fill="x")
        hours_display = shop.get("hours_display", "")
        if hours_display:
            open_now = shop.get("open_now")
            dot = "🟢" if open_now is True else "🔴" if open_now is False else "🟡"
            dot_color = SUCCESS if open_now is True else DANGER if open_now is False else GOLD
            tk.Label(info_frame, text=f"{dot}  {hours_display}",
                     font=FONT_SMALL, fg=dot_color, bg=PANEL, anchor="w").pack(fill="x", pady=(4, 0))
        if shop.get("phone"):
            tk.Label(info_frame, text=f"📞  {shop['phone']}",
                     font=FONT_SMALL, fg=SUBTEXT, bg=PANEL).pack(anchor="w", pady=(3, 0))

        btns = tk.Frame(self.win, bg=PANEL, padx=20, pady=6)
        btns.pack(fill="x")

        def btn(text, bg, cmd):
            tk.Button(btns, text=text, font=FONT_SMALL, bg=bg, fg=WHITE,
                      relief="flat", padx=12, pady=6, cursor="hand2",
                      activebackground=bg, activeforeground=WHITE,
                      command=cmd).pack(side="left", padx=(0, 8))

        btn("🗺️ Open in Maps", SUCCESS, lambda: webbrowser.open(shop["maps_link"]))
        btn("📊 View Review Graph", ACCENT, self._show_review_graph)
        if shop.get("website"):
            btn("🌐 Website", SUBTEXT, lambda: webbrowser.open(shop["website"]))

        tk.Frame(self.win, bg=BORDER, height=1).pack(fill="x", padx=16, pady=6)

        self.rev_hdr = tk.Label(self.win, text="💬  User Reviews  (loading…)",
                                font=FONT_HEADING, bg=PANEL, fg=TEXT)
        self.rev_hdr.pack(anchor="w", padx=16)

        _, self.rev_inner, _ = scrollable_frame(self.win, bg=PANEL)

    def _load_reviews(self):
        def worker():
            reviews = MapsDataFetcher.fetch_reviews(self.shop.get("place_id", ""))
            self.all_reviews = reviews
            self.shop["reviews"] = reviews
            self.win.after(0, self._render_reviews)

        threading.Thread(target=worker, daemon=True).start()

    def _render_reviews(self):
        revs = self.all_reviews
        self.rev_hdr.config(text=f"💬  User Reviews  ({len(revs)} fetched)")
        for w in self.rev_inner.winfo_children():
            w.destroy()
        if not revs:
            tk.Label(self.rev_inner, text="No reviews available.",
                     font=FONT_BODY, bg=PANEL, fg=SUBTEXT).pack(pady=20)
            return
        for r in revs:
            rating = r.get("rating", 0)
            snippet = r.get("snippet", "") or r.get("text", "")
            author = r.get("user", {}).get("name", "Anonymous") if isinstance(r.get("user"), dict) else "Anonymous"
            accent = rating_color(rating)
            outer = tk.Frame(self.rev_inner, bg=PANEL, pady=4, padx=4)
            outer.pack(fill="x")
            card = tk.Frame(outer, bg=BG)
            card.pack(fill="x")
            tk.Frame(card, bg=accent, width=5).pack(side="left", fill="y")
            body = tk.Frame(card, bg=BG, padx=12, pady=8)
            body.pack(side="left", fill="both", expand=True)
            top = tk.Frame(body, bg=BG)
            top.pack(fill="x")
            tk.Label(top, text=f"⭐ {rating}/5.0  —  {author}",
                     font=("Segoe UI", 9, "bold"), bg=BG, fg=accent).pack(side="left")
            tk.Label(body, text=snippet or "(No text)",
                     font=FONT_BODY, bg=BG, fg=TEXT,
                     wraplength=680, justify="left", anchor="w").pack(fill="x", pady=(5, 0))

    def _show_review_graph(self):
        revs = self.all_reviews
        if not revs:
            messagebox.showinfo("No Data", "No review data available yet.", parent=self.win)
            return

        stars = [int(r.get("rating", 0)) for r in revs]
        counts = Counter(stars)
        sizes = [counts.get(i, 0) for i in [5, 4, 3, 2, 1]]
        labels = ["5★", "4★", "3★", "2★", "1★"]
        colors = [SUCCESS, "#4ade80", GOLD, WARNING, DANGER]

        gw = tk.Toplevel(self.win)
        gw.title(f"📊 Review Analysis — {self.shop['name']}")
        gw.geometry("820x620")
        gw.configure(bg=BG)

        hdr = tk.Frame(gw, bg="#a855f7", pady=12)
        hdr.pack(fill="x")
        tk.Label(hdr, text=f"📊  Review Analysis  —  {self.shop['name']}",
                 font=FONT_HEADING, bg="#a855f7", fg=WHITE).pack(anchor="w", padx=16)
        tk.Label(hdr, text=f"Based on {len(revs)} fetched reviews",
                 font=FONT_SMALL, bg="#a855f7", fg="#e9d5ff").pack(anchor="w", padx=16)

        fig = Figure(figsize=(10, 5), dpi=100)
        fig.patch.set_facecolor(BG)

        ax1 = fig.add_subplot(1, 2, 1)
        ax1.set_facecolor(PANEL)
        non_zero = [(s, l, c) for s, l, c in zip(sizes, labels, colors) if s > 0]
        if non_zero:
            sz, lb, cl = zip(*non_zero)
            wedges, texts, autotexts = ax1.pie(
                sz, labels=lb, autopct="%1.1f%%", colors=cl, startangle=90,
                wedgeprops={"edgecolor": BG, "linewidth": 2}, pctdistance=0.82)
            for t in texts:
                t.set_color(TEXT)
                t.set_fontsize(9)
            for at in autotexts:
                at.set_color(WHITE)
                at.set_fontweight("bold")
                at.set_fontsize(9)
        ax1.set_title(f"Star Distribution\n({len(revs)} reviews)", color=TEXT, fontweight="bold", pad=12)

        ax2 = fig.add_subplot(1, 2, 2)
        ax2.set_facecolor(PANEL)
        bars = ax2.barh(["5 ★", "4 ★", "3 ★", "2 ★", "1 ★"], sizes, color=colors, edgecolor=BG, height=0.55)
        ax2.set_xlim(0, max(sizes) * 1.3 + 1)
        ax2.set_xlabel("Number of Reviews", color=SUBTEXT, fontweight="bold")
        ax2.set_title("Review Count per Star", color=TEXT, fontweight="bold", pad=12)
        for bar, val in zip(bars, sizes):
            if val > 0:
                ax2.text(val + max(sizes)*0.02, bar.get_y() + bar.get_height()/2,
                         str(val), va="center", color=TEXT, fontweight="bold", fontsize=10)
        ax2.spines[:].set_color(BORDER)
        ax2.grid(axis="x", linestyle="--", alpha=0.3, color=BORDER)
        fig.tight_layout(pad=2.5)

        canvas = FigureCanvasTkAgg(fig, master=gw)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=16, pady=8)


class PlayDetailPopup:

    def __init__(self, parent, comp: Dict):
        self.win = tk.Toplevel(parent)
        self.win.title(f"📱  {comp.get('appTitle', 'App')}  —  Details")
        self.win.geometry("760x800")
        self.win.configure(bg=PANEL)
        self.win.grab_set()

        hdr = tk.Frame(self.win, bg=PRIMARY, pady=14)
        hdr.pack(fill="x")
        tk.Label(hdr, text=f"📱  {comp.get('appTitle','—')}",
                 font=("Segoe UI", 15, "bold"), bg=PRIMARY, fg=WHITE).pack(anchor="w", padx=18)
        tk.Label(hdr, text=f"Genre: {comp.get('genre','—')}  ·  Installs: {comp.get('installs','—')}",
                 font=FONT_BODY, bg=PRIMARY, fg="#BBDEFB").pack(anchor="w", padx=18)

        card_row = tk.Frame(self.win, bg=PANEL)
        card_row.pack(fill="x", padx=16, pady=12)
        card_row.columnconfigure((0, 1, 2, 3), weight=1)

        def sc(col, icon, label, value, fg=PRIMARY):
            f = tk.Frame(card_row, bg=BG, padx=10, pady=10)
            f.grid(row=0, column=col, padx=4, sticky="ew")
            tk.Label(f, text=icon, font=("Segoe UI", 20), bg=BG).pack()
            tk.Label(f, text=value, font=("Segoe UI", 11, "bold"), bg=BG, fg=fg, wraplength=140).pack()
            tk.Label(f, text=label, font=FONT_SMALL, bg=BG, fg=SUBTEXT).pack()

        rating = comp.get("rating", 0)
        price_str = "Free" if comp.get("isFree") else f"₹{comp.get('price','')}"
        sc(0, "⭐", "Rating", f"{rating:.1f}/5.0", rating_color(rating))
        sc(1, "📦", "Installs", comp.get("installs", "—"), ACCENT)
        sc(2, "🎮", "Genre", comp.get("genre", "—"), GOLD)
        sc(3, "💰", "Price", price_str, SUCCESS if comp.get("isFree") else WARNING)

        tk.Frame(self.win, bg=BORDER, height=1).pack(fill="x", padx=16, pady=6)
        revs = comp.get("reviews", [])
        tk.Label(self.win, text=f"💬  User Reviews  ({len(revs)})",
                 font=FONT_HEADING, bg=PANEL, fg=TEXT).pack(anchor="w", padx=16)

        _, inner, _ = scrollable_frame(self.win, bg=PANEL)
        if not revs:
            tk.Label(inner, text="No reviews fetched.", font=FONT_BODY,
                     bg=PANEL, fg=SUBTEXT).pack(pady=20)
        else:
            for r in revs:
                score = r["score"]
                accent = rating_color(score)
                outer = tk.Frame(inner, bg=PANEL, pady=4, padx=4)
                outer.pack(fill="x")
                card = tk.Frame(outer, bg=BG)
                card.pack(fill="x")
                tk.Frame(card, bg=accent, width=5).pack(side="left", fill="y")
                body = tk.Frame(card, bg=BG, padx=12, pady=8)
                body.pack(side="left", fill="both", expand=True)
                top = tk.Frame(body, bg=BG)
                top.pack(fill="x")
                tk.Label(top, text=f"⭐ {score:.1f}/5.0",
                         font=("Segoe UI", 9, "bold"), bg=BG, fg=accent).pack(side="left")
                tk.Label(top, text=f"👍 {r['thumbsUpCount']}",
                         font=FONT_SMALL, bg=BG, fg=SUBTEXT).pack(side="right")
                tk.Label(body, text=r["content"] or "(No text)",
                         font=FONT_BODY, bg=BG, fg=TEXT,
                         wraplength=660, justify="left", anchor="w").pack(fill="x", pady=(5, 0))
