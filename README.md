# Desktop Wiki

An internal knowledge base for a customer-support team: tutorials, procedures, a glossary and small browser tools in one place, with an AI assistant that answers questions using only the wiki's own content.

**[Live demo](https://wiki-desktop.onrender.com)** · runs on Render's free tier, so the first load can take ~1 minute to wake up.

![Desktop Wiki home page](https://giovaniolivr.github.io/static/home_wiki.png)

> This public repository is the portfolio copy of a wiki used internally at a company. All topics, tools and seed data here are fictional placeholders. No internal content, systems or endpoints are included.

## Features

- **Three-level navigation**: Home → topic → sub-topic. Each sub-topic is a single page built from ordered content blocks: text, checklist, image, video and link.
- **Admin panel**: create and reorder topics and blocks with drag-and-drop, upload media, and manage the glossary and the regional map. Readers only browse; one admin account edits.
- **Lightweight formatting**: `**bold**`, `_italic_`, `` `code` ``, `~~strike~~` and a highlighted `[ATENÇÃO]…[/ATENÇÃO]` warning box inside text blocks.
- **Glossary tooltips**: any glossary term that appears in a text or checklist gets an automatic hover definition.
- **Search**: instant search across topics, block content, tools and places.
- **AI assistant (RAG)**: answers questions from the wiki's content and links to the pages it used (details below).
- **Tools**: browser-only utilities such as a support-ticket script generator. It parses customer data pasted by the user entirely client-side, so that data never reaches the server.

## How the assistant works

The assistant is retrieval-augmented generation on Cloudflare Workers AI, implemented in [`core/chatbot.py`](core/chatbot.py):

1. **Indexing**: when a block is saved, its text is embedded with `bge-m3`. Images are first described by a vision model (`llama-3.2-11b-vision`), so screenshots of step-by-step procedures become searchable.
2. **Retrieval**: the question, plus the user's last messages for follow-ups, is embedded and ranked against blocks by cosine similarity. Results are grouped by sub-topic and cut off relative to the best match instead of by a fixed threshold.
3. **Keyword boost**: a lexical score on topic titles, with synonyms and typo tolerance, catches what embeddings miss, such as short acronyms or different verbs for the same action.
4. **Structured data**: the regions → territories → cities hierarchy and the tools registry have no embeddings. They are matched by name and added to the context.
5. **Answer**: `llama-3.3-70b-instruct` answers only from that context. The sources are returned separately and rendered as buttons, and links are stripped from the generated text.

## Adding a tool

Tools live in a single registry, [`core/tools.py`](core/tools.py). One entry (name, URL name, description, keywords) adds the tool to the sidebar, the header search and the assistant's context.

## Stack

| Layer | Technology |
|---|---|
| Backend | Django 5.2 (Python) |
| Frontend | Django templates, Tailwind CSS, vanilla JavaScript |
| Database | SQLite locally, PostgreSQL in production |
| Media | Cloudflare R2 (S3-compatible, via `django-storages`) |
| AI | Cloudflare Workers AI: embeddings, chat and vision models |
| Hosting | Render (Gunicorn + WhiteNoise) |

## Running locally

```bash
python -m venv venv
venv\Scripts\activate            # Windows  (Linux/macOS: source venv/bin/activate)
pip install -r requirements.txt

python manage.py migrate
python manage.py seed --topicos  # admin user + demo topic structure
python manage.py runserver       # http://127.0.0.1:8000
```

Configuration is read from a `.env` file. Everything is optional for a local run:

| Variable | Purpose |
|---|---|
| `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS` | Django basics |
| `ADMIN_USERNAME`, `ADMIN_PASSWORD` | Admin account created by `seed` |
| `DATABASE_URL` | Use PostgreSQL instead of SQLite |
| `CF_ACCOUNT_ID`, `CF_API_TOKEN` | Enable the AI assistant |
| `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME`, `R2_ACCOUNT_ID`, `R2_PUBLIC_URL` | Store uploads on Cloudflare R2 instead of `media/` |

Without the Cloudflare variables the wiki still works, but the assistant is disabled.

## Deployment

`render.yaml` and `build.sh` deploy to Render: they install dependencies, collect static files, run migrations, ensure the admin user exists and backfill missing embeddings. Deploys never create or change content. Content is managed only through the admin panel.
