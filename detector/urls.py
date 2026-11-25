"""Rutas de la interfaz y del análisis de imágenes."""

# Declaramos rutas con la función path del enrutador de Django.
from django.urls import path

# Importamos las vistas que reciben las solicitudes del detector.
from . import views


# Damos un espacio de nombres a las rutas usadas desde la plantilla.
app_name = "detector"
# Reunimos los puntos de entrada de la aplicación.
urlpatterns = [
    # Vinculamos la raíz a la vista que prepara la pantalla inicial.
    path("", views.inicio, name="inicio"),
    # Vinculamos la API al análisis y nombramos la ruta para resolverla en el formulario.
    path("api/analizar/", views.analizar, name="analizar"),
    # Exponemos las consultas al Transformer en una ruta separada de la inferencia de imágenes.
    path("api/asistente/", views.consultar_asistente, name="asistente"),
]
