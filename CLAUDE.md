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

## Credentials
Admin user is created directly in the database. Password is managed via Django Admin (`/django-admin/`).

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

## Antes de entregar para servidor interno (fazer como etapa final)

### 1. Tailwind CDN → arquivo estático
Atualmente o CSS é carregado via CDN (`cdn.tailwindcss.com`). Se o servidor interno não tiver acesso à internet, o site ficará sem estilo. Resolver antes da entrega:

1. Baixar o executável standalone em https://github.com/tailwindlabs/tailwindcss/releases (`tailwindcss-windows-x64.exe`) — não precisa de Node.js
2. Gerar o CSS:
   ```bash
   tailwindcss.exe -i - -o static/css/tailwind.css --content "templates/**/*.html" --minify
   ```
3. Em `templates/base.html`, substituir as duas tags do Tailwind por:
   ```html
   <link rel="stylesheet" href="{% static 'css/tailwind.css' %}">
   ```
4. Rodar `python manage.py collectstatic`

> Se forem adicionadas classes Tailwind novas nos templates depois disso, rodar o passo 2 novamente.

### 2. Organizar views.py
`core/views.py` já tem mais de 400 linhas. Antes da entrega, separar em:
- `core/views/public.py` — home, search, major_topic, minor_topic
- `core/views/auth.py` — login_view, logout_view
- `core/views/admin.py` — todo o painel admin (tópicos, blocos, glossário, regionais)
- `core/views/__init__.py` — importa tudo para manter URLs funcionando sem alteração

### 3. Configurações de produção
Ajustar antes de subir no servidor interno:
- `DEBUG=False` no `.env`
- `ALLOWED_HOSTS=<ip-do-servidor>` no `.env` (e lido em `settings.py`)
- Instalar Gunicorn: `pip install gunicorn`
- Iniciar com: `gunicorn wiki_project.wsgi:application --bind 0.0.0.0:8000`
- Colocar Nginx na frente para servir `static/` e `media/` diretamente

## Ideia futura: Simulador de atendimento

Seção separada da wiki para treinar fluxos de suporte de provedor de internet. Acessível por uma aba no nav (`/simulador/`), fora da navegação em 3 camadas existente.

### Conceito
- Empresas mock pré-definidas com suas informações e planos de internet — sempre as mesmas, fixas
- Usuário acessa o simulador e cria um novo caso para praticar
- Os detalhes do caso (empresa, plano, tipo de problema) são gerados aleatoriamente a partir dos dados fixos

### Dados mock (sem banco de dados)
Hardcoded em JS estático — dados fixos, sem modelo Django.

### Estado durante a sessão
O caso gerado vive na memória do navegador (JS) enquanto o usuário está na página. Não persiste entre sessões — comportamento intencional.

### O que precisaria implementar
- `templates/simulador.html` — interface da página
- `static/js/simulador.js` — dados das empresas + lógica de geração aleatória
- Uma view simples em `core/views.py`
- Uma URL: `/simulador/`
- Link no `base.html` para a nova seção
- Zero novos modelos Django

### Detalhes a definir
- Quais empresas e planos existirão
- Quais tipos de caso serão gerados (cancelamento, reagendamento, etc.)
- Como será a interface de resolução do caso

---

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
