# Getting Started

A 5-minute walkthrough to get the Adaptive Statistics Tutor running on your machine.

> **TL;DR**
> ```bash
> git clone https://github.com/jean-claude-bogdan/adaptive-stats-tutor.git
> cd adaptive-stats-tutor
> pip install -r requirements-dev.txt
> cp .env.example .env       # edit, paste your ANTHROPIC_API_KEY
> pytest                     # 84 tests, ~5s
> python -m src.app          # open http://localhost:8000
> ```

---

## 1. Prerequisites

| Tool | Version | How to check |
|------|---------|--------------|
| **Python** | 3.11 or newer | `python --version` |
| **pip** | any recent | `pip --version` |
| **git** | any recent | `git --version` |
| **Anthropic API key** | from [console.anthropic.com](https://console.anthropic.com/) | — |

> Windows? PowerShell or Git Bash both work. On macOS/Linux, use your normal terminal.

## 2. Clone the repo

```bash
git clone https://github.com/jean-claude-bogdan/adaptive-stats-tutor.git
cd adaptive-stats-tutor
```

## 3. (Recommended) Create a virtual environment

```bash
# macOS / Linux
python -m venv .venv
source .venv/bin/activate

# Windows (PowerShell)
python -m venv .venv
.venv\Scripts\Activate.ps1
```

## 4. Install dependencies

For everyday use:

```bash
pip install -r requirements.txt
```

For development (adds pytest, mypy, ruff):

```bash
pip install -r requirements-dev.txt
```

## 5. Configure your API key

```bash
cp .env.example .env
```

Open `.env` in any editor and paste your key:

```
ANTHROPIC_API_KEY=sk-ant-...
```

> The server will still run without a key — it just returns a safe fallback message ("I'm having a little trouble right now…") instead of real Claude output. Tests work fully offline.

## 6. Verify everything works

```bash
pytest
```

You should see something like:

```
============================= 84 passed in 5.00s ==============================
```

If anything fails, see [Troubleshooting](#troubleshooting) below.

## 7. Run the web app

```bash
python -m src.app
```

You'll see:

```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

Open **http://localhost:8000/** in your browser. You should see the chat UI with the six knowledge components across the top.

Try this 60-second arc:

1. Read the first tutor message
2. Click **"Got it"**
3. The tutor asks a question — type a deliberately wrong answer (e.g. `nope`) and click **Submit Answer**
4. The tutor re-explains. A confidence slider appears.
5. Rate your understanding 0–10 and click **Rate & continue**
6. The tutor asks another question — try the correct answer this time

Watch the **mastery percentages** at the top update as you go.

## 8. (Optional) Run the CLI demo instead

The same flow without a browser:

```bash
python -m src.demo --learner alice
```

Type answers at the prompts. Add `-v` for verbose logging.

## 9. Useful follow-up commands

```bash
pytest -v                       # show every test name
pytest tests/test_policy.py     # run a single test file
ruff check src/ tests/          # lint
mypy src/ canvas_stub.py        # strict type-check
```

---

## Troubleshooting

**`ModuleNotFoundError: No module named 'src'`**
You're not in the repo root. Run `cd adaptive-stats-tutor` first.

**`Error: ANTHROPIC_API_KEY is not set`**
The CLI demo requires the key. Make sure `.env` exists and contains a valid key, or pass it inline:
```bash
ANTHROPIC_API_KEY=sk-ant-... python -m src.demo
```

**Port 8000 already in use**
```bash
python -m uvicorn src.app:app --port 8765
```
Then open `http://localhost:8765/`.

**Tests fail right after install on Windows**
Make sure your Python version is **3.11 or newer**. The codebase uses 3.11+ syntax (`StrEnum`, `X | None` unions).

**Chat UI loads but says "Could not connect to the tutor server"**
The browser opened a stale tab from before the server started. Refresh the page.

---

## What's next?

- Read [`README.md`](README.md) for architecture, policy priorities, and scaling notes.
- Read [`docs/TWO_PAGER.md`](docs/TWO_PAGER.md) for the product strategy in two pages.
- Browse [`src/content/items.json`](src/content/items.json) — 56 statistics questions across 6 knowledge components.
- Look at [`src/policy.py`](src/policy.py) — every adaptation decision is one of 7 priority rules in ~150 lines.
