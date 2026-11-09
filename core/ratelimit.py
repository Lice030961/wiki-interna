"""Limites simples por contador no cache (LocMemCache, por processo).

Login: bloqueia 15 min depois de 5 falhas por IP ou 10 por usuário — o IP vem do X-Forwarded-For,
que quem ataca pode inventar a cada tentativa, por isso também conta por usuário.
Chat: cada pergunta chama o Cloudflare Workers AI (cota gratuita), então limita por IP.
"""
from django.core.cache import cache

LOGIN_MAX_FALHAS_IP = 5
LOGIN_MAX_FALHAS_USUARIO = 10
LOGIN_BLOQUEIO = 15 * 60

CHAT_MAX_POR_MINUTO = 6
CHAT_MAX_POR_HORA = 60


def client_ip(request):
    # No Render o IP real é o primeiro do X-Forwarded-For; sem proxy, o REMOTE_ADDR.
    return request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip() or request.META.get('REMOTE_ADDR', '')


def _login_keys(request, username):
    username = (username or '').strip().lower()[:150]
    return [
        (f'login-falhas-ip:{client_ip(request)}', LOGIN_MAX_FALHAS_IP),
        (f'login-falhas-usuario:{username}', LOGIN_MAX_FALHAS_USUARIO),
    ]


def login_blocked(request, username):
    return any(cache.get(key, 0) >= limit for key, limit in _login_keys(request, username))


def login_failed(request, username):
    for key, _ in _login_keys(request, username):
        cache.set(key, cache.get(key, 0) + 1, LOGIN_BLOQUEIO)


def login_succeeded(request, username):
    for key, _ in _login_keys(request, username):
        cache.delete(key)


def chat_allowed(request):
    """Conta a pergunta e diz se ainda está dentro do limite (por minuto e por hora)."""
    ip = client_ip(request)
    for key, limit, window in ((f'chat-min:{ip}', CHAT_MAX_POR_MINUTO, 60),
                               (f'chat-hora:{ip}', CHAT_MAX_POR_HORA, 60 * 60)):
        # add() só cria se não existir: a janela começa na primeira pergunta.
        cache.add(key, 0, window)
        try:
            count = cache.incr(key)
        except ValueError:  # expirou entre o add e o incr
            cache.set(key, 1, window)
            count = 1
        if count > limit:
            return False
    return True
