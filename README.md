# Claude vs GPT

A small cross-platform GUI to send the same prompt to Anthropic (Claude) and OpenAI (GPT) and compare **token usage, cost, and latency** side by side.

- Tkinter UI (stdlib) — runs on macOS, Linux, Windows
- Pulls token counts from each provider's response (no local tokenizer drift)
- Cost computed from `prices.json`, which you can edit as pricing changes
- API keys are kept in memory only; pre-fills from `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` env vars if present

## Install

```bash
git clone https://github.com/xMKx/claude-vs-gpt
cd claude-vs-gpt
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### macOS — important

Apple's bundled `/usr/bin/python3` ships an ancient Tk 8.5 that renders parts of the UI blank on recent macOS releases. Use a Python with modern Tk 8.6 instead:

```bash
brew install python-tk@3.13   # adds tkinter to Homebrew's python3.13
python3.13 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Or install Python from <https://www.python.org/downloads/macos/> — it bundles a working Tk.

## Run

```bash
python app.py
```

Optional — pre-load keys from environment:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
export OPENAI_API_KEY=sk-...
python app.py
```

## How it works

1. You enter both API keys (or one) and pick a model from each dropdown.
2. The same prompt is sent to both providers concurrently.
3. Results table shows input/output/total tokens, cost in USD, and latency.
4. The cheaper run is highlighted with the cost ratio.

Token counts come from each API's `usage` field — they reflect what the provider actually billed for, not a local estimate.

## Pricing

`prices.json` ships with approximate per-million-token rates for common models. **Verify these against the official pricing pages before relying on them**, and edit the file whenever rates change:

- Anthropic: <https://www.anthropic.com/pricing>
- OpenAI: <https://openai.com/api/pricing>

Cache discounts, batch pricing, and image/audio modalities are not modeled.

## Adding a model

Just add it to `prices.json` under the right provider with `input` and `output` rates (USD per 1M tokens). It will appear in the dropdown next time you launch.

## Limitations

- Text prompts only (no images, no tools, no streaming).
- Single-turn — no conversation history.
- Cost is text-token cost only.
- Reasoning models (o1/o3) bill thinking tokens as output; rates apply but you may want to set a higher max-tokens.

## Contributing

PRs welcome. Keep it small — the value is in being a 5-minute install for a one-task tool.

## License

MIT — see `LICENSE`.
