"""Configuración de la aplicación local y sus límites de entrada."""

# Leemos la configuración que proporciona el entorno de ejecución.
import os
# Construimos rutas independientes del directorio desde el que iniciamos Django.
from pathlib import Path

# Informamos errores de configuración durante el arranque de la aplicación.
from django.core.exceptions import ImproperlyConfigured


# Localizamos la raíz del repositorio a partir de este archivo de configuración.
BASE_DIR = Path(__file__).resolve().parent.parent
# Activamos el modo de desarrollo cuando DJANGO_DEBUG vale 1, incluido el valor por defecto.
DEBUG = os.getenv("DJANGO_DEBUG", "1") == "1"
# Obtenemos del entorno la clave con la que Django firma información.
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY")
# Aplicamos un tratamiento explícito si aún no hay clave configurada.
if not SECRET_KEY:
    # Exigimos una clave externa al ejecutar con la depuración desactivada.
    if not DEBUG:
        # Detenemos el arranque con el nombre de la variable que falta.
        raise ImproperlyConfigured("Define DJANGO_SECRET_KEY fuera del modo de desarrollo.")
    # Usamos una clave fija de conveniencia en el entorno de desarrollo.
    SECRET_KEY = "django-insecure-roadvision-clave-exclusiva-de-desarrollo-local"

# Construimos la lista de dominios admitidos para validar la cabecera Host.
ALLOWED_HOSTS = [
    # Quitamos espacios que pueden quedar alrededor de cada dominio.
    host.strip()
    # Leemos la lista separada por comas y usamos los dominios de retorno local por defecto.
    for host in os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,[::1]").split(",")
    # Omitimos las entradas que quedan vacías después de quitar espacios.
    if host.strip()
]
# Aplicamos el tratamiento del proxy únicamente en los despliegues de Vercel.
if os.getenv("VERCEL") == "1" and os.getenv("VERCEL_ENV") != "development":
    # Vercel termina HTTPS antes de reenviar la solicitud a Django.
    # Indicamos a Django cómo reconocer una petición que llegó a Vercel mediante HTTPS.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    # Marcamos la cookie CSRF como Secure para que el navegador la envíe por HTTPS.
    CSRF_COOKIE_SECURE = True
    # Recorremos dominios de despliegue, rama y producción que proporciona Vercel.
    for variable in ("VERCEL_URL", "VERCEL_BRANCH_URL", "VERCEL_PROJECT_PRODUCTION_URL"):
        # Usamos la variable solo cuando contiene un dominio disponible.
        if dominio := os.getenv(variable):
            # Agregamos ese dominio específico a la lista de hosts admitidos.
            ALLOWED_HOSTS.append(dominio)

# Seleccionamos el módulo raíz que resuelve las rutas del sitio.
ROOT_URLCONF = "roadvision.urls"
# Identificamos la aplicación WSGI que carga el servidor de producción.
WSGI_APPLICATION = "roadvision.wsgi.application"
# Usamos la configuración de idioma correspondiente al español de Colombia.
LANGUAGE_CODE = "es-co"
# Establecemos la zona horaria de la aplicación en Bogotá.
TIME_ZONE = "America/Bogota"

# Registramos el detector y el sistema de búsqueda de archivos estáticos.
INSTALLED_APPS = ["django.contrib.staticfiles", "detector"]
# Instalamos los middlewares en el orden en que procesarán la solicitud.
MIDDLEWARE = [
    # Aplicamos los ajustes de seguridad HTTP configurados por Django.
    "django.middleware.security.SecurityMiddleware",
    # Validamos el origen, la cookie y el token CSRF en solicitudes de escritura.
    "django.middleware.csrf.CsrfViewMiddleware",
    # Añadimos la protección de encuadre administrada por Django.
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
# Dirigimos los rechazos CSRF a una respuesta JSON en español.
CSRF_FAILURE_VIEW = "detector.views.error_csrf"
# Declaramos el conjunto de motores de plantillas disponibles.
TEMPLATES = [{
    # Seleccionamos el lenguaje de plantillas de Django.
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    # Permitimos que el motor encuentre las plantillas dentro de las aplicaciones instaladas.
    "APP_DIRS": True,
}]
# Publicamos los recursos estáticos con el prefijo que usa la etiqueta static.
STATIC_URL = "/static/"
# Elegimos el directorio de salida para collectstatic y el despliegue.
STATIC_ROOT = BASE_DIR / ".static"

# Buscamos los ONNX y sus metadatos en la carpeta indicada o en modelos.
MODELOS_DIR = Path(os.getenv("ROADVISION_MODELOS", BASE_DIR / "modelos"))
# Configuramos los hilos de ONNX Runtime con 4 por defecto y un mínimo de 1.
HILOS_ONNX = max(1, int(os.getenv("ROADVISION_HILOS", "4")))
# Limitamos la longitud del texto antes de tokenizar una consulta del asistente.
MAX_CARACTERES_PREGUNTA = 400
# Acotamos el tamaño del contexto firmado que releemos en cada consulta.
MAX_CARACTERES_CONTEXTO = 2048
# Umbrales operativos para imágenes y fotogramas de cámara.
# Filtramos las cajas de baches con la confianza operativa de la aplicación.
UMBRAL_CONFIANZA_BACHES = 0.15
# Segmentamos únicamente los píxeles que alcanzan el umbral operativo de grietas.
UMBRAL_SEGMENTACION_GRIETAS = 0.947
# Limitamos cada archivo recibido a 10 MiB antes de la decodificación.
MAX_BYTES_IMAGEN = 10 * 1024 * 1024
# Limitamos la cantidad de píxeles de la imagen original a 24 millones.
MAX_PIXELES_IMAGEN = 24_000_000
# Conservamos como máximo 1.600 píxeles en el lado mayor que procesamos.
MAX_LADO_ANALISIS = 1600
# Limitamos a 256 KiB los datos de la solicitud sujetos al límite de memoria de Django.
DATA_UPLOAD_MAX_MEMORY_SIZE = 256 * 1024
# Aceptamos un único archivo en el formulario multipart.
DATA_UPLOAD_MAX_NUMBER_FILES = 1
# Limitamos el número máximo de campos de formulario.
DATA_UPLOAD_MAX_NUMBER_FIELDS = 8
# Añadimos 64 KiB de margen al umbral con el que Django elige carga en memoria o temporal.
FILE_UPLOAD_MAX_MEMORY_SIZE = MAX_BYTES_IMAGEN + 64 * 1024
# Definimos la cadena de manejadores de subida, en orden de ejecución.
FILE_UPLOAD_HANDLERS = [
    # Cortamos primero la escritura del archivo cuando supera el límite de bytes.
    "detector.imagenes.LimiteCargaImagen",
    # Mantenemos las cargas suficientemente pequeñas en memoria.
    "django.core.files.uploadhandler.MemoryFileUploadHandler",
    # Delegamos a Django el archivo temporal de las cargas que pasan al siguiente manejador.
    "django.core.files.uploadhandler.TemporaryFileUploadHandler",
]
