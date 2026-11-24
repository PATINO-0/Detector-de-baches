"""Segmentación de grietas con el perfil original de CrackUNet."""

# Usamos OpenCV para dimensionar la imagen y el mapa de probabilidades.
import cv2
# Construimos arreglos numéricos y tensores para ONNX Runtime.
import numpy as np

# Reutilizamos la lectura de metadatos y la carga verificada de grafos ONNX.
from .onnx import cargar_metadatos, cargar_sesion


# Encapsulamos en esta clase la preparación, ejecución y segmentación de grietas.
class PredictorGrietas:
    """Identificar los píxeles con probabilidad de grieta sobre el umbral."""

    # Inicializamos una instancia con el archivo local y el presupuesto de hilos.
    def __init__(self, ruta, hilos):
        # Cargamos la configuración del JSON que acompaña al modelo.
        self.metadatos = cargar_metadatos(ruta)
        # Abrimos la sesión CPU y validamos los bytes con el SHA-256 esperado.
        self.sesion = cargar_sesion(ruta, self.metadatos["onnx_sha256"], hilos)

    # Recibimos la matriz RGB y un umbral de operación opcional.
    def predecir(self, imagen, *, umbral=None):
        """Aplicar el umbral indicado o el valor calibrado del modelo."""
        # Consultamos si el llamador pidió conservar el umbral de la ficha del modelo.
        if umbral is None:
            # Recuperamos el umbral original cuando se usa el predictor directamente.
            umbral = self.metadatos["threshold"]
        # Leemos el lado del cuadrado que espera el modelo.
        lado = self.metadatos["image_size"]
        # Obtenemos las dimensiones de la foto recibida por el predictor.
        alto, ancho = imagen.shape[:2]
        # Calculamos una escala uniforme para ajustar el lado mayor.
        escala = lado / max(alto, ancho)
        # Redondeamos las dimensiones y conservamos al menos un píxel por eje.
        nuevo_ancho, nuevo_alto = max(1, round(ancho * escala)), max(1, round(alto * escala))
        # Calculamos los desplazamientos para centrar el contenido sobre el relleno.
        x, y = (lado - nuevo_ancho) // 2, (lado - nuevo_alto) // 2
        # Guardamos las rebanadas que ocupan los píxeles reales dentro del cuadrado.
        region = np.s_[y:y + nuevo_alto, x:x + nuevo_ancho]

        # Creamos el lienzo RGB de 8 bits con el gris indicado en los metadatos.
        lienzo = np.full((lado, lado, 3), self.metadatos["input"]["letterbox_pad"], dtype=np.uint8)
        # Aplicamos interpolación lineal y colocamos la foto reducida en su región.
        lienzo[region] = cv2.resize(imagen, (nuevo_ancho, nuevo_alto), interpolation=cv2.INTER_LINEAR)
        # Convertimos HWC a NCHW con un lote, datos float32 contiguos y valores de 0 a 1.
        entrada = np.ascontiguousarray(lienzo.transpose(2, 0, 1)[None], dtype=np.float32) / 255
        # Pedimos la salida probabilities y extraemos el único mapa del único elemento.
        probabilidades = self.sesion.run(["probabilities"], {"images": entrada})[0][0, 0]

        # Retirar el relleno y recuperar la geometría antes de binarizar.
        # Recortamos a la región real y reescalamos las probabilidades a la foto analizada.
        probabilidades = cv2.resize(probabilidades[region], (ancho, alto), interpolation=cv2.INTER_LINEAR)
        # Devolvemos una máscara booleana que incluye los valores iguales al umbral.
        return probabilidades >= umbral
