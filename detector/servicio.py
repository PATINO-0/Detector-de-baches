"""Orquestación de los dos modelos sobre una misma imagen RGB."""

# Reutilizamos sesiones con la caché en memoria de la biblioteca estándar.
from functools import lru_cache
# Coordinamos la carga inicial concurrente con un candado del proceso.
from threading import Lock

# Usamos NumPy para contar los píxeles marcados en la máscara.
import numpy as np
# Obtenemos rutas, hilos y umbrales de la configuración de Django.
from django.conf import settings

# Importamos el predictor que devuelve cajas de baches.
from .inferencia.baches import PredictorBaches
# Importamos el predictor que devuelve una máscara de grietas.
from .inferencia.grietas import PredictorGrietas
# Usamos el compositor que combina ambos resultados en una imagen.
from .resultados import imagen_anotada


# Creamos el candado compartido por las solicitudes del mismo proceso.
candado_modelos = Lock()


# Conservamos un único par de modelos, identificado por directorio e hilos.
@lru_cache(maxsize=1)
# Tomamos la carpeta que contiene los pesos y los hilos que usará cada sesión.
def cargar_modelos(directorio, hilos):
    # Devolvemos un par de predictores listos para inferencia.
    return (
        # Cargamos el grafo y los metadatos de baches.
        PredictorBaches(directorio / "baches.onnx", hilos),
        # Cargamos el grafo y los metadatos de grietas.
        PredictorGrietas(directorio / "grietas.onnx", hilos),
    )


# Recibimos la imagen RGB ya validada y dimensionada.
def analizar_imagen(imagen):
    """Ejecutar ambos predictores y devolver sus resultados combinados."""
    # El candado evita cargar sesiones duplicadas en las primeras solicitudes simultáneas.
    # Serializamos únicamente el acceso que puede inicializar las sesiones.
    with candado_modelos:
        # Leemos de la caché el detector y el segmentador para esta configuración.
        detector, segmentador = cargar_modelos(settings.MODELOS_DIR, settings.HILOS_ONNX)

    # Buscamos cajas con el umbral de baches que fijamos en Django.
    baches = detector.predecir(imagen, umbral=settings.UMBRAL_CONFIANZA_BACHES)
    # Obtenemos la máscara booleana con el umbral de grietas que fijamos en Django.
    mascara = segmentador.predecir(imagen, umbral=settings.UMBRAL_SEGMENTACION_GRIETAS)
    # Contamos los píxeles verdaderos de la máscara y los convertimos a entero de Python.
    pixeles_grieta = int(np.count_nonzero(mascara))
    # Recuperamos las dimensiones que definen el sistema de coordenadas de salida.
    alto, ancho = imagen.shape[:2]
    # Construimos el contrato de respuesta que serializa la vista.
    return {
        # Añadimos el JPEG que combina ambos resultados como URL de datos.
        "imagen": imagen_anotada(imagen, baches, mascara),
        # Indicamos el ancho analizado para interpretar las coordenadas de la respuesta.
        "ancho": ancho,
        # Indicamos el alto analizado en la misma unidad de píxeles.
        "alto": alto,
        # Exponemos todas las cajas que dejó el posprocesamiento de baches.
        "baches": baches,
        # Indicamos si hay grietas y calculamos su cobertura sobre todos los píxeles analizados.
        "grietas": {"detectadas": pixeles_grieta > 0, "cobertura": 100 * pixeles_grieta / mascara.size},
    }
