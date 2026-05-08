"""Claude vs GPT — token & cost comparison GUI (Tkinter, cross-platform)."""
from __future__ import annotations

import json
import os
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from comparator import CallResult, call_anthropic, call_openai

APP_DIR = Path(__file__).resolve().parent
PRICES_PATH = APP_DIR / "prices.json"

# Explicit palette so the app is readable in light mode, dark mode, and on
# the macOS system Python's ancient Tk 8.5 (which doesn't auto-adapt to dark
# mode). The 'clam' ttk theme is cross-platform and respects these colors.
BG = "#f5f5f5"
FG = "#1a1a1a"
MUTED = "#666666"
ACCENT = "#0a6"
ENTRY_BG = "#ffffff"
BORDER = "#bbbbbb"


def load_prices() -> dict:
    with open(PRICES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Claude vs GPT")
        self.geometry("980x780")
        self.minsize(820, 640)
        self.configure(bg=BG)

        self._init_style()

        self.prices = load_prices()
        self.anthropic_models = sorted(self.prices.get("anthropic", {}).keys())
        self.openai_models = sorted(self.prices.get("openai", {}).keys())

        self._build_ui()
        self._load_keys_from_env()

        if sys.platform == "darwin":
            self.update_idletasks()
            self.lift()
            self.attributes("-topmost", True)
            self.after(250, lambda: self.attributes("-topmost", False))

    def _init_style(self) -> None:
        style = ttk.Style(self)
        if "clam" in style.theme_names():
            style.theme_use("clam")

        style.configure(".", background=BG, foreground=FG, font=("TkDefaultFont", 11))
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground=FG)
        style.configure("Muted.TLabel", background=BG, foreground=MUTED)
        style.configure("Accent.TLabel", background=BG, foreground=ACCENT, font=("TkDefaultFont", 11, "bold"))
        style.configure("TLabelframe", background=BG, foreground=FG, bordercolor=BORDER)
        style.configure("TLabelframe.Label", background=BG, foreground=FG, font=("TkDefaultFont", 11, "bold"))
        style.configure("TEntry", fieldbackground=ENTRY_BG, foreground=FG, bordercolor=BORDER, insertcolor=FG)
        style.configure("TCombobox", fieldbackground=ENTRY_BG, foreground=FG, background=ENTRY_BG, bordercolor=BORDER, arrowcolor=FG)
        style.map("TCombobox", fieldbackground=[("readonly", ENTRY_BG)], foreground=[("readonly", FG)])
        style.configure("TCheckbutton", background=BG, foreground=FG)
        style.map("TCheckbutton", background=[("active", BG)])
        style.configure("TButton", background="#e6e6e6", foreground=FG, padding=(12, 6))
        style.map("TButton", background=[("active", "#d4d4d4")])
        style.configure("Primary.TButton", background="#3a7afe", foreground="#ffffff", padding=(14, 6))
        style.map("Primary.TButton", background=[("active", "#2e63d8")])
        style.configure("TSpinbox", fieldbackground=ENTRY_BG, foreground=FG, background=ENTRY_BG, arrowcolor=FG)
        style.configure("Treeview", background=ENTRY_BG, fieldbackground=ENTRY_BG, foreground=FG, rowheight=24, bordercolor=BORDER)
        style.configure("Treeview.Heading", background="#e8e8e8", foreground=FG, font=("TkDefaultFont", 10, "bold"))
        style.map("Treeview", background=[("selected", "#cfe1ff")], foreground=[("selected", FG)])

        # Dropdown listbox isn't a ttk widget — set its colors via option db
        self.option_add("*TCombobox*Listbox.background", ENTRY_BG)
        self.option_add("*TCombobox*Listbox.foreground", FG)
        self.option_add("*TCombobox*Listbox.selectBackground", "#3a7afe")
        self.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")

    def _build_ui(self) -> None:
        outer = ttk.Frame(self, padding=12)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)

        # --- API keys ---
        keys = ttk.LabelFrame(outer, text="  API keys  ", padding=10)
        keys.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        keys.columnconfigure(1, weight=1)

        ttk.Label(keys, text="Anthropic key:").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
        self.anthropic_key = tk.StringVar()
        self.anthropic_entry = ttk.Entry(keys, textvariable=self.anthropic_key, show="*")
        self.anthropic_entry.grid(row=0, column=1, sticky="ew", pady=4)
        self.anthropic_show = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            keys, text="show", variable=self.anthropic_show,
            command=lambda: self.anthropic_entry.config(show="" if self.anthropic_show.get() else "*"),
        ).grid(row=0, column=2, padx=(8, 0))

        ttk.Label(keys, text="OpenAI key:").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=4)
        self.openai_key = tk.StringVar()
        self.openai_entry = ttk.Entry(keys, textvariable=self.openai_key, show="*")
        self.openai_entry.grid(row=1, column=1, sticky="ew", pady=4)
        self.openai_show = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            keys, text="show", variable=self.openai_show,
            command=lambda: self.openai_entry.config(show="" if self.openai_show.get() else "*"),
        ).grid(row=1, column=2, padx=(8, 0))

        ttk.Label(
            keys,
            text="Tip: set ANTHROPIC_API_KEY / OPENAI_API_KEY env vars to auto-load on startup.",
            style="Muted.TLabel",
        ).grid(row=2, column=0, columnspan=3, sticky="w", pady=(8, 0))

        # --- Models ---
        models = ttk.LabelFrame(outer, text="  Models  ", padding=10)
        models.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        models.columnconfigure(1, weight=1)
        models.columnconfigure(3, weight=1)

        ttk.Label(models, text="Anthropic:").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
        self.anthropic_model = tk.StringVar(
            value="claude-sonnet-4-6" if "claude-sonnet-4-6" in self.anthropic_models
            else (self.anthropic_models[0] if self.anthropic_models else "")
        )
        ttk.Combobox(
            models, textvariable=self.anthropic_model, values=self.anthropic_models, state="readonly",
        ).grid(row=0, column=1, sticky="ew", pady=4, padx=(0, 16))

        ttk.Label(models, text="OpenAI:").grid(row=0, column=2, sticky="w", padx=(0, 8), pady=4)
        self.openai_model = tk.StringVar(
            value="gpt-5.4" if "gpt-5.4" in self.openai_models
            else (self.openai_models[0] if self.openai_models else "")
        )
        ttk.Combobox(
            models, textvariable=self.openai_model, values=self.openai_models, state="readonly",
        ).grid(row=0, column=3, sticky="ew", pady=4)

        ttk.Label(models, text="Max output tokens:").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=(8, 4))
        self.max_tokens = tk.IntVar(value=1024)
        ttk.Spinbox(
            models, from_=16, to=8192, increment=64, textvariable=self.max_tokens, width=10,
        ).grid(row=1, column=1, sticky="w", pady=(8, 4))

        # --- Prompt ---
        prompt_frame = ttk.LabelFrame(outer, text="  Prompt  ", padding=10)
        prompt_frame.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        prompt_frame.columnconfigure(0, weight=1)
        self.prompt = tk.Text(
            prompt_frame, height=7, wrap="word",
            bg=ENTRY_BG, fg=FG, insertbackground=FG,
            relief="solid", borderwidth=1, highlightthickness=0,
        )
        self.prompt.grid(row=0, column=0, sticky="ew")

        # --- Action bar ---
        actions = ttk.Frame(outer)
        actions.grid(row=3, column=0, sticky="ew", pady=(0, 10))
        self.run_btn = ttk.Button(actions, text="Run comparison", command=self.on_run, style="Primary.TButton")
        self.run_btn.pack(side="left")
        ttk.Button(actions, text="Clear", command=self.clear_results).pack(side="left", padx=8)
        self.status = ttk.Label(actions, text="", style="Muted.TLabel")
        self.status.pack(side="left", padx=12)

        # --- Results ---
        results = ttk.LabelFrame(outer, text="  Results  ", padding=10)
        results.grid(row=4, column=0, sticky="nsew")
        outer.rowconfigure(4, weight=1)
        results.columnconfigure(0, weight=1)
        results.rowconfigure(2, weight=1)

        cols = ("model", "in", "out", "total", "cost", "latency")
        self.tree = ttk.Treeview(results, columns=cols, show="headings", height=4)
        for c, label, w, anchor in [
            ("model", "Model", 320, "w"),
            ("in", "Input tokens", 110, "center"),
            ("out", "Output tokens", 110, "center"),
            ("total", "Total tokens", 110, "center"),
            ("cost", "Cost (USD)", 130, "e"),
            ("latency", "Latency (s)", 110, "e"),
        ]:
            self.tree.heading(c, text=label)
            self.tree.column(c, width=w, anchor=anchor)
        self.tree.grid(row=0, column=0, sticky="ew")

        self.diff_label = ttk.Label(results, text="", style="Accent.TLabel")
        self.diff_label.grid(row=1, column=0, sticky="w", pady=(8, 6))

        responses = ttk.Frame(results)
        responses.grid(row=2, column=0, sticky="nsew")
        responses.columnconfigure(0, weight=1)
        responses.columnconfigure(1, weight=1)
        responses.rowconfigure(0, weight=1)

        anth_box = ttk.LabelFrame(responses, text="  Anthropic response  ", padding=6)
        anth_box.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        anth_box.columnconfigure(0, weight=1)
        anth_box.rowconfigure(0, weight=1)
        self.anthropic_out = tk.Text(
            anth_box, wrap="word", height=8,
            bg=ENTRY_BG, fg=FG, insertbackground=FG,
            relief="solid", borderwidth=1, highlightthickness=0,
        )
        self.anthropic_out.grid(row=0, column=0, sticky="nsew")

        oai_box = ttk.LabelFrame(responses, text="  OpenAI response  ", padding=6)
        oai_box.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        oai_box.columnconfigure(0, weight=1)
        oai_box.rowconfigure(0, weight=1)
        self.openai_out = tk.Text(
            oai_box, wrap="word", height=8,
            bg=ENTRY_BG, fg=FG, insertbackground=FG,
            relief="solid", borderwidth=1, highlightthickness=0,
        )
        self.openai_out.grid(row=0, column=0, sticky="nsew")

    def _load_keys_from_env(self) -> None:
        if v := os.environ.get("ANTHROPIC_API_KEY"):
            self.anthropic_key.set(v)
        if v := os.environ.get("OPENAI_API_KEY"):
            self.openai_key.set(v)

    def clear_results(self) -> None:
        for row in self.tree.get_children():
            self.tree.delete(row)
        self.anthropic_out.delete("1.0", "end")
        self.openai_out.delete("1.0", "end")
        self.diff_label.config(text="")
        self.status.config(text="")

    def on_run(self) -> None:
        prompt = self.prompt.get("1.0", "end").strip()
        if not prompt:
            messagebox.showwarning("Empty prompt", "Please enter a prompt first.")
            return
        ak, ok = self.anthropic_key.get().strip(), self.openai_key.get().strip()
        if not ak and not ok:
            messagebox.showwarning("No keys", "Provide at least one API key.")
            return

        self.clear_results()
        self.run_btn.config(state="disabled")
        self.status.config(text="Calling APIs in parallel…")

        results: dict[str, CallResult] = {}
        threads = []

        def runner(name: str, fn, *args):
            results[name] = fn(*args)

        if ak:
            threads.append(threading.Thread(
                target=runner,
                args=("anthropic", call_anthropic, ak, self.anthropic_model.get(), prompt, self.max_tokens.get(), self.prices),
                daemon=True,
            ))
        if ok:
            threads.append(threading.Thread(
                target=runner,
                args=("openai", call_openai, ok, self.openai_model.get(), prompt, self.max_tokens.get(), self.prices),
                daemon=True,
            ))
        for t in threads:
            t.start()
        self._poll(threads, results)

    def _poll(self, threads: list[threading.Thread], results: dict[str, CallResult]) -> None:
        if any(t.is_alive() for t in threads):
            self.after(100, self._poll, threads, results)
            return
        self._render(results)
        self.run_btn.config(state="normal")
        self.status.config(text="Done.")

    def _render(self, results: dict[str, CallResult]) -> None:
        for name in ("anthropic", "openai"):
            r = results.get(name)
            if not r:
                continue
            if r.error:
                self.tree.insert("", "end", values=(f"{name}/{r.model}", "—", "—", "—", "—", f"{r.latency_s:.2f}"))
                box = self.anthropic_out if name == "anthropic" else self.openai_out
                box.insert("end", f"[ERROR] {r.error}\n")
                continue
            self.tree.insert("", "end", values=(
                f"{name}/{r.model}",
                r.input_tokens,
                r.output_tokens,
                r.input_tokens + r.output_tokens,
                f"${r.cost_usd:.6f}",
                f"{r.latency_s:.2f}",
            ))
            box = self.anthropic_out if name == "anthropic" else self.openai_out
            box.insert("end", r.response_text)

        a, o = results.get("anthropic"), results.get("openai")
        if a and o and not a.error and not o.error:
            cheaper, dearer = (a, o) if a.cost_usd <= o.cost_usd else (o, a)
            if dearer.cost_usd > 0 and cheaper.cost_usd > 0:
                ratio = dearer.cost_usd / cheaper.cost_usd
                self.diff_label.config(
                    text=f"{cheaper.provider}/{cheaper.model} was cheaper by ${dearer.cost_usd - cheaper.cost_usd:.6f}  ({ratio:.2f}× ratio)"
                )


def main() -> None:
    App().mainloop()


if __name__ == "__main__":
    main()
