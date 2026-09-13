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
