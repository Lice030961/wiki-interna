# Wiki Interna — CLAUDE.md

## Project overview
Company-internal wiki platform. Red, Yellow and White themed. Two fixed accounts (admin + reader). Three-layer navigation: Home → Major Topic page → Minor Topic page (single-page with content blocks).

## Stack
- **Backend**: Django 5.2 (Python 3.10)
- **Frontend**: Django templates + Tailwind CSS (CDN Play) + vanilla JavaScript
- **Database**: SQLite (`db.sqlite3`)
- **File uploads**: Django's `MEDIA_ROOT` → `media/uploads/`

## Running the server
```bash
# Activate venv first
venv\Scripts\activate          # Windows
source venv/bin/activate       # Linux/Mac

python manage.py runserver
```
Server runs at http://127.0.0.1:8000

## Credentials (set in .env)
| Role   | Username | Password  |
|--------|----------|-----------|
| Admin  | admin    | admin123  |
| Reader | leitor   | leitor123 |

Change via `.env` → `ADMIN_USERNAME`, `ADMIN_PASSWORD`, `READER_USERNAME`, `READER_PASSWORD`.

## Key URLs
| URL | Purpose |
|-----|---------|
| `/` | Home (search + topic cards) |
| `/login/` | Login page |
| `/topico/<major_slug>/` | Major topic page (Layer 2) |
| `/topico/<major_slug>/<minor_slug>/` | Minor topic page (Layer 3) |
| `/busca/?q=<query>` | Search JSON API |
| `/admin-wiki/dashboard/` | Admin panel (admin only) |
| `/django-admin/` | Django built-in admin |

## Models (`core/models.py`)
- `MajorTopic` — top-level topic (Layer 2 pages)
- `MinorTopic` — sub-topic under a major (Layer 3 pages), FK to MajorTopic
- `ContentBlock` — content inside a minor topic; types: `text`, `image`, `video`, `checklist`

## Content blocks
Admins add blocks via `/admin-wiki/topico/<major>/<minor>/conteudo/`. Block types:
- **Texto** — free text, rendered with `whitespace-pre-wrap`
- **Checklist** — one item per line, rendered as interactive checkboxes
- **Imagem** — file upload, rendered as `<img>`
- **Vídeo** — file upload, rendered as `<video>`

## Seed command
```bash
python manage.py seed
```
Creates the two users and initial topic structure from `topicos.txt`.

## Theme colors
Defined in Tailwind config inside each template:
- `brand-red`: `#C8102E`
- `brand-yellow`: `#FFD100`
- Background: white (`#ffffff`)

## File structure
```
wiki/
├── core/                   # Main Django app
│   ├── models.py           # MajorTopic, MinorTopic, ContentBlock
│   ├── views.py            # All views (auth, public, admin)
│   ├── urls.py             # URL patterns
│   └── management/commands/seed.py
├── templates/
│   ├── base.html           # Header, footer, search bar
│   ├── login.html          # Standalone login page
│   ├── home.html           # Layer 1: search + topic cards
│   ├── major_topic.html    # Layer 2
│   ├── minor_topic.html    # Layer 3
│   └── admin/             # Admin-only templates
├── static/js/search.js     # Header live search
├── media/uploads/          # Uploaded images & videos
├── wiki_project/           # Django project settings
├── .env                    # Credentials & config (not committed)
└── db.sqlite3              # SQLite database
```
