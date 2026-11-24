"""Interfaz web y procesamiento de solicitudes de análisis."""

import logging

from django.conf import settings
from django.http import JsonResponse
from django.http.multipartparser import MultiPartParserError
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe

from .imagenes import ImagenDemasiadoGrande, ImagenInvalida, leer_imagen, mensaje_limite_archivo
from .servicio import analizar_imagen


logger = logging.getLogger(__name__)


def error_json(mensaje, estado, **encabezados):
    return JsonResponse({"error": mensaje}, status=estado, headers=encabezados)


def error_csrf(request, reason=""):
    return error_json("Recarga la página para volver a iniciar el análisis.", 403)


@require_safe
def inicio(request):
    return render(request, "detector/inicio.html", {
        "max_bytes_imagen": settings.MAX_BYTES_IMAGEN,
        "max_mb_imagen": settings.MAX_MB_IMAGEN,
    })


@never_cache
def analizar(request):
    """Analizar un archivo o fotograma recibido como formulario multipart."""
    if request.method != "POST":
        return error_json("Envía una imagen mediante el formulario.", 405, Allow="POST")

    try:
        archivo = request.FILES.get("imagen")
        if getattr(request, "imagen_demasiado_grande", False):
            raise ImagenDemasiadoGrande(mensaje_limite_archivo())
        if not archivo:
            return error_json("Selecciona una imagen o captura un fotograma.", 400)
        imagen = leer_imagen(archivo)
    except ImagenDemasiadoGrande as error:
        return error_json(str(error), 413)
    except (ImagenInvalida, MultiPartParserError) as error:
        mensaje = str(error) if isinstance(error, ImagenInvalida) else "El formulario de imagen no es válido."
        return error_json(mensaje, 400)

    try:
        return JsonResponse(analizar_imagen(imagen))
    except Exception:
        logger.exception("Falló el análisis con los modelos de RoadVision.")
        return error_json("No se pudo completar el análisis. Inténtalo de nuevo.", 503)
