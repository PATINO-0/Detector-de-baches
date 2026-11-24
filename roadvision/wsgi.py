"""Punto de entrada WSGI para servir la aplicación."""

# Usamos el entorno del proceso para seleccionar la configuración de Django.
import os

# Importamos la fábrica del objeto que atiende peticiones bajo WSGI.
from django.core.wsgi import get_wsgi_application


# Definimos la configuración predeterminada antes de inicializar el servidor.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "roadvision.settings")
# Exponemos el callable WSGI que invoca el servidor, incluido Vercel.
application = get_wsgi_application()
