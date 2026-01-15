import os
from os import getenv
import dotenv
from telebot.types import BotCommand
from pathlib import Path

dotenv.load_dotenv()
LOCAL = os.getenv('LOCAL', 'False').lower() == 'true'

if not LOCAL:
    import pymysql
    pymysql.install_as_MySQLdb()

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = 'w337k69z4)(z^v@^(^k^^s6v^6gp!hphhk15mlt$s$c'
DEBUG = True
ALLOWED_HOSTS = ["*"]
BOT_TOKEN = os.getenv('BOT_TOKEN')
HOOK = os.getenv('HOOK')
OWNER_ID = os.getenv('OWNER_ID')
BOT_COMMANDS = [
    BotCommand("tasks", "Мои активные задачи"),
    BotCommand("my_created_tasks", "Созданные мной задачи"),
    BotCommand("create_task", "Создать новую задачу"),
    BotCommand("close_task", "Закрыть задачу"),
    BotCommand("task_progress", "Показать прогресс задачи"),
    BotCommand("debug", "Отладочная информация"),
]
INSTALLED_APPS = [
    'bot',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
ROOT_URLCONF = 'dd.urls'
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]
WSGI_APPLICATION = 'dd.wsgi.application'

if LOCAL:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
else:
    # Автоматическое определение параметров MySQL
    db_name = os.getenv('NAME_DB', os.getenv('DB_NAME', 'jgetbot'))
    db_password = os.getenv('PASS_DB', os.getenv('DB_PASSWORD', ''))

    # Если есть NAME_DB, пытаемся автоматически определить USER
    if os.getenv('NAME_DB') and not os.getenv('DB_USER'):
        # Для хостингов типа nurgalpl_mandar1, пользователь часто такой же
        db_user = db_name
    else:
        db_user = os.getenv('DB_USER', db_name)  # По умолчанию используем имя БД как пользователя

    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': db_name,
            'USER': db_user,
            'PASSWORD': db_password,
            'HOST': os.getenv('DB_HOST', 'localhost'),
            'PORT': os.getenv('DB_PORT', '3306'),
            'OPTIONS': {
                'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
                'charset': 'utf8mb4',
            }
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]
LANGUAGE_CODE = 'ru-ru'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True
STATIC_URL = 'static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'static')
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
