"""Ejecutamos el clasificador Transformer V4 en CPU mediante ONNX Runtime."""

# Conservamos la sesión cargada en memoria con una caché de la biblioteca estándar.
from functools import lru_cache
# Coordinamos la primera petición concurrente de cada proceso.
from threading import Lock

# Construimos el lote de identificadores enteros que recibe el grafo.
import numpy as np

# Reutilizamos la carga de metadatos y la comprobación SHA-256 de los otros modelos.
from ..inferencia.onnx import cargar_metadatos, cargar_sesion
# Aplicamos exactamente el vocabulario BPE de la exportación.
from .tokenizador import TokenizadorBPE


# Serializamos el acceso que puede crear la sesión inicial del asistente.
candado_asistente = Lock()


# Representamos una sesión de clasificación y su esquema de etiquetas.
class ModeloAsistente:
    """Obtenemos la intención o el rechazo de dominio junto a su puntuación."""

    # Cargamos el grafo ya entrenado con su configuración y sus fusiones.
    def __init__(self, ruta, hilos):
        # Buscamos el JSON de vocabulario y etiquetas junto al archivo ONNX.
        meta = cargar_metadatos(ruta)
        # Exigimos la versión compatible con este tokenizador y contrato de inferencia.
        if meta["version"] != 4:
            # Indicamos qué paquete se debe usar antes de inicializar la sesión.
            raise ValueError("El asistente requiere un Transformer RoadVision V4.")
        # Usamos las etiquetas originales para interpretar la salida numérica.
        self.etiquetas = meta["labels"]
        # Creamos el tokenizador con los mismos 48 espacios del modelo entrenado.
        self.tokenizador = TokenizadorBPE(meta["vocab"], meta["merges"], meta["model"]["max_len"])
        # Comprobamos el SHA-256 antes de abrir la sesión de inferencia en CPU.
        self.sesion = cargar_sesion(ruta, meta["exportacion"]["onnx_sha256"], hilos)

    # Clasificamos una sola pregunta para el flujo web.
    def predecir(self, pregunta):
        # Codificamos el texto antes de enviarlo al Transformer.
        ids = self.tokenizador.codificar(pregunta)
        # Conservamos el rechazo del modelo original para frases sin tokens.
        if ids is None:
            # Devolvemos la etiqueta de rechazo y la misma puntuación de referencia.
            return "fuera_de_dominio", 0.0
        # Ejecutamos la sesión para un lote de una pregunta.
        clases, puntuaciones = self.sesion.run(
            # Pedimos el índice ya calibrado y su puntuación de decisión.
            ["intencion", "confianza"],
            # Enviamos los 48 identificadores como enteros de 64 bits.
            {"ids": np.asarray([ids], dtype=np.int64)},
        )
        # Resolvemos la intención y su probabilidad de decisión con los índices originales.
        return self.etiquetas[int(clases[0])], float(puntuaciones[0])


# Reutilizamos la sesión mientras la ruta y la configuración de hilos coincidan.
@lru_cache(maxsize=1)
# Aceptamos la ruta del grafo y el límite de hilos como clave de esa caché.
def cargar_asistente(ruta, hilos):
    # Inicializamos únicamente cuando llega la primera consulta.
    return ModeloAsistente(ruta, hilos)


# Obtenemos la sesión sin mantener el candado durante la clasificación.
def clasificar_consulta(pregunta, directorio, hilos):
    # Protegemos una posible carga concurrente del mismo modelo.
    with candado_asistente:
        # Localizamos los artefactos del asistente dentro del directorio de modelos.
        modelo = cargar_asistente(directorio / "asistente" / "transformer.onnx", hilos)
    # Devolvemos la decisión utilizando los pesos entrenados del paquete V4.
    return modelo.predecir(pregunta)
