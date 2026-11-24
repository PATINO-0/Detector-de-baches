"""Rutas de la interfaz y del análisis de imágenes."""

from django.urls import path

from . import views


app_name = "detector"
urlpatterns = [
    path("", views.inicio, name="inicio"),
    path("api/analizar/", views.analizar, name="analizar"),
]
