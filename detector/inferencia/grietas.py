"""Segmentación de grietas con el perfil original de CrackUNet."""

import cv2
import numpy as np

from .onnx import cargar_metadatos, cargar_sesion


class PredictorGrietas:
    """Identificar los píxeles con probabilidad de grieta sobre el umbral."""

    def __init__(self, ruta, hilos, *, leer_pesos=None):
        self.metadatos = cargar_metadatos(ruta)
        self.sesion = cargar_sesion(ruta, self.metadatos["onnx_sha256"], hilos, leer_pesos=leer_pesos)

    def predecir(self, imagen, *, umbral=None):
        """Aplicar el umbral indicado o el valor calibrado del modelo."""
        if umbral is None:
            umbral = self.metadatos["threshold"]
        lado = self.metadatos["image_size"]
        alto, ancho = imagen.shape[:2]
        escala = lado / max(alto, ancho)
        nuevo_ancho, nuevo_alto = max(1, round(ancho * escala)), max(1, round(alto * escala))
        x, y = (lado - nuevo_ancho) // 2, (lado - nuevo_alto) // 2
        region = np.s_[y:y + nuevo_alto, x:x + nuevo_ancho]

        lienzo = np.full((lado, lado, 3), self.metadatos["input"]["letterbox_pad"], dtype=np.uint8)
        lienzo[region] = cv2.resize(imagen, (nuevo_ancho, nuevo_alto), interpolation=cv2.INTER_LINEAR)
        entrada = np.ascontiguousarray(lienzo.transpose(2, 0, 1)[None], dtype=np.float32) / 255
        probabilidades = self.sesion.run(["probabilities"], {"images": entrada})[0][0, 0]

        # Retirar el relleno y recuperar la geometría antes de binarizar.
        probabilidades = cv2.resize(probabilidades[region], (ancho, alto), interpolation=cv2.INTER_LINEAR)
        return probabilidades >= umbral
