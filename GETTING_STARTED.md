# Getting Started

A 5-minute walkthrough to get the Adaptive Statistics Tutor running on your machine.

> **Quick version**
> ```bash
> git clone https://github.com/jean-claude-bogdan/adaptive-stats-tutor.git
> cd adaptive-stats-tutor
> pip install -r requirements-dev.txt
> cp .env.example .env       # edit, paste your ANTHROPIC_API_KEY
> pytest                     # should show 84 tests passing in about 5 seconds
> python -m src.app          # open http://localhost:8000 in your browser
> ```

---

## 1. What you need first

| Tool | Version | How to check it's installed |
|------|---------|--------------|
| **Python** | 3.11 or newer | `python --version` |
| **pip** (Python package installer) | any recent | `pip --version` |
| **git** | any recent | `git --version` |
| **Anthropic API key** | get one at [console.anthropic.com](https://console.anthropic.com/) | — |

> Windows? PowerShell or Git Bash both work. On macOS or Linux, use your normal terminal.

## 2. Download the project

```bash
git clone https://github.com/jean-claude-bogdan/adaptive-stats-tutor.git
cd adaptive-stats-tutor
```

## 3. (Recommended) Create an isolated Python environment

This keeps the project's libraries from interfering with anything else on your machine.

```bash
# macOS / Linux
python -m venv .venv
source .venv/bin/activate

# Windows (PowerShell)
python -m venv .venv
.venv\Scripts\Activate.ps1
```

## 4. Install the libraries

For just running the project:

```bash
pip install -r requirements.txt
```

For working on the code (adds tools for testing, type-checking, and code-style checks):

```bash
pip install -r requirements-dev.txt
```

## 5. Add your Anthropic API key

```bash
cp .env.example .env
```

Open `.env` in any text editor and paste your key:

```
ANTHROPIC_API_KEY=sk-ant-...
```

> The server will still run without a key — it just shows a safe backup message ("I'm having a little trouble right now…") instead of real Claude output. The tests work fully offline so they don't need a key either.

## 6. Check everything works

```bash
pytest
```

You should see something like:

```
============================= 84 passed in 5.00s ==============================
```

If anything fails, see [Troubleshooting](#troubleshooting) at the bottom.

## 7. Run the web app

```bash
python -m src.app
```

You'll see:

```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

Open **http://localhost:8000/** in your browser. You should see the chat interface with six topic chips across the top.

Try this 60-second walkthrough:

1. Read the first tutor message
2. Click **"Got it"**
3. The tutor asks a question — type a deliberately wrong answer (e.g. `nope`) and click **Submit Answer**
4. The tutor re-explains. A confidence slider appears.
5. Rate your understanding 0–10 and click **Rate & continue**
6. The tutor asks another question — try the correct answer this time

Watch the **percentage** next to each topic at the top update as you go.

## 8. (Optional) Run the command-line demo instead

Same flow, no browser:

```bash
python -m src.demo --learner alice
```

Type answers at the prompts. Add `-v` for verbose output.

## 9. Other useful commands

```bash
pytest -v                       # show every test name
pytest tests/test_policy.py     # run a single test file
ruff check src/ tests/          # check code style
mypy src/ canvas_stub.py        # check types
```

---

## Troubleshooting

**`ModuleNotFoundError: No module named 'src'`**
You're not in the project folder. Run `cd adaptive-stats-tutor` first.

**`Error: ANTHROPIC_API_KEY is not set`**
The command-line demo requires the key. Make sure `.env` exists and contains a valid key, or pass it on the command line:
```bash
ANTHROPIC_API_KEY=sk-ant-... python -m src.demo
```

**Port 8000 already in use**
```bash
python -m uvicorn src.app:app --port 8765
```
Then open `http://localhost:8765/`.

**Tests fail right after install on Windows**
Make sure your Python is **3.11 or newer**. The code uses features from Python 3.11+.

**Chat interface loads but says "Could not connect to the tutor server"**
The browser is showing a stale tab from before the server started. Refresh the page.

---

## What's next?

- Read [`README.md`](README.md) for how the whole system fits together and how it's designed to scale.
- Read [`docs/TWO_PAGER.md`](docs/TWO_PAGER.md) for the product strategy in two pages.
- Browse [`src/content/items.json`](src/content/items.json) — 56 statistics questions across 6 topics, each with notes on common student mistakes.
- Read [`src/policy.py`](src/policy.py) — every adaptation decision the tutor makes is one of 7 rules in about 150 lines.
