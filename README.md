# Adaptive Statistics Tutor

A one-on-one tutor for college-level introductory statistics, powered by Anthropic's Claude AI. It walks each student through six topics — averages, variance, z-scores, sampling distributions, standard error, and confidence intervals — and adjusts in real time based on what they get right, what they get wrong, and how confident they say they are.

## How it's different from a typical AI tutor

Every teaching decision — when to re-explain, when to switch to a worked example, when to move to the next topic — is made by plain Python code, not by the AI. The AI only writes the actual explanations and feedback the student reads. This means every choice the tutor makes is one line of code anyone can read, test, and explain. No "the AI decided" mysteries.

## What's in the system

Two ways to use it, both built on the same core:

```
                                       ┌── Command-line demo
Teaching rules + content + AI calls ───┤
                                       └── Web chat interface
```

- **`src/policy.py`** — The teaching rules. 7 priorities, first match wins.
- **`src/engine.py`** — Shared building blocks (grading answers, recording each turn, tracking progress) used by both interfaces.
- **`src/state.py`** — The data shapes for a learner's progress.
- **`src/primitives.py`** — The data shapes for content (topics, exercises, rubrics, evidence).
- **`src/tools/llm_tool.py`** — How we talk to Claude. Uses the cheaper Haiku model by default, the smarter Sonnet model when a student is struggling.
- **`src/tools/content_store.py`** — Where we pull practice questions from.
- **`src/app.py`** — The web server.
- **`src/web/index.html`** — The chat interface, in plain HTML and JavaScript.

### The 7 teaching rules (first match wins)

1. **First time on this topic** → introduce it
2. **Student says they're not confident** (rated under 4.5 out of 10) → re-explain
3. **High mastery + steady performance** → move to the next topic
4. **2+ wrong answers in a row in the same format** → switch format (e.g. show a worked example instead of multiple choice)
5. **Last answer was wrong** → re-explain
6. **Last answer was right, but mastery is still building** → ask another question
7. **Just got an explanation, no wrong answers** → ask a question to test understanding (prevents getting stuck in explanation loops)
8. **Default** → light review

### Two AI models, used differently

- **Haiku** (cheap, fast) — used by default.
- **Sonnet** (smarter, more expensive) — only when a student rated their confidence below 4.5/10.

You can override which model name we use with environment variables (`TUTOR_HAIKU_MODEL`, `TUTOR_SONNET_MODEL`) if Anthropic releases a newer version.

### When the tutor asks for a confidence rating

We don't ask after every turn — that's survey fatigue. We only ask after the tutor re-explains something (because the student got an answer wrong) or after a worked example. On routine question turns, the slider is hidden.

### Why each teaching move

Every response from the server includes a plain-English explanation for the next move (e.g. "That answer wasn't quite right — let me re-explain"). The chat interface shows it as a 💡 line above the tutor's message. This makes the adjustment visible to the student.

## Quickstart

```bash
pip install -r requirements-dev.txt
cp .env.example .env             # then add your ANTHROPIC_API_KEY
pytest                            # 84 tests, ~5 seconds
```

> **New to the project?** [`GETTING_STARTED.md`](GETTING_STARTED.md) walks through the whole setup in 5 minutes, including common problems.

### Try the command-line demo

```bash
python -m src.demo --learner alice
```

### Try the web app

```bash
python -m src.app                                        # serves on http://0.0.0.0:8000
# or with auto-reload during development:
python -m uvicorn src.app:app --reload --port 8000
```

Then open **http://localhost:8000/** in your browser.

### The web API

```
POST /api/session            → start a session; returns the first tutor message
POST /api/turn/{session_id}  → submit an answer and/or confidence rating; receive feedback + next step
GET  /api/session/{session_id}  → check progress without affecting the session
GET  /docs                   → auto-generated API documentation
```

### Running the server with Claude Code preview

The Claude Code preview tool can manage the server using a config file (`.claude/launch.json`, which is gitignored). Drop this in:

```json
{
  "version": "0.0.1",
  "configurations": [
    {
      "name": "tutor",
      "runtimeExecutable": "python",
      "runtimeArgs": ["-m", "uvicorn", "src.app:app", "--host", "127.0.0.1", "--port", "8765"],
      "port": 8765
    }
  ]
}
```

## Running tests and quality checks

```bash
pytest -v                                    # full test suite
ruff check src/ tests/ canvas_stub.py        # style and quality checks
mypy src/ canvas_stub.py                     # type checks
```

We have one critical test in [`tests/test_golden_traces.py`](tests/test_golden_traces.py) that compares the teaching rules against 12 saved test cases. If accuracy drops below 100%, the build fails.

Content has its own quality checks in [`tests/test_content.py`](tests/test_content.py): every topic needs at least 8 questions, every question needs a misconception tag, every multiple-choice question needs valid answer options, every topic needs at least one free-response question.

## Folder layout

```
src/
  app.py                    # Web server (HTTP requests)
  flow.py                   # Command-line conversation flow
  demo.py                   # Command-line entry point
  engine.py                 # Shared building blocks
  state.py                  # Student progress data shapes
  policy.py                 # The 7 teaching rules
  primitives.py             # Content catalog data shapes
  content/items.json        # 56 practice questions across 6 topics
  prompts/                  # Templates for what we tell the AI
  tools/
    llm_tool.py             # Talking to Claude
    content_store.py        # Looking up questions
  evals/golden_traces.jsonl # 12 saved test cases for the teaching rules
  web/index.html            # Chat interface
tests/                      # 84 tests
canvas_stub.py              # Stand-in for Canvas integration (replace for production)
docs/                       # Strategy and decision documents
.github/workflows/ci.yml    # Automated test runs
```

## Stand-ins for version 1 (replace before launch)

- **Canvas integration** — `canvas_stub.py` returns fake data. The production version would use the PyLTI1p3 library.
- **Saving data** — currently kept in memory only (lost on restart). Production version would use PostgreSQL. The data already has the right shape so swapping the storage is straightforward.
- **Grading free-response answers** — currently a simple text match with number tolerance (so "(46.08, 53.92)" matches "46.08, 53.92"). Production version would use AI-based grading with a rubric.

## Growing to 10,000 students

About $700/month in AI costs at that scale (10,000 students, 12 turns each per month), assuming the cheaper Haiku model handles most of it. The smarter Sonnet model would be 5–6x more if it handled everything — that's why we only upgrade when a student says they're confused.

To get there:
- **Storage**: switch from in-memory storage to Redis with timed cleanup
- **Monitoring**: add Langfuse + OpenTelemetry to track every AI call
- **Canvas**: replace the stand-in with real PyLTI1p3 integration
- **Grading**: upgrade the simple text-matching grader to AI-based grading

None of these change the teaching rules, the content shapes, or the basic structure.

## Strategy documents

- [`docs/TWO_PAGER.md`](docs/TWO_PAGER.md) — Two-page executive summary
- [`docs/PRODUCT_DECISIONS.md`](docs/PRODUCT_DECISIONS.md) — 12 open product questions with recommended answers
