"""Interfaz web y procesamiento de solicitudes de análisis."""

# Interpretamos los cuerpos JSON de las consultas al asistente.
import json
# Importamos el sistema de registro para diagnosticar fallos de inferencia.
import logging

# Usamos los límites de entrada que define el proyecto.
from django.conf import settings
# Tratamos explícitamente los cuerpos JSON que superen el límite HTTP.
from django.core.exceptions import RequestDataTooBig
# Rechazamos un resumen cuando la firma de Django no se puede verificar.
from django.core.signing import BadSignature
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

# Firmamos el resumen de cada análisis y lo recuperamos al responder preguntas.
from .asistente.contexto import abrir_contexto, firmar_resultado
# Clasificamos las preguntas mediante el Transformer exportado.
from .asistente.modelo import clasificar_consulta
# Seleccionamos una plantilla de texto y la completamos con el contexto verificado.
from .asistente.respuestas import redactar
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
    # Pasamos a la plantilla los límites que valida el navegador.
    return render(request, "detector/inicio.html", {
        # Comunicamos el tamaño máximo de una imagen en bytes.
        "max_bytes_imagen": settings.MAX_BYTES_IMAGEN,
        # Coordinamos la longitud de la pregunta con la validación del servidor.
        "max_caracteres_pregunta": settings.MAX_CARACTERES_PREGUNTA,
    })


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
        # Ejecutamos los dos predictores y añadimos un resumen firmado para el asistente.
        resultado = analizar_imagen(imagen)
        # Vinculamos las consultas posteriores con las detecciones que acabamos de producir.
        resultado["contexto_asistente"] = firmar_resultado(resultado)
        # Enviamos el resultado anotado y su contexto con estado 200.
        return JsonResponse(resultado)
    # Capturamos el fallo de inferencia o composición como error del servicio.
    except Exception:
        # Registramos el detalle y la traza en los registros del servidor.
        logger.exception("Falló el análisis con los modelos de RoadVision.")
        # Devolvemos 503 con una indicación de reintento.
        return error_json("No se pudo completar el análisis. Inténtalo de nuevo.", 503)


# Impedimos que las consultas y sus respuestas se guarden en cachés HTTP.
@never_cache
def consultar_asistente(request):
    """Clasificamos una pregunta y respondemos con los datos del análisis seleccionado."""

    # Reservamos el endpoint para el envío explícito de preguntas.
    if request.method != "POST":
        return error_json("Envía la pregunta mediante POST.", 405, Allow="POST")
    # Exigimos el formato que utiliza el cliente del asistente.
    if request.content_type != "application/json":
        return error_json("Envía la pregunta en formato JSON.", 415)

    # Interpretamos el cuerpo y damos un mensaje específico si supera el límite HTTP.
    try:
        datos = json.loads(request.body)
    except RequestDataTooBig:
        return error_json("La consulta es demasiado grande.", 413)
    except (UnicodeDecodeError, ValueError, RecursionError):
        return error_json("La consulta no contiene un JSON válido.", 400)

    # Esperamos un objeto con la pregunta y un contexto opcional.
    if not isinstance(datos, dict):
        return error_json("La consulta debe ser un objeto JSON.", 400)
    # Validamos el texto antes de entrar al tokenizador del modelo.
    pregunta = datos.get("pregunta")
    # Rechazamos valores ausentes, tipos incorrectos y preguntas demasiado largas.
    if not isinstance(pregunta, str) or not pregunta.strip() or len(pregunta) > settings.MAX_CARACTERES_PREGUNTA:
        return error_json(f"Escribe una pregunta de hasta {settings.MAX_CARACTERES_PREGUNTA} caracteres.", 400)

    # Admitimos un contexto nulo para preguntas generales o sin una imagen analizada.
    token = datos.get("contexto")
    # Verificamos el tipo y el tamaño del token antes de decodificarlo.
    if token is not None and (not isinstance(token, str) or len(token) > settings.MAX_CARACTERES_CONTEXTO):
        return error_json("El contexto del análisis no es válido.", 400)
    # Verificamos que el resumen venga de la API de análisis del servidor.
    try:
        contexto = abrir_contexto(token)
    except BadSignature:
        return error_json("El resultado no se pudo verificar. Vuelve a analizar la imagen.", 400)

    # Ejecutamos el Transformer y redactamos la respuesta con los indicadores verificados.
    try:
        intencion, confianza = clasificar_consulta(pregunta.strip(), settings.MODELOS_DIR, settings.HILOS_ONNX)
        # Aplicamos la plantilla que corresponde a la intención que decidió el modelo.
        respuesta = redactar(intencion, contexto)
    except Exception:
        # Dejamos el detalle técnico en el servidor y ofrecemos un error independiente de la detección.
        logger.exception("Falló el asistente Transformer de RoadVision.")
        return error_json("El asistente no pudo responder. Inténtalo de nuevo.", 503)

    # Entregamos texto y datos de clasificación como campos independientes.
    return JsonResponse({"respuesta": respuesta, "intencion": intencion, "confianza_intencion": confianza})
