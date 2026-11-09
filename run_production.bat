@echo off
cd /d "%~dp0"
call venv\Scripts\activate
echo Coletando arquivos estaticos...
python manage.py collectstatic --noinput
rem Waitress serve HTTP puro: sem HTTPS=False o cookie de sessao "secure" nao volta e o login falha.
if not defined HTTPS set HTTPS=False
echo Iniciando servidor de producao...
waitress-serve --host=0.0.0.0 --port=8000 wiki_project.wsgi:application
pause
