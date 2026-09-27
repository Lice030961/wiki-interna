"""
Registro das ferramentas da wiki (páginas em /ferramentas/).

Ferramentas não são MajorTopic/MinorTopic nem têm ContentBlock, então não
aparecem sozinhas na busca nem no chatbot. Tudo o que precisa saber delas
vem daqui: barra lateral, busca do header e contexto do Assistente.

Nova ferramenta: criar a view/URL e adicionar uma entrada em TOOLS.
"""
from django.urls import reverse

TOOLS = [
    {
        'name': 'Gerador de Script SA',
        'url_name': 'script_generator',
        'description': (
            'Monta o script de abertura de SA do Salesforce a partir da ficha do cliente copiada do SIS '
            '(Ctrl+A, Ctrl+C com o "Mostrar" dos Ativos aberto): preenche ADM, PPPoE, nome, plano, ativo, '
            'telefone e endereço, e deixa escolher cliente dedicado, GPON, tratativa e observações.'
        ),
        # Palavras soltas (sem acento/maiúscula importar) que levam a esta ferramenta na
        # busca e no chatbot, além das palavras do próprio nome.
        'keywords': ['script', 'gerador', 'sa', 'salesforce', 'sis', 'ficha'],
    },
]

# Palavras que, sozinhas, significam "quero ver as ferramentas".
GROUP_WORDS = ['ferramenta', 'ferramentas']


def all_tools():
    return [{**t, 'url': reverse(t['url_name'])} for t in TOOLS]


def _normalize(text):
    from core.chatbot import _normalize as normalize
    return normalize(text)


def search_tools(q):
    """Busca do header: o texto digitado (mesmo incompleto, ex. "ferr", "gerad")
    aparece no nome, numa palavra-chave ou em "ferramentas"? Todas as palavras
    digitadas precisam bater."""
    words = _normalize(q).split()
    if not words or len(''.join(words)) < 2:
        return []
    results = []
    for tool in all_tools():
        haystack = ' '.join([tool['name'], *tool['keywords'], *GROUP_WORDS])
        haystack = _normalize(haystack)
        if all(w in haystack for w in words):
            results.append(tool)
    return results


def tools_for_question(query_words):
    """Chatbot: ferramentas relacionadas à pergunta (já passada por
    chatbot._concept_words). "ferramenta(s)" sozinho traz todas."""
    from core.chatbot import _word_matches
    if any(w in query_words for w in GROUP_WORDS):
        return all_tools()
    matched = []
    for tool in all_tools():
        tool_words = {w for w in _normalize(' '.join([tool['name'], *tool['keywords']])).split() if len(w) > 1}
        tool_words -= {'de', 'do', 'da'}
        if any(_word_matches(w, query_words) for w in tool_words):
            matched.append(tool)
    return matched


def tools_context(request):
    """Context processor: lista de ferramentas pra barra lateral."""
    tools = all_tools()
    return {'wiki_tools': tools, 'wiki_tool_url_names': [t['url_name'] for t in tools]}
