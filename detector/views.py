"""Interfaz web y procesamiento de solicitudes de análisis."""

# Importamos el sistema de registro para diagnosticar fallos de inferencia.
import logging

# Usamos los límites de entrada que define el proyecto.
from django.conf import settings
# Convertimos las respuestas del análisis a JSON con el estado HTTP apropiado.
from django.http import JsonResponse
# Capturamos errores al interpretar el formulario de subida.
from django.http.multipartparser import MultiPartParserError
# Representamos la interfaz usando la plantilla registrada en la aplicación.
from django.shortcuts import render
# Evitamos que intermediarios o clientes reutilicen respuestas de análisis.
from django.views.decorators.cache import never_cache
# Restringimos la portada a métodos HTTP de lectura segura.
from django.views.decorators.http import require_safe

# Reutilizamos la preparación de imágenes y sus dos excepciones de validación.
from .imagenes import ImagenDemasiadoGrande, ImagenInvalida, leer_imagen
# Delegamos la inferencia y la composición del resultado al servicio.
from .servicio import analizar_imagen


# Nombramos el registrador con el módulo para identificar el origen de cada error.
logger = logging.getLogger(__name__)


# Centralizamos la respuesta de error y admitimos encabezados adicionales.
def error_json(mensaje, estado, **encabezados):
    # Entregamos un campo error en español con el código HTTP correspondiente.
    return JsonResponse({"error": mensaje}, status=estado, headers=encabezados)


# Recibimos la petición rechazada por el middleware y el motivo técnico de Django.
def error_csrf(request, reason=""):
    # Ofrecemos una indicación para recuperar el formulario con un token vigente.
    return error_json("Recarga la página para volver a iniciar el análisis.", 403)


# Habilitamos GET y HEAD para la vista principal.
@require_safe
# Atendemos la petición inicial que renderiza el espacio de inspección.
def inicio(request):
    # Pasamos a la plantilla el límite en bytes que valida el navegador.
    return render(request, "detector/inicio.html", {"max_bytes_imagen": settings.MAX_BYTES_IMAGEN})


# Impedimos que se cacheen respuestas de análisis de fotos o cámara.
@never_cache
# Recibimos la petición que contiene el archivo o fotograma.
def analizar(request):
    """Analizar un archivo o fotograma recibido como formulario multipart."""
    # Comprobamos el método antes de leer archivos o ejecutar modelos.
    if request.method != "POST":
        # Indicamos que el recurso acepta POST y devolvemos el encabezado Allow.
        return error_json("Envía una imagen mediante el formulario.", 405, Allow="POST")

    # Aislamos la validación de entrada de los fallos de inferencia.
    try:
        # Extraemos el archivo del campo imagen del formulario multipart.
        archivo = request.FILES.get("imagen")
        # Comprobamos si el manejador cortó la carga al exceder el tamaño.
        if getattr(request, "imagen_demasiado_grande", False):
            # Convertimos esa marca de la petición en un error de tamaño.
            raise ImagenDemasiadoGrande("La imagen debe pesar como máximo 10 MB.")
        # Detectamos la ausencia de archivo después de interpretar la solicitud.
        if not archivo:
            # Devolvemos una instrucción válida para las dos fuentes de imagen.
            return error_json("Selecciona una imagen o captura un fotograma.", 400)
        # Decodificamos y normalizamos el archivo como matriz RGB.
        imagen = leer_imagen(archivo)
    # Distinguimos las imágenes que superan el límite de tamaño o píxeles.
    except ImagenDemasiadoGrande as error:
        # Respondemos con 413 y el motivo de la validación.
        return error_json(str(error), 413)
    # Interceptamos los formatos inválidos y los errores estructurales del multipart.
    except (ImagenInvalida, MultiPartParserError) as error:
        # Usamos un mensaje de entrada validado o uno genérico para multipart.
        mensaje = str(error) if isinstance(error, ImagenInvalida) else "El formulario de imagen no es válido."
        # Devolvemos 400 para la solicitud que el usuario puede corregir.
        return error_json(mensaje, 400)

    # Separamos la etapa de inferencia de los errores del formulario.
    try:
        # Ejecutamos ambos predictores y enviamos el resultado con estado 200.
        return JsonResponse(analizar_imagen(imagen))
    # Capturamos el fallo de inferencia o composición como error del servicio.
    except Exception:
        # Registramos el detalle y la traza en los registros del servidor.
        logger.exception("Falló el análisis con los modelos de RoadVision.")
        # Devolvemos 503 con una indicación de reintento.
        return error_json("No se pudo completar el análisis. Inténtalo de nuevo.", 503)
