"""Detector de baches V6 con el preprocesamiento y TTA de su paquete original."""

import math

import cv2
import numpy as np

from .onnx import cargar_metadatos, cargar_sesion


def letterbox(image, size):
    """Conservar proporción y centrar sobre RGB 114, siguiendo Ultralytics.

    La asimetría de un píxel en rellenos impares se resuelve con round(-0,1),
    igual que en la preparación usada al medir el detector seleccionado.
    """
    height, width = image.shape[:2]
    ratio = min(size / height, size / width)
    resized_width, resized_height = max(1, round(width * ratio)), max(1, round(height * ratio))
    left, top = round((size - resized_width) / 2 - 0.1), round((size - resized_height) / 2 - 0.1)
    canvas = np.full((size, size, 3), 114, dtype=np.uint8)
    canvas[top:top + resized_height, left:left + resized_width] = cv2.resize(
        image, (resized_width, resized_height), interpolation=cv2.INTER_LINEAR)
    tensor = np.ascontiguousarray(canvas.transpose(2, 0, 1)[None], dtype=np.float32) / 255
    # Al redondear el resize, la escala efectiva puede diferir ligeramente por
    # eje. scale_boxes de Ultralytics utiliza esas dos escalas al restaurar.
    return tensor, (resized_width / width, resized_height / height, left, top, width, height)


def augmented_view(tensor, scale, flip):
    """Aplicar el resize bilineal y el relleno inferior/derecho de scale_img.

    Las tres vistas son 1,00, 0,83 con volteo horizontal y 0,67. Los tamaños
    se redondean al múltiplo superior de 32, con relleno normalizado 0,447.
    """
    image = tensor[0].transpose(1, 2, 0)
    if flip:
        image = image[:, ::-1]
    if scale == 1:
        return np.ascontiguousarray(image.transpose(2, 0, 1)[None])
    height, width = image.shape[:2]
    resized = cv2.resize(image, (int(width * scale), int(height * scale)), interpolation=cv2.INTER_LINEAR)
    padded = np.full((math.ceil(height * scale / 32) * 32, math.ceil(width * scale / 32) * 32, 3),
                     0.447, dtype=np.float32)
    padded[:resized.shape[0], :resized.shape[1]] = resized
    return np.ascontiguousarray(padded.transpose(2, 0, 1)[None])


def combine_tta(predictions, size, views):
    """Deshacer escalas/volteo y recortar las colas TTA como YOLOv8.

    La red tiene tres escalas de detección, con proporciones de anclas 16:4:1.
    El recorte elimina los extremos que Ultralytics excluye antes de NMS.
    """
    corrected = []
    for rows, (scale, flip) in zip(predictions, views, strict=True):
        rows = rows.copy()
        rows[:, :4] /= scale
        if flip:
            rows[:, 0] = size - rows[:, 0]
        corrected.append(rows)
    corrected[0] = corrected[0][..., :-(corrected[0].shape[-1] // 21)]
    corrected[-1] = corrected[-1][..., corrected[-1].shape[-1] // 21 * 16:]
    return np.concatenate(corrected, axis=-1)


def decode(predictions, geometry, confidence, nms_iou, max_det):
    """Filtrar la clase única, aplicar NMS y recuperar coordenadas originales."""
    if predictions.ndim != 3 or predictions.shape[:2] != (1, 5):
        raise ValueError(f"Salida inesperada del detector: {predictions.shape}")
    rows = predictions[0].T
    rows = rows[(rows[:, 4] > confidence) & np.isfinite(rows).all(axis=1)]
    rows = rows[np.argsort(-rows[:, 4], kind="stable")[:30000]]
    boxes = np.column_stack((rows[:, :2] - rows[:, 2:4] / 2, rows[:, :2] + rows[:, 2:4] / 2))
    scores = rows[:, 4]
    # NMS mantiene la caja de mayor puntuación y elimina solapamientos mayores
    # al umbral. Se usa área continua xyxy, igual que el operador de torchvision.
    pending = np.arange(len(rows))
    keep = []
    while len(pending) and len(keep) < max_det:
        current = pending[0]
        keep.append(current)
        remaining = pending[1:]
        top_left = np.maximum(boxes[current, :2], boxes[remaining, :2])
        bottom_right = np.minimum(boxes[current, 2:], boxes[remaining, 2:])
        intersection = np.maximum(bottom_right - top_left, 0).prod(axis=1)
        area = np.maximum(boxes[current, 2:] - boxes[current, :2], 0).prod()
        other_area = np.maximum(boxes[remaining, 2:] - boxes[remaining, :2], 0).prod(axis=1)
        overlaps = intersection / np.maximum(area + other_area - intersection, 1e-9)
        pending = remaining[overlaps <= nms_iou]
    indices = np.asarray(keep, dtype=int)
    boxes, scores = boxes[indices], scores[indices]
    ratio_x, ratio_y, left, top, width, height = geometry
    boxes = (boxes - np.array([left, top, left, top], dtype=np.float32)) / np.array(
        [ratio_x, ratio_y, ratio_x, ratio_y], dtype=np.float32)
    boxes[:, 0::2] = np.clip(boxes[:, 0::2], 0, width)
    boxes[:, 1::2] = np.clip(boxes[:, 1::2], 0, height)
    return [{"class_id": 0, "label": "Bache", "confidence": float(score),
             "box_xyxy": [float(value) for value in box]} for box, score in zip(boxes, scores)]


class PredictorBaches:
    """Ejecutar las tres vistas del perfil calibrado del detector."""

    def __init__(self, ruta, hilos):
        self.metadatos = cargar_metadatos(ruta)
        self.sesion = cargar_sesion(ruta, self.metadatos["sha256"][ruta.name], hilos)
        self.entrada = self.sesion.get_inputs()[0].name

    def predecir(self, imagen, *, umbral=None):
        """Aplicar el umbral indicado o la confianza original del modelo."""
        if umbral is None:
            umbral = self.metadatos["confidence"]
        size = self.metadatos["image_size"]
        tensor, geometria = letterbox(imagen, size)
        tta = self.metadatos["tta"]
        vistas = list(zip(tta["scales"], tta["horizontal_flip"], strict=True))
        predicciones = [
            self.sesion.run(None, {self.entrada: augmented_view(tensor, escala, volteo)})[0]
            for escala, volteo in vistas
        ]
        return decode(
            combine_tta(predicciones, size, vistas),
            geometria,
            umbral,
            self.metadatos["nms_iou"],
            self.metadatos["max_det"],
        )
