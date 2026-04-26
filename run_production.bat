@echo off
cd /d "%~dp0"
call venv\Scripts\activate
echo Coletando arquivos estaticos...
python manage.py collectstatic --noinput
echo Iniciando servidor de producao...
waitress-serve --host=0.0.0.0 --port=8000 wiki_project.wsgi:application
pause
