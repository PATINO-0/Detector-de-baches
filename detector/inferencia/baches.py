"""Detector de baches V6 con el preprocesamiento y TTA de su paquete original."""

# Usamos funciones de redondeo hacia arriba para alinear las vistas al stride.
import math

# Usamos OpenCV para interpolar los píxeles al redimensionar.
import cv2
# Usamos NumPy para tensores, coordenadas y operaciones vectorizadas sobre candidatos.
import numpy as np

# Reutilizamos la lectura de metadatos y la carga verificada de la sesión CPU.
from .onnx import cargar_metadatos, cargar_sesion


# Preparamos el cuadrado de entrada y registramos cómo regresar a la foto.
def letterbox(image, size):
    """Conservar proporción y centrar sobre RGB 114, siguiendo Ultralytics.

    La asimetría de un píxel en rellenos impares se resuelve con round(-0,1),
    igual que en la preparación usada al medir el detector seleccionado.
    """
    # Obtenemos alto y ancho de la matriz RGB de origen.
    height, width = image.shape[:2]
    # Calculamos la mayor escala uniforme que permite ajustar ambos ejes al cuadrado.
    ratio = min(size / height, size / width)
    # Redondeamos las dimensiones de la imagen y garantizamos al menos un píxel por eje.
    resized_width, resized_height = max(1, round(width * ratio)), max(1, round(height * ratio))
    # Calculamos la posición inicial con el criterio de redondeo del detector original.
    left, top = round((size - resized_width) / 2 - 0.1), round((size - resized_height) / 2 - 0.1)
    # Llenamos el cuadrado de tres canales con gris 114 en formato de 8 bits.
    canvas = np.full((size, size, 3), 114, dtype=np.uint8)
    # Colocamos los píxeles reescalados únicamente en la región central.
    canvas[top:top + resized_height, left:left + resized_width] = cv2.resize(
        # Pasamos el ancho y el alto esperados por OpenCV y seleccionamos interpolación lineal.
        image, (resized_width, resized_height), interpolation=cv2.INTER_LINEAR)
    # Añadimos el eje de lote y convertimos HWC a NCHW, float32 y rango de 0 a 1.
    tensor = np.ascontiguousarray(canvas.transpose(2, 0, 1)[None], dtype=np.float32) / 255
    # Al redondear el resize, la escala efectiva puede diferir ligeramente por
    # eje. scale_boxes de Ultralytics utiliza esas dos escalas al restaurar.
    # Devolvemos el tensor y las escalas efectivas de cada eje junto con los límites originales.
    return tensor, (resized_width / width, resized_height / height, left, top, width, height)


# Preparamos una de las vistas aumentadas que evalúa el mismo modelo.
def augmented_view(tensor, scale, flip):
    """Aplicar el resize bilineal y el relleno inferior/derecho de scale_img.

    Las tres vistas son 1,00, 0,83 con volteo horizontal y 0,67. Los tamaños
    se redondean al múltiplo superior de 32, con relleno normalizado 0,447.
    """
    # Extraemos el primer elemento del lote y recuperamos el orden de canales HWC.
    image = tensor[0].transpose(1, 2, 0)
    # Consultamos el indicador de inversión de esta vista.
    if flip:
        # Invertimos el orden de columnas para voltear la imagen horizontalmente.
        image = image[:, ::-1]
    # Conservamos las dimensiones si la escala solicitada es uno.
    if scale == 1:
        # Volvemos a NCHW y aseguramos memoria contigua, incluso si hubo volteo.
        return np.ascontiguousarray(image.transpose(2, 0, 1)[None])
    # Leemos las dimensiones espaciales que usa esta vista.
    height, width = image.shape[:2]
    # Calculamos dimensiones truncadas y redimensionamos con interpolación bilineal.
    resized = cv2.resize(image, (int(width * scale), int(height * scale)), interpolation=cv2.INTER_LINEAR)
    # Reservamos un lienzo que redondeamos hacia arriba a múltiplos de 32.
    padded = np.full((math.ceil(height * scale / 32) * 32, math.ceil(width * scale / 32) * 32, 3),
                     # Llenamos el lienzo con el gris normalizado que usa el aumento original.
                     0.447, dtype=np.float32)
    # Copiamos la vista desde la esquina superior izquierda y dejamos relleno abajo y a la derecha.
    padded[:resized.shape[0], :resized.shape[1]] = resized
    # Devolvemos la vista aumentada como tensor NCHW de un elemento.
    return np.ascontiguousarray(padded.transpose(2, 0, 1)[None])


