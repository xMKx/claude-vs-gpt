"""Claude vs GPT — token & cost comparison GUI (Tkinter, cross-platform)."""
from __future__ import annotations

import os

# Must be set before tkinter is imported. Suppresses the cosmetic
# "system version of Tk is deprecated" warning on macOS.
os.environ.setdefault("TK_SILENCE_DEPRECATION", "1")

import json
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

from comparator import CallResult, call_anthropic, call_openai

APP_DIR = Path(__file__).resolve().parent
PRICES_PATH = APP_DIR / "prices.json"

# Explicit palette so the UI is visible regardless of OS theme.
# macOS system Python (Tk 8.5) doesn't auto-adapt to dark mode and ttk widgets
# can render blank under the Aqua theme — so we use plain tk widgets and force
# every color, font, and border explicitly.
BG = "#f5f5f5"
PANEL = "#ffffff"
FG = "#1a1a1a"
MUTED = "#666666"
ACCENT = "#0a6f3a"
ENTRY_BG = "#ffffff"
BORDER = "#bbbbbb"
HEADER_BG = "#e2e6ea"
PRIMARY = "#3a7afe"
PRIMARY_FG = "#ffffff"

FONT = ("TkDefaultFont", 12)
FONT_BOLD = ("TkDefaultFont", 12, "bold")
FONT_SMALL = ("TkDefaultFont", 10)


