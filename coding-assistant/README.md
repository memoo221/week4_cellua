# Coding Assistant — File Structure & Communication

What each file does, and which files talk to which. Folder: coding-assistant/

This project has two parts now:
- the **original chat assistant** (explain/generate code, RAG, memory) — Streamlit UI, `core/` graph
- the **new voice data-analysis feature** (Project 2) — FastAPI, upload a dataset, ask questions by voice or text, get SQL run against it

## 1. Folder layout

```
coding-assistant/
├── app/                        Streamlit UI (original assistant)
│   ├── streamlit_app.py        entry point (streamlit run app/streamlit_app.py)
│   └── components/
│       ├── chat.py             renders chat messages
│       └── artifact_view.py    shows code + "Run" button
│
├── api/                        FastAPI backend (new voice/SQL feature)
│   ├── main.py                 entry point (uvicorn api.main:app)
│   └── routes/
│       ├── health.py           GET /health — is the server alive
│       ├── dataset.py          POST /upload_dataset — upload a CSV
│       ├── query.py            POST /ask — typed question -> SQL -> result
│       └── voice.py            POST /transcribe, POST /ask-voice — voice question -> SQL -> result
│
├── core/                       the brain of the original assistant: decides what happens each turn
│   ├── state.py                the data object passed between every step
│   ├── types.py                small shared data shapes (Chunk, Artifact, Turn...)
│   ├── router.py                decides which step runs next
│   ├── graph.py                 runs the steps in order
│   └── nodes/                   one file per step
│       ├── load_memory.py
│       ├── classify.py
│       ├── explain.py
│       ├── retrieve.py
│       ├── grade.py
│       ├── generate.py
│       ├── ask_for_help.py
│       ├── learn_taught_fact.py
│       ├── request_solution.py
│       └── learn.py
│
├── services/                   talks to the outside world (APIs, databases)
│   ├── llm.py                   calls the AI model (OpenRouter) — used by both the chat assistant and the voice/SQL feature
│   ├── embeddings.py            calls the embedding API (Jina)
│   ├── vectorstore.py           talks to the Chroma database
│   ├── memory.py                talks to the SQLite database (conversation history)
│   ├── artifacts.py             wraps generated code into an object
│   ├── data_parser.py           turns an uploaded CSV's bytes into a table (pandas) — new
│   ├── dataset_store.py         talks to the SQLite database that holds the uploaded dataset — new
│   ├── speech_to_text.py        talks to Faster-Whisper (turns audio into text) — new
│   └── runner/
│       ├── protocol.py          defines what a "code runner" looks like
│       └── terminal_runner.py   actually runs the code on this machine
│
├── ingestion/                   a separate script, run once, to fill the Chroma database
│   ├── loader.py                downloads/reads the source documents
│   ├── chunker.py               splits documents into smaller pieces
│   └── build_index.py           runs loader → chunker → embeddings → database
│
├── prompts/                     the instructions sent to the AI, as text files
│   ├── classifier.v1.md
│   ├── explain.v1.md
│   ├── grade.v1.md
│   ├── generate.v1.md
│   ├── summarize.v1.md
│   └── text_to_sql.v1.md        turns a question + the dataset's columns into SQL — new
│
├── config/
│   └── settings.py              reads all settings from the .env file
│
├── data/                        created automatically, not written by hand
│   ├── chroma/                  the vector database files
│   ├── memory.db                the SQLite database file (conversation history)
│   └── datasets.db              the SQLite database file (uploaded dataset) — new
│
├── .env / .env.example          API keys and settings
└── pyproject.toml               list of Python packages this project needs
```

## 2. How the original assistant's folders talk to each other

Each folder is only allowed to call into the folder listed below it. This keeps things
simple: if you want to change how the database works, you only touch `services/`, never
`core/` or `app/`.

```
app/ → core/ → services/ → outside world (OpenRouter, Jina, Chroma, SQLite)
```