# Llevamos los candidatos de las tres vistas al mismo espacio de coordenadas.
def combine_tta(predictions, size, views):
    """Deshacer escalas/volteo y recortar las colas TTA como YOLOv8.

    La red tiene tres escalas de detección, con proporciones de anclas 16:4:1.
    El recorte elimina los extremos que Ultralytics excluye antes de NMS.
    """
    # Acumulamos las salidas corregidas por separado antes de concatenarlas.
    corrected = []
    # Emparejamos cada salida con su escala y su volteo y exigimos el mismo número de elementos.
    for rows, (scale, flip) in zip(predictions, views, strict=True):
        # Copiamos los candidatos para preservar la salida original de la sesión.
        rows = rows.copy()
        # Deshacemos la escala en centro, ancho y alto y conservamos la confianza.
        rows[:, :4] /= scale
        # Consultamos si las coordenadas proceden de la vista invertida.
        if flip:
            # Reflejamos horizontalmente el centro de la caja para recuperar su orientación.
            rows[:, 0] = size - rows[:, 0]
        # Incorporamos las cajas de la vista al conjunto corregido.
        corrected.append(rows)
    # Retiramos la última escala de anclas de la primera vista para replicar el recorte TTA.
    corrected[0] = corrected[0][..., :-(corrected[0].shape[-1] // 21)]
    # Retiramos la primera escala de anclas de la última vista para replicar el mismo protocolo.
    corrected[-1] = corrected[-1][..., corrected[-1].shape[-1] // 21 * 16:]
    # Unimos los candidatos en el último eje para efectuar una sola supresión de cajas.
    return np.concatenate(corrected, axis=-1)


# Convertimos candidatos del grafo en detecciones con geometría y confianza publicables.
def decode(predictions, geometry, confidence, nms_iou, max_det):
    """Filtrar la clase única, aplicar NMS y recuperar coordenadas originales."""
    # Exigimos tres ejes y exactamente un elemento con cinco valores por candidato.
    if predictions.ndim != 3 or predictions.shape[:2] != (1, 5):
        # Interrumpimos la inferencia si el grafo devuelve dimensiones incompatibles.
        raise ValueError(f"Salida inesperada del detector: {predictions.shape}")
    # Quitamos el lote unitario y transponemos para tener un candidato por fila.
    rows = predictions[0].T
    # Conservamos puntuaciones estrictamente superiores al umbral y filas con valores finitos.
    rows = rows[(rows[:, 4] > confidence) & np.isfinite(rows).all(axis=1)]
    # Ordenamos por confianza descendente de forma estable y limitamos el costo de NMS.
    rows = rows[np.argsort(-rows[:, 4], kind="stable")[:30000]]
    # Transformamos cada centro y tamaño en las dos esquinas de la caja.
    boxes = np.column_stack((rows[:, :2] - rows[:, 2:4] / 2, rows[:, :2] + rows[:, 2:4] / 2))
    # Guardamos la confianza en un arreglo paralelo al de coordenadas.
    scores = rows[:, 4]
    # NMS mantiene la caja de mayor puntuación y elimina solapamientos mayores
    # al umbral. Se usa área continua xyxy, igual que el operador de torchvision.
    # Creamos los índices pendientes en el mismo orden de prioridad de las cajas.
    pending = np.arange(len(rows))
    # Reservamos la lista de índices que sobrevivirán a la supresión.
    keep = []
    # Repetimos mientras existan candidatos y no alcancemos el máximo de detecciones.
    while len(pending) and len(keep) < max_det:
        # Seleccionamos el candidato pendiente con mayor confianza.
        current = pending[0]
        # Conservamos el índice seleccionado antes de compararlo con el resto.
        keep.append(current)
        # Separamos los demás índices pendientes para medir el solapamiento.
        remaining = pending[1:]
        # Calculamos la esquina superior izquierda común tomando los máximos por eje.
        top_left = np.maximum(boxes[current, :2], boxes[remaining, :2])
        # Calculamos la esquina inferior derecha común tomando los mínimos por eje.
        bottom_right = np.minimum(boxes[current, 2:], boxes[remaining, 2:])
        # Medimos la intersección y usamos área cero cuando las cajas no se solapan.
        intersection = np.maximum(bottom_right - top_left, 0).prod(axis=1)
        # Calculamos el área de la caja que seleccionamos en esta iteración.
        area = np.maximum(boxes[current, 2:] - boxes[current, :2], 0).prod()
        # Calculamos las áreas de las otras cajas en paralelo.
        other_area = np.maximum(boxes[remaining, 2:] - boxes[remaining, :2], 0).prod(axis=1)
        # Dividimos intersección entre unión y protegemos el denominador frente a cero.
        overlaps = intersection / np.maximum(area + other_area - intersection, 1e-9)
        # Conservamos como pendientes las cajas cuyo IoU no supera el umbral NMS.
        pending = remaining[overlaps <= nms_iou]
    # Convertimos el conjunto conservado en índices enteros incluso cuando esté vacío.
    indices = np.asarray(keep, dtype=int)
    # Filtramos las coordenadas y sus puntuaciones con los mismos índices.
    boxes, scores = boxes[indices], scores[indices]
    # Recuperamos las escalas, posición del relleno y dimensiones del espacio original.
    ratio_x, ratio_y, left, top, width, height = geometry
    # Restamos el desplazamiento del lienzo a ambas esquinas de cada caja.
    boxes = (boxes - np.array([left, top, left, top], dtype=np.float32)) / np.array(
        # Dividimos cada coordenada por la escala efectiva de su eje.
        [ratio_x, ratio_y, ratio_x, ratio_y], dtype=np.float32)
    # Recortamos las coordenadas horizontales a los límites de la imagen analizada.
    boxes[:, 0::2] = np.clip(boxes[:, 0::2], 0, width)
    # Recortamos las coordenadas verticales del mismo modo.
    boxes[:, 1::2] = np.clip(boxes[:, 1::2], 0, height)
    # Entregamos la clase única Bache con el índice 0 y la confianza como float de Python.
    return [{"class_id": 0, "label": "Bache", "confidence": float(score),
             # Adjuntamos las dos esquinas xyxy con valores aptos para serializar en JSON.
             "box_xyxy": [float(value) for value in box]} for box, score in zip(boxes, scores)]


# Encapsulamos metadatos, preparación de vistas y sesión en una instancia reutilizable.
class PredictorBaches:
    """Ejecutar las tres vistas del perfil calibrado del detector."""

    # Inicializamos el predictor con una ruta local de pesos y la política de hilos.
    def __init__(self, ruta, hilos):
        # Cargamos la ficha del modelo que acompaña al archivo ONNX.
        self.metadatos = cargar_metadatos(ruta)
        # Abrimos la sesión con la huella esperada para el archivo seleccionado.
        self.sesion = cargar_sesion(ruta, self.metadatos["sha256"][ruta.name], hilos)
        # Obtenemos el nombre de la entrada directamente del grafo.
        self.entrada = self.sesion.get_inputs()[0].name

    # Recibimos la imagen RGB y permitimos reemplazar la confianza original.
    def predecir(self, imagen, *, umbral=None):
        """Aplicar el umbral indicado o la confianza original del modelo."""
        # Detectamos si el llamador omitió el umbral operativo.
        if umbral is None:
            # Usamos la confianza registrada para la exportación cuando no hay un valor explícito.
            umbral = self.metadatos["confidence"]
        # Leemos el lado de la entrada base del modelo.
        size = self.metadatos["image_size"]
        # Ejecutamos letterbox y conservamos la geometría de retorno.
        tensor, geometria = letterbox(imagen, size)
        # Recuperamos la configuración de aumentos utilizada para la exportación.
        tta = self.metadatos["tta"]
        # Combinamos cada escala con el volteo que le corresponde.
        vistas = list(zip(tta["scales"], tta["horizontal_flip"], strict=True))
        # Reunimos una salida del grafo por cada vista configurada.
        predicciones = [
            # Alimentamos el modelo con una vista aumentada y seleccionamos su primera salida.
            self.sesion.run(None, {self.entrada: augmented_view(tensor, escala, volteo)})[0]
            # Repetimos la inferencia con los parámetros de las tres vistas.
            for escala, volteo in vistas
        ]
        # Aplicamos el posprocesamiento conjunto y devolvemos detecciones finales.
        return decode(
            # Unificamos las vistas antes del filtrado y supresión de cajas.
            combine_tta(predicciones, size, vistas),
            # Pasamos la geometría que permite recuperar las coordenadas.
            geometria,
            # Pasamos el límite operativo de confianza.
            umbral,
            # Aplicamos el umbral de IoU del modelo para eliminar solapamientos.
            self.metadatos["nms_iou"],
            # Aplicamos el máximo de detecciones registrado en los metadatos.
            self.metadatos["max_det"],
        )
