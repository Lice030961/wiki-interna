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
| `/ferramentas/gerador-sa/` | Gerador de Script de SA (client-side only) |
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

## Ferramentas (registro em `core/tools.py`)
Ferramentas não são tópicos nem têm `ContentBlock`, então tudo sobre elas vem da lista `TOOLS` em `core/tools.py` (nome, `url_name`, descrição, palavras-chave). Esse registro alimenta: o menu "Ferramentas" da barra lateral (context processor `tools_context`), a busca do header (`search_tools`, resultados com rótulo "Ferramentas") e o chatbot (`_tools_context` em `chatbot.py`, casamento léxico pelo nome/palavras-chave; "ferramenta(s)" traz todas; a ferramenta vira fonte com link). **Nova ferramenta:** criar view + URL e adicionar uma entrada em `TOOLS` — nada mais.

## Gerador de Script de SA
`/ferramentas/gerador-sa/` monta o script de abertura de SA do Salesforce a partir do texto da ficha do cliente copiado do SIS (Ctrl+A, Ctrl+C, com o "Mostrar" dos Ativos aberto). O parser fica em `static/js/script_generator.js` e roda **só no navegador**: nada de dados de cliente vai ao servidor, e o código não chama nem referencia nenhum sistema interno (só procura rótulos no texto colado). Não adicionar integração direta com o SIS/NOC — os endpoints internos não podem aparecer neste repo público.

Regras: ADM vem da "Área do Assinante (SAC)"; o nome é a linha antes de "E-mail"; o plano é o serviço aberto (linha antes de "Adicionais do Contrato", já que um ADM pode ter vários links); "Manter endereço do SIS" (marcado por padrão) pode ser desmarcado quando o SIS repete o mesmo endereço em todos os links; PPPoE `@desktop.com.br` é encurtado até o `@` (outros domínios ficam completos); endereço sempre `Rua, número - Bairro - Cidade/SP`; cliente dedicado → Ativo `-` e sem GPON; Mudança de ponto também não leva GPON; Navegação ("SEM NAVEGAÇÃO") e Lentidão escondem a escolha e usam sempre GPON UP (o cliente está conectado); botões na ordem Conexão, Oscilação (UP/DOWN) → Navegação, Lentidão (só UP) → Mudança de ponto (sem GPON); Obs "LIBERAR TÉCNICO" escreve "NECESSÁRIO LIBERAR TÉCNICO".

## Seed command
```bash
python manage.py seed             # só o usuário admin (roda a cada deploy via build.sh)
python manage.py seed --topicos    # + tópicos de demonstração (lista fixa em seed.py) — só em banco novo/local
```
O deploy **nunca** cria tópicos: o conteúdo de cada site (inclusive o da empresa, via `lice`) é criado pelo painel e vive só no banco. Push leva só código — por isso qualquer mudança que precise de dados tem que vir como migration, não como seed. `topicos.txt` é só referência, o código não lê.

## Theme / design
Visual language follows `DESIGN.md` (Pinterest design system) **but with the Desktop palette** — never use Pinterest red `#e60023`.
- Brand (Tailwind config in `templates/base.html`): `brand-red` `#AC2407` (hover `brand-redhov` `#8f1d06`), `brand-yellow` `#EFBC00` (hover `brand-yellhov` `#d4a800`)
- Neutrals from DESIGN.md: `ink`, `body`, `mute`, `ash`, `hairline`, `card` (`#f6f6f3`), `secondary` (`#e5e5e0`), etc.
- Font Inter (substitute for Pin Sans); radii only 16px (`rounded-2xl`), 32px (`rounded-[32px]`) and pill (`rounded-full`); no card shadows
- Shared CSS in `static/css/theme.css`: collapsible sidebar, glossary tooltips (red + yellow, Desktop palette), `[ATENÇÃO]` box, chat typing dots
- Layout: red left sidebar, icons-only by default and expanding over the content on hover (logo → Home, Início, Ferramentas group, Assistente/chat; bottom: Painel Admin for admins, Entrar/Sair); drawer on mobile. Search bar stays in the white top bar (1px `ash` divider, same gray as the topic card borders). No footer.

