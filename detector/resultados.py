"""Composición y codificación de la imagen anotada."""

from base64 import b64encode

import cv2
import numpy as np


COLOR_BACHE = (255, 182, 74)
COLOR_GRIETA = (255, 61, 128)
COLOR_TEXTO = (28, 23, 14)
TIPOGRAFIA = cv2.FONT_HERSHEY_SIMPLEX


def marcar_bache(imagen, deteccion):
    """Dibujar una caja y su confianza en el sistema de píxeles analizado."""
    alto, ancho = imagen.shape[:2]
    x1, y1, x2, y2 = map(round, deteccion["box_xyxy"])
    cv2.rectangle(imagen, (x1, y1), (x2, y2), COLOR_BACHE, max(2, round(max(alto, ancho) / 450)))

    etiqueta = f"Bache {deteccion['confidence']:.0%}"
    escala = max(0.43, max(alto, ancho) / 1550)
    (ancho_texto, alto_texto), base = cv2.getTextSize(etiqueta, TIPOGRAFIA, escala, 1)
    ancho_etiqueta, alto_etiqueta = ancho_texto + 10, alto_texto + base + 9
    x = min(x1, max(0, ancho - ancho_etiqueta))
    y = min(y1 - alto_etiqueta if y1 >= alto_etiqueta else y1, max(0, alto - alto_etiqueta))
    cv2.rectangle(imagen, (x, y), (x + ancho_etiqueta, y + alto_etiqueta), COLOR_BACHE, cv2.FILLED)
    cv2.putText(imagen, etiqueta, (x + 5, y + alto_texto + 4), TIPOGRAFIA, escala, COLOR_TEXTO, 1, cv2.LINE_AA)


def imagen_anotada(imagen, baches, mascara, *, max_bytes=None):
    """Superponer la máscara de grietas y las cajas de baches en el mismo JPEG."""
    salida = imagen.copy()
    salida[mascara] = 0.40 * salida[mascara] + 0.60 * np.asarray(COLOR_GRIETA)
    for bache in baches:
        marcar_bache(salida, bache)

    bgr = cv2.cvtColor(salida, cv2.COLOR_RGB2BGR)
    # Reducir la calidad solo si hace falta para enviar el JSON con base64.
    for calidad in (92, 80, 65):
        exito, jpeg = cv2.imencode(".jpg", bgr, [cv2.IMWRITE_JPEG_QUALITY, calidad])
        if not exito:
            raise RuntimeError("No se pudo codificar la imagen de resultado.")
        if max_bytes is None or jpeg.nbytes <= max_bytes:
            return "data:image/jpeg;base64," + b64encode(jpeg).decode("ascii")
    raise RuntimeError("La imagen anotada supera el límite de respuesta.")
