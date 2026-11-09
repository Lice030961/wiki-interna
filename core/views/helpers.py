"""Funções usadas por mais de um módulo de views."""
import re
import unicodedata
from django.utils.html import escape
from django.utils.safestring import mark_safe



def is_admin(user):
    return user.is_staff or user.is_superuser


def apply_markdown(text):
    """Converte marcadores de formatação em HTML. Chamado sobre texto já HTML-escapado."""
    def attention_replace(m):
        inner = m.group(1).strip('\n')
        return (
            '\n<div class="attention-box">'
            '<span class="attention-label">⚠️ ATENÇÃO</span>'
            + inner +
            '</div>\n'
        )
    text = re.sub(
        r'\n*\[ATENÇÃO\]\n?(.*?)\n?\[/ATENÇÃO\]\n*',
        attention_replace,
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    pairs = [
        (re.compile(r'\~\~(.+?)\~\~', re.DOTALL), r'<s>\1</s>'),
        (re.compile(r'\*\*(.+?)\*\*', re.DOTALL), r'<strong>\1</strong>'),
        (re.compile(r'\_\_(.+?)\_\_', re.DOTALL), r'<u>\1</u>'),
        (re.compile(r'\_(.+?)\_', re.DOTALL), r'<em>\1</em>'),
        (re.compile(r'\`(.+?)\`'), r'<code class="bg-gray-100 px-1 rounded text-xs font-mono">\1</code>'),
    ]
    for pattern, repl in pairs:
        text = pattern.sub(repl, text)
    return text


def apply_glossary(text, terms):
    """
    Converte marcadores de formatação e substitui termos do glossário por spans com tooltip.
    Retorna HTML seguro.
    """
    escaped = escape(text)
    escaped = apply_markdown(escaped)

    if terms:
        sorted_terms = sorted(terms, key=lambda t: len(t.term), reverse=True)
        for term_obj in sorted_terms:
            # (?![^<>]*>) impede substituição dentro de atributos de tags já inseridas
            pattern = re.compile(
                r'(?<!\w)(?![^<>]*>)(' + re.escape(escape(term_obj.term)) + r')(?!\w)',
                re.IGNORECASE
            )
            tooltip_def = escape(term_obj.definition).replace('"', '&quot;')
            replacement = (
                f'<span class="glossary-term" '
                f'data-term="{escape(term_obj.term)}" '
                f'data-def="{tooltip_def}">'
                f'\\1</span>'
            )
            escaped = pattern.sub(replacement, escaped)

    return mark_safe(escaped.replace('\n', '<br>'))


def city_key(name):
    name = unicodedata.normalize('NFKD', name or '').encode('ascii', 'ignore').decode().lower()
    name = re.sub(r"['`´’]", '', name)
    return ' '.join(re.sub(r'[^a-z0-9]+', ' ', name).split())


def projeto_key(name):
    """ "GPON Bauru Area E LPNET" e "Bauru Área E - LPNET" viram a mesma chave."""
    return re.sub(r'^gpon ', '', city_key(name))
