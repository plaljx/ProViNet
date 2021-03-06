# -*- coding: utf-8 -*-
# Django settings for glabnetman project.

from django import VERSION as DJANGO_VERSION
from django.utils.translation import ugettext_lazy as _
import platform

RUNNING_ENVIROMENT = "development"
# RUNNING_ENVIROMENT = "production"
if RUNNING_ENVIROMENT == "development":
	DEBUG = True
else:
	DEBUG = False
TEMPLATE_DEBUG = DEBUG
ENABLE_DEBUG_TOOL = False

OPERATING_SYSTEM = platform.system()
if OPERATING_SYSTEM == "Windows":
	MY_LOCALE_PATH = "D:\ProViNet\web\tomato\locale"
	MY_SYSCONF_PATH = "D:\ProViNet\conf\web.conf"
	STATIC_ROOT = ('D:\ProViNet\web\tomato\static')
	STATIC_URL = ('/static/')
else:
	MY_LOCALE_PATH = "/usr/share/tomato/web/tomato/locale"
	MY_SYSCONF_PATH = "/etc/tomato/web.conf"
	STATIC_ROOT = "/usr/share/tomato/web/tomato/static"
	STATIC_URL = '/static/'
	
LOCALE_PATHS = (
	MY_LOCALE_PATH
)
TUTORIAL_URL = "/static/tutorials/index.json"

ADMINS = (
    # ('Your Name', 'your_email@domain.com'),
)

MANAGERS = ADMINS

DATABASE_ENGINE = ''           # 'postgresql_psycopg2', 'postgresql', 'mysql', 'sqlite3' or 'oracle'.
DATABASE_NAME = ''             # Or path to database file if using sqlite3.
DATABASE_USER = ''             # Not used with sqlite3.
DATABASE_PASSWORD = ''         # Not used with sqlite3.
DATABASE_HOST = ''             # Set to empty string for localhost. Not used with sqlite3.
DATABASE_PORT = ''             # Set to empty string for default. Not used with sqlite3.

# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be available on all operating systems.
# If running in a Windows environment this must be set to the same as your
# system time zone.
TIME_ZONE = 'Asia/Shanghai'

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = 'zh-cn'
gettext_noop = lambda s: s
LANGUAGES = (
    ('en', gettext_noop('English')),
    ('zh-cn', gettext_noop('Simplified Chinese')),
    ('zh-tw', gettext_noop('Traditional Chinese')),
)

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

# Absolute path to the directory that holds media.
# Example: "/home/media/media.lawrence.com/"
MEDIA_ROOT = ''

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash if there is a path component (optional in other cases).
# Examples: "http://media.lawrence.com", "http://example.com/media/"
MEDIA_URL = ''

# Make this unique, and don't share it with anybody.
import random
SECRET_KEY = str(random.random())

# List of callables that know how to import templates from various sources.
TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.Loader',
    'django.template.loaders.app_directories.Loader',
)

MIDDLEWARE_CLASSES = (
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
)
if ENABLE_DEBUG_TOOL:
	MIDDLEWARE_CLASSES += ( 'debug_toolbar.middleware.DebugToolbarMiddleware',)
	
AUTHENTICATION_BACKENDS = ('django.contrib.auth.backends.RemoteUserAuthBackend',)

ROOT_URLCONF = 'tomato.urls'

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'TIMEOUT': 3600,
        'OPTIONS': {
            'MAX_ENTRIES': 1000
        }
    }
}

SESSION_ENGINE = 'django.contrib.sessions.backends.signed_cookies'
SESSION_SERIALIZER='django.contrib.sessions.serializers.PickleSerializer'

TEMPLATE_CONTEXT_PROCESSORS = ('django.core.context_processors.request',
                               'django.core.context_processors.i18n',)

import os
CURRENT_DIR = os.path.dirname(__file__)
TEMPLATE_DIRS =(os.path.join(CURRENT_DIR, 'templates'),)

INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sites',
    'tomato.crispy_forms',
    'tomato'
)
if ENABLE_DEBUG_TOOL:
	INSTALLED_APPS += ('django.contrib.staticfiles',)
	INSTALLED_APPS += ( 'debug_toolbar',)
	
if RUNNING_ENVIROMENT == "production":
	INSTALLED_APPS += ('django.contrib.staticfiles',)

server_protocol = "http"
server_host = "localhost"
server_port = "8000"
server_httprealm="BUPT ProViNet"
# tutorial_list_url="http://packages.tomato-lab.org/tutorials/index.json"
server_url = "http://127.0.0.1"

CRISPY_TEMPLATE_PACK = "bootstrap3"

if DJANGO_VERSION < (1,4):
    TEMPLATE_LOADERS = (
        'django.template.loaders.filesystem.load_template_source',
        'django.template.loaders.app_directories.load_template_source',
    )
    SESSION_ENGINE = 'django.contrib.sessions.backends.cache'

try:
    import sys
    for path in filter(os.path.exists, [MY_SYSCONF_PATH, os.path.expanduser("~/.tomato/web.conf"), "web.conf"]):
        try:
            execfile(path)
            print >>sys.stderr, "Loaded config from %s" % path
        except Exception, exc:
            print >>sys.stderr, "Failed to load config from %s: %s" % (path, exc)
except:
    import traceback
    traceback.print_exc()