def load_prices() -> dict:
    with open(PRICES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def lf(parent, title: str) -> tk.LabelFrame:
    return tk.LabelFrame(
        parent, text=f"  {title}  ",
        bg=BG, fg=FG, font=FONT_BOLD,
        bd=1, relief="solid", padx=12, pady=10,
        labelanchor="nw",
    )


def lbl(parent, text: str, *, muted: bool = False, bold: bool = False, fg: str | None = None) -> tk.Label:
    color = fg if fg is not None else (MUTED if muted else FG)
    return tk.Label(parent, text=text, bg=BG, fg=color, font=FONT_BOLD if bold else FONT)


def entry(parent, var: tk.Variable, *, show: str | None = None) -> tk.Entry:
    e = tk.Entry(
        parent, textvariable=var,
        bg=ENTRY_BG, fg=FG, insertbackground=FG,
        font=FONT, bd=1, relief="solid", highlightthickness=0,
    )
    if show is not None:
        e.config(show=show)
    return e


def btn(parent, text: str, command, *, primary: bool = False) -> tk.Button:
    if primary:
        return tk.Button(
            parent, text=text, command=command,
            bg=PRIMARY, fg=PRIMARY_FG,
            activebackground="#2e63d8", activeforeground=PRIMARY_FG,
            font=FONT_BOLD, padx=14, pady=6, bd=0,
            highlightbackground=PRIMARY, highlightthickness=0,
        )
    return tk.Button(
        parent, text=text, command=command,
        bg="#e6e6e6", fg=FG,
        activebackground="#d4d4d4", activeforeground=FG,
        font=FONT, padx=12, pady=6, bd=0,
        highlightbackground="#e6e6e6", highlightthickness=0,
    )


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Claude vs GPT")
        self.geometry("1000x800")
        self.minsize(840, 660)
        self.configure(bg=BG)

        self.prices = load_prices()
        self.anthropic_models = sorted(self.prices.get("anthropic", {}).keys())
        self.openai_models = sorted(self.prices.get("openai", {}).keys())

        self._result_rows: list[list[tk.Label]] = []

        self._build_ui()
        self._load_keys_from_env()

        if sys.platform == "darwin":
            self.update_idletasks()
            self.lift()
            self.attributes("-topmost", True)
            self.after(250, lambda: self.attributes("-topmost", False))

    def _build_ui(self) -> None:
        outer = tk.Frame(self, bg=BG, padx=14, pady=14)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)

        # --- API keys ---
        keys = lf(outer, "API keys")
        keys.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        keys.columnconfigure(1, weight=1)

        lbl(keys, "Anthropic key:").grid(row=0, column=0, sticky="w", padx=(0, 10), pady=5)
        self.anthropic_key = tk.StringVar()
        self.anthropic_entry = entry(keys, self.anthropic_key, show="*")
        self.anthropic_entry.grid(row=0, column=1, sticky="ew", pady=5, ipady=4)
        self.anthropic_show = tk.BooleanVar(value=False)
        tk.Checkbutton(
            keys, text="show", variable=self.anthropic_show,
            bg=BG, fg=FG, activebackground=BG, activeforeground=FG,
            selectcolor=PANEL, font=FONT,
            command=lambda: self.anthropic_entry.config(show="" if self.anthropic_show.get() else "*"),
        ).grid(row=0, column=2, padx=(10, 0))

        lbl(keys, "OpenAI key:").grid(row=1, column=0, sticky="w", padx=(0, 10), pady=5)
        self.openai_key = tk.StringVar()
        self.openai_entry = entry(keys, self.openai_key, show="*")
        self.openai_entry.grid(row=1, column=1, sticky="ew", pady=5, ipady=4)
        self.openai_show = tk.BooleanVar(value=False)
        tk.Checkbutton(
            keys, text="show", variable=self.openai_show,
            bg=BG, fg=FG, activebackground=BG, activeforeground=FG,
            selectcolor=PANEL, font=FONT,
            command=lambda: self.openai_entry.config(show="" if self.openai_show.get() else "*"),
        ).grid(row=1, column=2, padx=(10, 0))

        lbl(keys, "Tip: set ANTHROPIC_API_KEY / OPENAI_API_KEY env vars to auto-load on startup.",
            muted=True).grid(row=2, column=0, columnspan=3, sticky="w", pady=(8, 0))

        # --- Models ---
        models = lf(outer, "Models")
        models.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        models.columnconfigure(1, weight=1)
        models.columnconfigure(3, weight=1)

        lbl(models, "Anthropic:").grid(row=0, column=0, sticky="w", padx=(0, 10), pady=5)
        self.anthropic_model = tk.StringVar(
            value="claude-sonnet-4-6" if "claude-sonnet-4-6" in self.anthropic_models
            else (self.anthropic_models[0] if self.anthropic_models else "")
        )
        self._option_menu(models, self.anthropic_model, self.anthropic_models).grid(
            row=0, column=1, sticky="ew", pady=5, padx=(0, 20)
        )

        lbl(models, "OpenAI:").grid(row=0, column=2, sticky="w", padx=(0, 10), pady=5)
        self.openai_model = tk.StringVar(
            value="gpt-5.4" if "gpt-5.4" in self.openai_models
            else (self.openai_models[0] if self.openai_models else "")
        )
        self._option_menu(models, self.openai_model, self.openai_models).grid(
            row=0, column=3, sticky="ew", pady=5
        )

        lbl(models, "Max output tokens:").grid(row=1, column=0, sticky="w", padx=(0, 10), pady=(8, 5))
        self.max_tokens = tk.IntVar(value=1024)
        tk.Spinbox(
            models, from_=16, to=8192, increment=64, textvariable=self.max_tokens,
            bg=ENTRY_BG, fg=FG, font=FONT, width=10,
            buttonbackground="#e6e6e6", relief="solid", bd=1, highlightthickness=0,
        ).grid(row=1, column=1, sticky="w", pady=(8, 5))

        # --- Prompt ---
        prompt_frame = lf(outer, "Prompt")
        prompt_frame.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        prompt_frame.columnconfigure(0, weight=1)
        self.prompt = tk.Text(
            prompt_frame, height=7, wrap="word", font=FONT,
            bg=ENTRY_BG, fg=FG, insertbackground=FG,
            relief="solid", bd=1, highlightthickness=0,
        )
        self.prompt.grid(row=0, column=0, sticky="ew")

        # --- Action bar ---
        actions = tk.Frame(outer, bg=BG)
        actions.grid(row=3, column=0, sticky="ew", pady=(0, 10))
        self.run_btn = btn(actions, "Run comparison", self.on_run, primary=True)
        self.run_btn.pack(side="left")
        btn(actions, "Clear", self.clear_results).pack(side="left", padx=10)
        self.status = lbl(actions, "", muted=True)
        self.status.pack(side="left", padx=12)

        # --- Results ---
        results = lf(outer, "Results")
        results.grid(row=4, column=0, sticky="nsew")
        outer.rowconfigure(4, weight=1)
        results.columnconfigure(0, weight=1)
        results.rowconfigure(2, weight=1)

        # Manual table (label grid) since ttk.Treeview doesn't render reliably
        # on macOS system Python. Header + dynamic rows.
        self._table = tk.Frame(results, bg=BORDER)  # border color shows as cell separator
        self._table.grid(row=0, column=0, sticky="ew")
        for i in range(6):
            self._table.columnconfigure(i, weight=1, uniform="cols")

        headers = ["Model", "Input tokens", "Output tokens", "Total tokens", "Cost (USD)", "Latency (s)"]
        for i, h in enumerate(headers):
            tk.Label(
                self._table, text=h, bg=HEADER_BG, fg=FG, font=FONT_BOLD,
                padx=10, pady=6, anchor="center",
            ).grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 1), pady=(0, 1))

        self.diff_label = lbl(results, "", fg=ACCENT, bold=True)
        self.diff_label.grid(row=1, column=0, sticky="w", pady=(10, 8))

        responses = tk.Frame(results, bg=BG)
        responses.grid(row=2, column=0, sticky="nsew")
        responses.columnconfigure(0, weight=1)
        responses.columnconfigure(1, weight=1)
        responses.rowconfigure(0, weight=1)

        anth_box = lf(responses, "Anthropic response")
        anth_box.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        anth_box.columnconfigure(0, weight=1)
        anth_box.rowconfigure(0, weight=1)
        self.anthropic_out = tk.Text(
            anth_box, wrap="word", height=8, font=FONT,
            bg=ENTRY_BG, fg=FG, insertbackground=FG,
            relief="solid", bd=1, highlightthickness=0,
        )
        self.anthropic_out.grid(row=0, column=0, sticky="nsew")

        oai_box = lf(responses, "OpenAI response")
        oai_box.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        oai_box.columnconfigure(0, weight=1)
        oai_box.rowconfigure(0, weight=1)
        self.openai_out = tk.Text(
            oai_box, wrap="word", height=8, font=FONT,
            bg=ENTRY_BG, fg=FG, insertbackground=FG,
            relief="solid", bd=1, highlightthickness=0,
        )
        self.openai_out.grid(row=0, column=0, sticky="nsew")

    def _option_menu(self, parent, var: tk.StringVar, values: list[str]) -> tk.OptionMenu:
        if not values:
            values = [""]
        om = tk.OptionMenu(parent, var, *values)
        om.config(
            bg=ENTRY_BG, fg=FG, activebackground="#e6e6e6", activeforeground=FG,
            font=FONT, bd=1, relief="solid", highlightthickness=0,
            anchor="w", padx=8, pady=4,
        )
        om["menu"].config(bg=ENTRY_BG, fg=FG, font=FONT)
        return om

    def _add_result_row(self, values: tuple) -> None:
        row_idx = len(self._result_rows) + 1
        cells = []
        for i, v in enumerate(values):
            anchor = "w" if i == 0 else "center"
            cell = tk.Label(
                self._table, text=str(v), bg=PANEL, fg=FG, font=FONT,
                padx=10, pady=6, anchor=anchor,
            )
            cell.grid(row=row_idx, column=i, sticky="nsew", padx=(0 if i == 0 else 1), pady=(0, 1))
            cells.append(cell)
        self._result_rows.append(cells)

    def _clear_table(self) -> None:
        for row in self._result_rows:
            for cell in row:
                cell.destroy()
        self._result_rows = []

    def _load_keys_from_env(self) -> None:
        if v := os.environ.get("ANTHROPIC_API_KEY"):
            self.anthropic_key.set(v)
        if v := os.environ.get("OPENAI_API_KEY"):
            self.openai_key.set(v)

    def clear_results(self) -> None:
        self._clear_table()
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
                self._add_result_row((f"{name}/{r.model}", "—", "—", "—", "—", f"{r.latency_s:.2f}"))
                box = self.anthropic_out if name == "anthropic" else self.openai_out
                box.insert("end", f"[ERROR] {r.error}\n")
                continue
            self._add_result_row((
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
