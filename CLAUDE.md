# Wiki Interna — CLAUDE.md

## Project overview
Company-internal wiki platform. Red, Yellow and White themed. Two fixed accounts (admin + reader). Three-layer navigation: Home → Major Topic page → Minor Topic page (single-page with content blocks). Also mirrored to a public portfolio repo with genericized demo content (`topicos.txt` and seed commands use fictional tool names, not real internal systems).

## Stack
- **Backend**: Django 5.2 (Python 3.10)
- **Frontend**: Django templates + Tailwind CSS (CDN Play) + vanilla JavaScript
- **Database**: SQLite locally (`db.sqlite3`); Postgres in production via `DATABASE_URL` (`dj-database-url`)
- **File uploads**: `MEDIA_ROOT` → `media/uploads/` locally; Cloudflare R2 (S3-compatible, via `django-storages`) in production when `R2_ACCESS_KEY_ID` is set
- **Static files**: WhiteNoise (`CompressedManifestStaticFilesStorage`) — no Nginx needed
- **Production server**: Gunicorn, deployed on Render (`render.yaml`)
- **Chatbot (RAG)**: Cloudflare Workers AI — embeddings (`bge-m3`), chat (`llama-3.3-70b-instruct`), vision (`llama-3.2-11b-vision`) — see `core/chatbot.py`

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
| `/chat/` | Chatbot JSON API (RAG over wiki content) |
| `/admin-wiki/dashboard/` | Admin panel (admin only) |
| `/django-admin/` | Django built-in admin |

## Models (`core/models.py`)
- `MajorTopic` — top-level topic (Layer 2 pages)
- `MinorTopic` — sub-topic under a major (Layer 3 pages), FK to MajorTopic. `is_territory_map=True` renders a special `regionais.html` page instead of content blocks.
- `ContentBlock` — content inside a minor topic; types: `text`, `image`, `video`, `checklist`, `link`. Also stores `embedding` and `image_description`, used only by the chatbot.
- `GlossaryTerm` — global glossary; any matching word in rendered text/checklists gets an auto tooltip.
- `Regiao` → `Territorio` → `Cidade` — geographic hierarchy for the regionais page, separate from the topic tree.

## Content blocks
Admins add blocks via `/admin-wiki/topico/<major>/<minor>/conteudo/`. Block types:
- **Texto** — free text, rendered with `whitespace-pre-wrap`, supports a small markdown-like syntax (`**bold**`, `_italic_`, `__underline__`, `~~strike~~`, `` `code` ``, `[ATENÇÃO]...[/ATENÇÃO]`) plus glossary tooltips
- **Checklist** — one item per line, rendered as interactive checkboxes
- **Imagem** — file upload, rendered as `<img>`; auto-described by the vision model for chatbot search
- **Vídeo** — file upload, rendered as `<video>`
- **Link** — external URL

## Chatbot (RAG)
`core/chatbot.py` implements retrieval-augmented generation over the wiki's own content:
1. On block create/edit, an embedding is generated (images are first described by the vision model) and stored on `ContentBlock.embedding`.
2. A question hits `/chat/`, gets embedded, and is matched by cosine similarity against block embeddings, with a lexical keyword boost (synonyms, typo tolerance) to catch cases the embedding misses (acronyms like "SA"/"INC").
3. The regional hierarchy (`Regiao`/`Territorio`/`Cidade`) is matched separately via direct text matching, since it's structured data with no embedding.
4. Matched blocks become context for the chat model, which answers only from that context and returns `{answer, sources}` (sources link back to the relevant topic pages).
5. Keeps a short conversation history (last 3 turns, client-sent, server-trimmed).

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

## Pendências conhecidas

### 1. Tailwind CDN → arquivo estático (ainda não feito)
Atualmente o CSS é carregado via CDN (`cdn.tailwindcss.com`). Se o servidor de destino não tiver acesso à internet, o site fica sem estilo. Resolver quando necessário:

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

### 2. Organizar views.py (ainda não feito)
`core/views.py` já tem mais de 600 linhas. Separar em:
- `core/views/public.py` — home, search, chat, major_topic, minor_topic
- `core/views/auth.py` — login_view, logout_view
- `core/views/admin.py` — todo o painel admin (tópicos, blocos, glossário, regionais)
- `core/views/__init__.py` — importa tudo para manter URLs funcionando sem alteração

