from pathlib import Path
import os
import dj_database_url
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

DEBUG = os.getenv('DEBUG', 'True') == 'True'
SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-change-me')
if not DEBUG and SECRET_KEY == 'django-insecure-change-me':
    import warnings
    warnings.warn('SECRET_KEY não definida: usando a chave padrão insegura. Defina SECRET_KEY no ambiente.')
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

CSRF_TRUSTED_ORIGINS = os.getenv(
    'CSRF_TRUSTED_ORIGINS',
    'https://*.app.github.dev,https://fantastic-tribble-gxq7wjgvjv7qhv75q-8000.app.github.dev,https://localhost:8000'
).split(',')

_render_host = os.getenv('RENDER_EXTERNAL_HOSTNAME')
if _render_host:
    ALLOWED_HOSTS.append(_render_host)
    CSRF_TRUSTED_ORIGINS.append(f'https://{_render_host}')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    # Em dev, o WhiteNoise serve os estáticos no lugar do runserver (ver WHITENOISE_MAX_AGE abaixo).
    'whitenoise.runserver_nostatic',
    'django.contrib.staticfiles',
    'storages',
    'core',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # estáticos já vão comprimidos (.gz/.br do collectstatic)
    # HTML/JSON comprimido: menos tráfego na cota do Render. O token CSRF muda a cada página (proteção contra BREACH).
    'django.middleware.gzip.GZipMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'wiki_project.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'core.tools.tools_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'wiki_project.wsgi.application'

if os.getenv('DATABASE_URL'):
    # conn_max_age=0 de propósito: conexão aberta segura o compute do Neon acordado e gasta a cota.
    DATABASES = {'default': dj_database_url.config(conn_max_age=0)}
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
]

LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Sao_Paulo'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_ROOT = BASE_DIR / 'media'

# Produção: nomes com hash + .gz/.br (precisa de collectstatic). Dev e testes: os arquivos de static/ direto.
STATICFILES_BACKEND = ('django.contrib.staticfiles.storage.StaticFilesStorage' if DEBUG
                       else 'whitenoise.storage.CompressedManifestStaticFilesStorage')

if os.getenv('R2_ACCESS_KEY_ID'):
    AWS_ACCESS_KEY_ID = os.getenv('R2_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.getenv('R2_SECRET_ACCESS_KEY')
    AWS_STORAGE_BUCKET_NAME = os.getenv('R2_BUCKET_NAME')
    AWS_S3_ENDPOINT_URL = f"https://{os.getenv('R2_ACCOUNT_ID')}.r2.cloudflarestorage.com"
    AWS_S3_CUSTOM_DOMAIN = os.getenv('R2_PUBLIC_URL')
    AWS_QUERYSTRING_AUTH = False
    AWS_DEFAULT_ACL = None
    AWS_S3_FILE_OVERWRITE = False
    MEDIA_URL = f"https://{os.getenv('R2_PUBLIC_URL')}/"
    STORAGES = {
        'default': {'BACKEND': 'storages.backends.s3boto3.S3Boto3Storage'},
        'staticfiles': {'BACKEND': STATICFILES_BACKEND},
    }
else:
    MEDIA_URL = '/media/'
    STORAGES = {
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': STATICFILES_BACKEND},
    }

# Chatbot (RAG via Cloudflare Workers AI) — mesma conta Cloudflare do R2
CF_ACCOUNT_ID = os.getenv('CF_ACCOUNT_ID') or os.getenv('R2_ACCOUNT_ID')
CF_API_TOKEN = os.getenv('CF_API_TOKEN')
CF_EMBED_MODEL = os.getenv('CF_EMBED_MODEL', '@cf/baai/bge-m3')
CF_CHAT_MODEL = os.getenv('CF_CHAT_MODEL', '@cf/meta/llama-3.3-70b-instruct-fp8-fast')
CF_VISION_MODEL = os.getenv('CF_VISION_MODEL', '@cf/meta/llama-3.2-11b-vision-instruct')

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Cache em memória do processo: contadores do limite de login e do chat (core/ratelimit.py).
CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}

# Dev: os estáticos são revalidados (304) a cada carga — senão, depois de um git pull,
# o navegador roda JS/CSS velho do cache. Em produção os nomes têm hash e cache longo.
if DEBUG:
    WHITENOISE_USE_FINDERS = True
    WHITENOISE_AUTOREFRESH = True
    WHITENOISE_MAX_AGE = 0

# HTTPS: ligado em produção (Render). Num servidor interno só com HTTP (ex.: run_production.bat),
# definir HTTPS=False no .env — senão o cookie de sessão "secure" não volta e o login não funciona.
if os.getenv('HTTPS', 'False' if DEBUG else 'True') == 'True':
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = True
    SECURE_REDIRECT_EXEMPT = [r'^healthz/$']
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
SECURE_REFERRER_POLICY = 'same-origin'
SESSION_COOKIE_HTTPONLY = True

# Logs no stdout (aparecem no painel do Render). Sem isso, com DEBUG=False um erro 500 não mostra o traceback.
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'simples': {'format': '{asctime} {levelname} {name}: {message}', 'style': '{'},
    },
    'handlers': {
        'console': {'class': 'logging.StreamHandler', 'formatter': 'simples'},
    },
    'root': {'handlers': ['console'], 'level': 'WARNING'},
    'loggers': {
        'django': {'handlers': ['console'], 'level': os.getenv('DJANGO_LOG_LEVEL', 'INFO'), 'propagate': False},
        'core': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
    },
}

LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/login/'

# Corpo da requisição sem contar arquivos (formulários, JSON do chat/reordenar).
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
# Arquivos acima de 2,5 MB (padrão do Django) vão para um arquivo temporário em disco, não para a RAM:
# um vídeo grande não derruba o servidor (Render free tem 512 MB de memória).
FILE_UPLOAD_MAX_MEMORY_SIZE = 2_621_440
# Tamanho máximo de um upload de imagem/vídeo (validado em core/views/admin.py).
MAX_UPLOAD_SIZE = 500 * 1024 * 1024