## Revamp de design — CONCLUÍDO

**Estado atual (27/09/2026):** a primeira parte do revamp (itens abaixo) foi commitada na branch `revamp`, mergeada na `main` e enviada para `origin` e `lice` — o Render publica a partir da `main`. O que está em "Falta fazer" continua pendente.

**Já feito (na branch `revamp`):**
- `base.html`: barra lateral vermelha (só ícones, abre no hover por cima do conteúdo; gaveta no celular), grupo "Ferramentas" que abre/fecha (Gerador de Script SA), "Assistente" abre o chat, Painel Admin + Entrar/Sair no rodapé da barra; header branco com linha `ash` e busca em pílula; sem footer; fonte Inter; tokens de cor no Tailwind config
- `static/css/theme.css`: CSS global (barra lateral, tooltips do glossário em vermelho/amarelo, caixa `[ATENÇÃO]`, chat) — o CSS do glossário saiu de `minor_topic.html`
- Home: frase "Encontre **tutoriais**, **ferramentas** e **informações** da equipe" (palavras em vermelho, traço amarelo acima), tópicos em blocos brancos com borda vermelha Desktop (`brand-red`) que fica amarela no hover (sombra neutra bem leve só no hover), contorno do emoji `brand-red`, etiquetas de sub-tópicos em vermelho
- Chat: cabeçalho vermelho com faixa amarela, mensagens do usuário em amarelo, do assistente em vermelho claro, fontes como pílulas
- Login e as 11 telas de `templates/admin/` convertidas para o novo padrão (cantos 16px, neutros do DESIGN.md, foco amarelo, texto escuro sobre amarelo)
- Ferramentas: registro único em `core/tools.py` (barra lateral, busca do header e chatbot); Assistente indica o caminho no menu em vez de escrever links
- Tópico, sub-tópico e regionais: breadcrumb `mute`, título 28px, emoji em círculo com borda `brand-red`, painéis/blocos brancos com borda `brand-red` (clicáveis ficam amarelos no hover), botões `rounded-2xl` h-10, estado vazio em `brand-yellow/20`
- Painéis do admin (formulários, lista de tópicos, blocos, glossário, regionais) com borda `brand-red`; campos de formulário continuam `hairline`
- Gerador SA: entrada e script em painéis com borda `brand-red`, opções como pílulas (vermelho quando marcadas; Obs em amarelo), campos não encontrados destacados em amarelo;
  instrução encurtada; "Administrativo" virou placeholder cinza (continua sendo o valor padrão no script); aviso amarelo logo abaixo dos botões Copiar/Limpar: "Lembre-se de sempre conferir o Script e adicionar Notas na SA!"

**Preferências de design do usuário (já validadas):**
- Paleta da Desktop sempre (vermelho `#AC2407`, amarelo `#EFBC00`), nada do vermelho do Pinterest
- Não exagerar em cores diferentes: blocos brancos, bordas vermelho Desktop (`brand-red`), amarelo como destaque de hover, vermelho para etiquetas/destaques
- Sem painéis/seções redundantes (ex.: ferramentas ficam só na barra lateral, não na Home)
- Textos curtos: nada de explicação técnica que não ajuda quem usa a ferramenta

**Falta fazer:**
- Próximas entregas: mesmo fluxo — commit na `revamp`, merge na `main` e push (`origin` = `giovaniolivr/wiki-desktop`; depois `lice` = `Lice030961/wiki-interna`)

**Observações:**
- `DESIGN.md` (raiz) é o design system do Pinterest, gerado com `npx getdesign@latest add pinterest` (Node.js LTS instalado via winget)
- Em dev, o navegador pode usar `chat.js`/`theme.css` antigos do cache — Ctrl+F5 (em produção o WhiteNoise versiona os arquivos)
- O sub-tópico "Localizar Cliente" mostra o mapa de regionais porque está marcado `is_territory_map` no banco — não é bug do revamp
- O git local usa o e-mail `giovaniolivr@gmail.com` (commits antigos, até `b73cb8b`, saíram com `gibinha.jesus@gmail.com`)

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
