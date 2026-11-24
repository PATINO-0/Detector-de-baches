"""Orquestación de los dos modelos sobre una misma imagen RGB."""

from functools import lru_cache
from threading import Lock

import numpy as np
from django.conf import settings

from .inferencia.baches import PredictorBaches
from .inferencia.grietas import PredictorGrietas
from .resultados import imagen_anotada


candado_modelos = Lock()


@lru_cache(maxsize=1)
def cargar_modelos(directorio, hilos):
    return (
        PredictorBaches(directorio / "baches.onnx", hilos),
        PredictorGrietas(directorio / "grietas.onnx", hilos),
    )


def analizar_imagen(imagen):
    """Ejecutar ambos predictores y devolver sus resultados combinados."""
    # El candado evita cargar sesiones duplicadas en las primeras solicitudes simultáneas.
    with candado_modelos:
        detector, segmentador = cargar_modelos(settings.MODELOS_DIR, settings.HILOS_ONNX)

    baches = detector.predecir(imagen, umbral=settings.UMBRAL_CONFIANZA_BACHES)
    mascara = segmentador.predecir(imagen, umbral=settings.UMBRAL_SEGMENTACION_GRIETAS)
    pixeles_grieta = int(np.count_nonzero(mascara))
    alto, ancho = imagen.shape[:2]
    return {
        "imagen": imagen_anotada(imagen, baches, mascara),
        "ancho": ancho,
        "alto": alto,
        "baches": baches,
        "grietas": {"detectadas": pixeles_grieta > 0, "cobertura": 100 * pixeles_grieta / mascara.size},
    }
