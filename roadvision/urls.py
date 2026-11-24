"""Rutas principales del sitio."""

from django.urls import include, path


urlpatterns = [path("", include("detector.urls"))]