### 3. Configuração de produção (feito — hospedado no Render)
O deploy já roda em produção via `render.yaml`: `DEBUG=False`, `ALLOWED_HOSTS`/`CSRF_TRUSTED_ORIGINS` lidos de env vars (com fallback automático para o hostname do Render), Gunicorn como servidor WSGI, WhiteNoise servindo estáticos (sem precisar de Nginx), Postgres via `DATABASE_URL` e mídia no Cloudflare R2. As env vars do chatbot (`CF_ACCOUNT_ID`, `CF_API_TOKEN`, etc.) precisam ser configuradas manualmente no painel do Render (não têm `generateValue` no `render.yaml`).

## Simulador de atendimento (projeto separado)

Plataforma separada para treinar fluxos de suporte de provedor de internet. **Não faz parte deste repositório** — terá repo próprio no GitHub, hospedado no Render (backend) + Neon (PostgreSQL).

### Decisões de arquitetura
- **Repositório próprio** — projeto independente da wiki
- **Hosting**: Render (web service) + Neon (PostgreSQL); cold start e perda de progresso ao fechar a aba são aceitáveis
- **Estado do caso**: vive em memória de sessão (JS/sessionStorage) enquanto o usuário está na página; não persiste entre sessões — comportamento intencional, já que casos duram poucos minutos
- **Banco de dados**: usado apenas para estrutura (tabelas de casos, fluxos, empresas mock) — sem persistência de dados por usuário entre sessões

### UI: simulação de navegador
- Tela única com múltiplas abas simulando os sistemas que o atendente usa no dia a dia
- Não criar todos os botões/campos de cara — cada elemento de UI é adicionado quando um caso real exigir aquela funcionalidade
- Desenvolvimento incremental: pega-se um fluxo real da empresa → adiciona os botões e informações relevantes → repete para o próximo caso

### Modos de uso

#### Modo Tutorial (guiado)
- Casos pré-estabelecidos com passo a passo obrigatório
- Tela escurecida com foco apenas nos elementos relevantes do momento
- Instruções explícitas: "Aqui você precisa pesquisar o PPPoE no campo X para encontrar Y"
- Obriga o usuário a seguir padronizações (ex.: sempre incluir justificativa nas notas)
- Usuário não pode pular etapas

#### Modo Prática (livre)
- Caso aleatório ou pré-selecionado gerado para o usuário praticar sozinho
- Sem guia visual — usuário resolve como sabe
- Sistema vai mostrando como está indo (feedback em tempo real ou ao final)
- Casos com múltiplas soluções válidas: a ser definido quando houver mais conhecimento sobre os fluxos reais das plataformas

### Regra de um caso por vez (sistema de fases)
- Enquanto há um caso aberto, o usuário não pode iniciar outro
- Garante que a validação do fluxo faça sentido (não mistura contextos)
- Caso encerrado (resolvido ou abandonado) → libera para iniciar um novo

### Dados mock
- Empresas e planos fixos, hardcoded (JS ou fixture Django)
- Tipos de caso a definir a partir dos fluxos reais da empresa (cancelamento, reagendamento, etc.)

### O que ainda precisa ser definido
- Quais empresas e planos existirão
- Quais fluxos/casos serão o ponto de partida do desenvolvimento
- Como representar "passos válidos" de um caso (estrutura de dados)
- Se o progresso dentro de um tutorial deve ser persistido (banco) ou só em sessão

---

## File structure
```
wiki/
├── core/                   # Main Django app
│   ├── models.py           # MajorTopic, MinorTopic, ContentBlock, GlossaryTerm, Regiao/Territorio/Cidade
│   ├── views.py            # All views (auth, public, admin) — still monolithic, see Pendências
│   ├── chatbot.py           # RAG chatbot (Cloudflare Workers AI)
│   ├── urls.py             # URL patterns
│   └── management/commands/ # seed.py, seed_regionais.py, seed_chat_demo.py, backfill_embeddings.py
├── templates/
│   ├── base.html           # Header, footer, search bar, chat widget
│   ├── login.html          # Standalone login page
│   ├── home.html           # Layer 1: search + topic cards
│   ├── major_topic.html    # Layer 2
│   ├── minor_topic.html    # Layer 3
│   ├── regionais.html      # Special Layer 3 page for the region/territory/city map
│   └── admin/              # Admin-only templates
├── static/js/              # search.js, chat.js, admin_content_block.js (drag-and-drop)
├── media/uploads/          # Uploaded images & videos (local dev only — R2 in production)
├── wiki_project/           # Django project settings
├── render.yaml             # Render deploy config
├── build.sh                # Render build script
├── .env                    # Credentials & config (not committed)
└── db.sqlite3              # SQLite database (local dev only — Postgres in production)
```