- **app/** shows the chat window and calls `core/graph.py` once per message.
- **core/** decides what to do with the message and calls the right functions in `services/`.
- **services/** is the only place that actually calls an external API or database library.
- **ingestion/** is separate — it is run by hand from the terminal to fill the database, and
  also calls into `services/` directly. It never runs during a normal chat.

## 3. One chat message, step by step (original assistant)

`core/graph.py` runs these steps, in this order, every time the user sends a message:

| Step (file in core/nodes/) | What it does |
|---|---|
| load_memory.py | Reads old messages and saved facts about the user from services/memory.py. |
| classify.py | Asks the AI: does the user want an **explanation** or **generated code**? |
| — then one of two paths runs — | |
| explain.py | Path A. Asks the AI to explain, directly. No database involved. |
| retrieve.py | Path B, step 1. Searches the Chroma database for related code. |
| grade.py | Path B, step 2. Asks the AI whether what was found is actually useful. |
| generate.py | Path B, step 3 (only if useful). Asks the AI to write the code. |
| ask_for_help.py | Path B, fallback. If nothing useful was found twice in a row, asks the user for the answer instead of guessing. |
| learn_taught_fact.py | Runs on the next message, if the user just answered ask_for_help. Saves that answer into the database. |
| request_solution.py | If code was generated, marks that the app is waiting for the user's feedback on it. |
| learn.py | Always runs last. Saves this message and the reply into memory for next time. |

## 4. Which file calls which service (original assistant)

| core/nodes/ file | Calls this in services/ | Which talks to |
|---|---|---|
| load_memory.py | memory.py | SQLite (data/memory.db) |
| classify.py | llm.py | OpenRouter (AI model) |
| explain.py | llm.py | OpenRouter |
| retrieve.py | embeddings.py, vectorstore.py | Jina (embeddings), Chroma (database) |
| grade.py | llm.py | OpenRouter |
| generate.py | llm.py, artifacts.py | OpenRouter |
| learn_taught_fact.py | embeddings.py, vectorstore.py | Jina, Chroma |
| learn.py | llm.py, memory.py | OpenRouter, SQLite |
| app/components/artifact_view.py | services/runner/terminal_runner.py | runs code locally on this computer |

## 5. The new voice/data-analysis feature (api/)

This is the Project 2 feature: upload a dataset, then ask questions about it by typing or
by speaking, and get back real results — no manually written SQL.

**Note on layering:** the original rule ("each folder only calls the one below it, `api/`
included") is bent here on purpose — `api/routes/` calls straight into `services/`
(`dataset_store.py`, `data_parser.py`, `speech_to_text.py`, `llm.py`), skipping `core/`
entirely. This feature is a separate pipeline from the chat assistant's node graph, not a
new path through it.

### Step 1 — upload a dataset (do this first, before asking anything)

`POST /upload_dataset` (api/routes/dataset.py):

1. Reads the uploaded file's bytes.
2. `services/data_parser.py` turns the bytes into a table (pandas).
3. `services/dataset_store.py` saves that table into `data/datasets.db`, as a table
   called `dataset` — a new upload replaces the old one, there's only ever one active
   dataset at a time.

### Step 2 — ask a question, typed or spoken

| Route | File | What it does |
|---|---|---|
| `POST /ask` | api/routes/query.py | Typed question in, SQL result out. |
| `POST /transcribe` | api/routes/voice.py | Audio in, transcribed text out. Doesn't touch SQL at all. |
| `POST /ask-voice` | api/routes/voice.py | Audio in → transcribed → same SQL pipeline as /ask → result out. |

Both `/ask` and `/ask-voice` end up calling the same function,
`answer_question()` in `query.py`, which does:

1. `services/dataset_store.py` → `get_schema()` — reads the current dataset's real table
   name and column names straight from SQLite.
2. `services/llm.py` → `run_text_to_sql()` — sends the question + schema to the AI model,
   using `prompts/text_to_sql.v1.md`. Understands English or Arabic; always writes standard
   SQL back.
3. `services/dataset_store.py` → `validate_sql()` — checks the SQL is a single, safe
   `SELECT` statement. Rejects anything else (DELETE, DROP, multiple statements, ...)
   before it can touch the real data.
4. `services/dataset_store.py` → `execute_sql()` — actually runs the query against
   `data/datasets.db` and returns the real rows.

### Which file calls which service (new feature)

| api/routes/ file | Calls this in services/ | Which talks to |
|---|---|---|
| dataset.py | data_parser.py, dataset_store.py | data/datasets.db (SQLite) |
| query.py | dataset_store.py, llm.py | data/datasets.db, OpenRouter |
| voice.py (/transcribe) | speech_to_text.py | Faster-Whisper (runs locally, no API key) |
| voice.py (/ask-voice) | speech_to_text.py, dataset_store.py, llm.py | Faster-Whisper, data/datasets.db, OpenRouter |

## 6. Notes

- Every file in `core/nodes/` only reads and writes its own small piece of the shared data
  object (defined in `core/state.py`) — it never calls another node file directly. Only
  `core/graph.py` decides the order.
- The text sent to the AI model is never written directly inside the Python files — it
  always comes from a matching file in `prompts/` (e.g. generate.py uses
  prompts/generate.v1.md, run_text_to_sql uses prompts/text_to_sql.v1.md).
- `config/settings.py` is read by almost every file in `services/` — it holds API keys,
  model names, and database paths, all coming from the `.env` file.
- `data/memory.db` (conversation history) and `data/datasets.db` (uploaded dataset) are
  two completely separate databases — they must never share a file or a table.
