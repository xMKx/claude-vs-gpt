"""Claude vs GPT — token & cost comparison GUI (Tkinter, cross-platform)."""
from __future__ import annotations

import json
import os
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from comparator import CallResult, call_anthropic, call_openai

APP_DIR = Path(__file__).resolve().parent
PRICES_PATH = APP_DIR / "prices.json"


def load_prices() -> dict:
    with open(PRICES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Claude vs GPT")
        self.geometry("900x720")
        self.minsize(720, 600)

        self.prices = load_prices()
        self.anthropic_models = sorted(self.prices.get("anthropic", {}).keys())
        self.openai_models = sorted(self.prices.get("openai", {}).keys())

        self._build_ui()
        self._load_keys_from_env()

    def _build_ui(self) -> None:
        pad = {"padx": 8, "pady": 4}

        keys = ttk.LabelFrame(self, text="API keys")
        keys.pack(fill="x", **pad)

        ttk.Label(keys, text="Anthropic:").grid(row=0, column=0, sticky="w", padx=6, pady=4)
        self.anthropic_key = tk.StringVar()
        self.anthropic_entry = ttk.Entry(keys, textvariable=self.anthropic_key, show="*", width=60)
        self.anthropic_entry.grid(row=0, column=1, sticky="ew", padx=6, pady=4)
        self.anthropic_show = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            keys, text="show", variable=self.anthropic_show,
            command=lambda: self.anthropic_entry.config(show="" if self.anthropic_show.get() else "*"),
        ).grid(row=0, column=2, padx=6)

        ttk.Label(keys, text="OpenAI:").grid(row=1, column=0, sticky="w", padx=6, pady=4)
        self.openai_key = tk.StringVar()
        self.openai_entry = ttk.Entry(keys, textvariable=self.openai_key, show="*", width=60)
        self.openai_entry.grid(row=1, column=1, sticky="ew", padx=6, pady=4)
        self.openai_show = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            keys, text="show", variable=self.openai_show,
            command=lambda: self.openai_entry.config(show="" if self.openai_show.get() else "*"),
        ).grid(row=1, column=2, padx=6)

        ttk.Label(
            keys, text="Tip: set ANTHROPIC_API_KEY / OPENAI_API_KEY env vars to auto-load.",
            foreground="#666",
        ).grid(row=2, column=0, columnspan=3, sticky="w", padx=6, pady=(0, 4))
        keys.columnconfigure(1, weight=1)

        models = ttk.LabelFrame(self, text="Models")
        models.pack(fill="x", **pad)
        ttk.Label(models, text="Anthropic model:").grid(row=0, column=0, sticky="w", padx=6, pady=4)
        self.anthropic_model = tk.StringVar(
            value="claude-sonnet-4-6" if "claude-sonnet-4-6" in self.anthropic_models else (self.anthropic_models[0] if self.anthropic_models else "")
        )
        ttk.Combobox(models, textvariable=self.anthropic_model, values=self.anthropic_models, width=40, state="readonly").grid(row=0, column=1, sticky="w", padx=6, pady=4)

        ttk.Label(models, text="OpenAI model:").grid(row=1, column=0, sticky="w", padx=6, pady=4)
        self.openai_model = tk.StringVar(
            value="gpt-4o" if "gpt-4o" in self.openai_models else (self.openai_models[0] if self.openai_models else "")
        )
        ttk.Combobox(models, textvariable=self.openai_model, values=self.openai_models, width=40, state="readonly").grid(row=1, column=1, sticky="w", padx=6, pady=4)

        ttk.Label(models, text="Max output tokens:").grid(row=2, column=0, sticky="w", padx=6, pady=4)
        self.max_tokens = tk.IntVar(value=1024)
        ttk.Spinbox(models, from_=16, to=8192, increment=64, textvariable=self.max_tokens, width=10).grid(row=2, column=1, sticky="w", padx=6, pady=4)

        prompt_frame = ttk.LabelFrame(self, text="Prompt")
        prompt_frame.pack(fill="both", expand=False, **pad)
        self.prompt = tk.Text(prompt_frame, height=8, wrap="word")
        self.prompt.pack(fill="both", expand=True, padx=6, pady=6)

        actions = ttk.Frame(self)
        actions.pack(fill="x", **pad)
        self.run_btn = ttk.Button(actions, text="Run comparison", command=self.on_run)
        self.run_btn.pack(side="left")
        ttk.Button(actions, text="Clear results", command=self.clear_results).pack(side="left", padx=8)
        self.status = ttk.Label(actions, text="", foreground="#444")
        self.status.pack(side="left", padx=12)

        results = ttk.LabelFrame(self, text="Results")
        results.pack(fill="both", expand=True, **pad)

        cols = ("model", "in", "out", "total", "cost", "latency")
        self.tree = ttk.Treeview(results, columns=cols, show="headings", height=4)
        for c, label, w in [
            ("model", "Model", 240),
            ("in", "Input tokens", 110),
            ("out", "Output tokens", 110),
            ("total", "Total tokens", 110),
            ("cost", "Cost (USD)", 110),
            ("latency", "Latency (s)", 110),
        ]:
            self.tree.heading(c, text=label)
            self.tree.column(c, width=w, anchor="center")
        self.tree.pack(fill="x", padx=6, pady=6)

        self.diff_label = ttk.Label(results, text="", foreground="#0a6")
        self.diff_label.pack(anchor="w", padx=8)

        responses = ttk.Frame(results)
        responses.pack(fill="both", expand=True, padx=6, pady=6)

        anth_box = ttk.LabelFrame(responses, text="Anthropic response")
        anth_box.pack(side="left", fill="both", expand=True, padx=(0, 4))
        self.anthropic_out = tk.Text(anth_box, wrap="word", height=10)
        self.anthropic_out.pack(fill="both", expand=True, padx=4, pady=4)

        oai_box = ttk.LabelFrame(responses, text="OpenAI response")
        oai_box.pack(side="right", fill="both", expand=True, padx=(4, 0))
        self.openai_out = tk.Text(oai_box, wrap="word", height=10)
        self.openai_out.pack(fill="both", expand=True, padx=4, pady=4)

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
                target=runner, args=("anthropic", call_anthropic, ak, self.anthropic_model.get(), prompt, self.max_tokens.get(), self.prices),
                daemon=True,
            ))
        if ok:
            threads.append(threading.Thread(
                target=runner, args=("openai", call_openai, ok, self.openai_model.get(), prompt, self.max_tokens.get(), self.prices),
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
            if dearer.cost_usd > 0:
                ratio = dearer.cost_usd / cheaper.cost_usd if cheaper.cost_usd > 0 else float("inf")
                self.diff_label.config(
                    text=f"{cheaper.provider}/{cheaper.model} was cheaper by ${dearer.cost_usd - cheaper.cost_usd:.6f} ({ratio:.2f}× ratio)."
                )


def main() -> None:
    App().mainloop()


if __name__ == "__main__":
    main()
