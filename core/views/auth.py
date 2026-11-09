"""Login e logout (só administradores entram; a leitura da wiki não exige login)."""
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.utils.http import url_has_allowed_host_and_scheme

from .. import ratelimit


def login_view(request):
    if request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser):
        return redirect('admin_dashboard')
    error = None
    if request.method == 'POST':
        username = request.POST.get('username', '')
        if ratelimit.login_blocked(request, username):
            error = 'Muitas tentativas. Tente de novo em 15 minutos.'
        else:
            user = authenticate(request, username=username, password=request.POST.get('password'))
            if user and (user.is_staff or user.is_superuser):
                ratelimit.login_succeeded(request, username)
                login(request, user)
                # Só volta para endereços deste site (?next=https://outro-site não vira redirecionamento aberto).
                next_url = request.GET.get('next', '')
                if not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()},
                                                       require_https=request.is_secure()):
                    next_url = 'admin_dashboard'
                return redirect(next_url)
            ratelimit.login_failed(request, username)
            error = 'Credenciais inválidas ou sem permissão de administrador.'
    return render(request, 'login.html', {'error': error})


def logout_view(request):
    logout(request)
    return redirect('home')
