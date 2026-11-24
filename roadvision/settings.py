"""Configuración de la aplicación local y sus límites de entrada."""

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured


BASE_DIR = Path(__file__).resolve().parent.parent
DEBUG = os.getenv("DJANGO_DEBUG", "1") == "1"
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured("Define DJANGO_SECRET_KEY fuera del modo de desarrollo.")
    SECRET_KEY = "django-insecure-roadvision-clave-exclusiva-de-desarrollo-local"

ALLOWED_HOSTS = os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,[::1]").split(",")
ROOT_URLCONF = "roadvision.urls"
WSGI_APPLICATION = "roadvision.wsgi.application"
LANGUAGE_CODE = "es-co"
TIME_ZONE = "America/Bogota"

INSTALLED_APPS = ["django.contrib.staticfiles", "detector"]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
CSRF_FAILURE_VIEW = "detector.views.error_csrf"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "APP_DIRS": True,
}]
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / ".static"

MODELOS_DIR = Path(os.getenv("ROADVISION_MODELOS", BASE_DIR / "modelos"))
HILOS_ONNX = max(1, int(os.getenv("ROADVISION_HILOS", "4")))
# Umbrales operativos para imágenes y fotogramas de cámara.
UMBRAL_CONFIANZA_BACHES = 0.15
UMBRAL_SEGMENTACION_GRIETAS = 0.947
MAX_BYTES_IMAGEN = 10 * 1024 * 1024
MAX_PIXELES_IMAGEN = 24_000_000
MAX_LADO_ANALISIS = 1600
DATA_UPLOAD_MAX_MEMORY_SIZE = 256 * 1024
DATA_UPLOAD_MAX_NUMBER_FILES = 1
DATA_UPLOAD_MAX_NUMBER_FIELDS = 8
FILE_UPLOAD_MAX_MEMORY_SIZE = MAX_BYTES_IMAGEN + 64 * 1024
FILE_UPLOAD_HANDLERS = [
    "detector.imagenes.LimiteCargaImagen",
    "django.core.files.uploadhandler.MemoryFileUploadHandler",
    "django.core.files.uploadhandler.TemporaryFileUploadHandler",
]
