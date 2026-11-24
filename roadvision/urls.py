"""Rutas principales del sitio."""

# Usamos path para registrar rutas e include para montar las de la aplicación.
from django.urls import include, path


# Montamos las rutas del detector desde la raíz del sitio.
urlpatterns = [path("", include("detector.urls"))]
