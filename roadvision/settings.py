"""Configuración de la aplicación local y sus límites de entrada."""

import os
from pathlib import Path
from urllib.parse import urlsplit

from django.core.exceptions import ImproperlyConfigured

from detector.inferencia.almacen import AlmacenSupabase


BASE_DIR = Path(__file__).resolve().parent.parent
EN_VERCEL = os.getenv("VERCEL") == "1" and os.getenv("VERCEL_ENV") != "development"
DEBUG = os.getenv("DJANGO_DEBUG", "0" if EN_VERCEL else "1") == "1"
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured("Define DJANGO_SECRET_KEY fuera del modo de desarrollo.")
    SECRET_KEY = "django-insecure-roadvision-clave-exclusiva-de-desarrollo-local"

hosts_locales = "" if EN_VERCEL else "localhost,127.0.0.1,[::1]"
ALLOWED_HOSTS = [
    host.strip() for host in os.getenv("DJANGO_ALLOWED_HOSTS", hosts_locales).split(",") if host.strip()
]
if EN_VERCEL:
    for variable in ("VERCEL_URL", "VERCEL_BRANCH_URL", "VERCEL_PROJECT_PRODUCTION_URL"):
        if host := os.getenv(variable):
            ALLOWED_HOSTS.append(host)
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    CSRF_COOKIE_SECURE = True

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
HILOS_ONNX = max(1, int(os.getenv("ROADVISION_HILOS", "2" if EN_VERCEL else "4")))
ORIGEN_MODELOS = os.getenv("ROADVISION_ORIGEN_MODELOS", "supabase" if EN_VERCEL else "local")
ALMACEN_MODELOS = None
if ORIGEN_MODELOS == "supabase":
    url_supabase = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    origen_supabase = urlsplit(url_supabase)
    clave_supabase = (
        os.getenv("SUPABASE_ANON_KEY", "").strip() or os.getenv("SUPABASE_PUBLISHABLE_KEY", "").strip()
    )
    if (
        origen_supabase.scheme != "https" or not origen_supabase.hostname
        or origen_supabase.username is not None or origen_supabase.path
        or origen_supabase.query or origen_supabase.fragment
    ):
        raise ImproperlyConfigured("Define SUPABASE_URL con la URL HTTPS del proyecto de Supabase.")
    if not clave_supabase or clave_supabase.startswith("sb_secret_"):
        raise ImproperlyConfigured("Define SUPABASE_ANON_KEY o SUPABASE_PUBLISHABLE_KEY con una clave pública.")
    bucket_supabase = os.getenv("SUPABASE_MODELOS_BUCKET", "modelos").strip() or "modelos"
    ALMACEN_MODELOS = AlmacenSupabase(url_supabase, bucket_supabase, clave_supabase)
elif ORIGEN_MODELOS != "local":
    raise ImproperlyConfigured("ROADVISION_ORIGEN_MODELOS debe ser local o supabase.")

# Umbrales operativos para imágenes y fotogramas de cámara.
UMBRAL_CONFIANZA_BACHES = 0.15
UMBRAL_SEGMENTACION_GRIETAS = 0.947
# Reservar espacio para el formulario multipart y el JSON de la función.
MAX_MB_IMAGEN = 4 if EN_VERCEL else 10
MAX_BYTES_IMAGEN = MAX_MB_IMAGEN * 1024 * 1024
MAX_BYTES_JPEG_RESULTADO = 3_000_000 if EN_VERCEL else None
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
