"""Views da wiki, separadas por área. Tudo é reexportado aqui para `core/urls.py` continuar usando `views.<nome>`.

- public.py           Home, busca, chat, tópicos (sem login) e /healthz/
- auth.py             login/logout
- ferramentas.py      Gerador de Script SA e Batimento de SAs
- admin_topics.py     painel: tópicos, blocos de conteúdo, glossário
- admin_regionais.py  painel: Regiões / Territórios / Cidades
- admin_olts.py       painel: OLTs, fabricantes, projetos GPON
- helpers.py          markdown, glossário, chaves de cidade/projeto
"""
from .helpers import *  # noqa: F401,F403
from .auth import *  # noqa: F401,F403
from .public import *  # noqa: F401,F403
from .ferramentas import *  # noqa: F401,F403
from .admin_topics import *  # noqa: F401,F403
from .admin_regionais import *  # noqa: F401,F403
from .admin_olts import *  # noqa: F401,F403
