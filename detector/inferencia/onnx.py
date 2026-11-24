"""Carga en CPU y comprobación de integridad de los pesos exportados."""

# Calculamos la huella criptográfica de cada archivo de pesos.
import hashlib
# Leemos la configuración JSON asociada a las exportaciones.
import json

# Usamos el motor que ejecuta los grafos ONNX en Python.
import onnxruntime as ort


# Resolvemos la configuración del modelo a partir de la ruta del archivo.
def cargar_metadatos(ruta):
    # Sustituimos la extensión por .json, leemos el texto UTF-8 y lo interpretamos.
    return json.loads(ruta.with_suffix(".json").read_text(encoding="utf-8"))


# Recibimos el archivo ONNX, la huella esperada y los hilos de CPU.
def cargar_sesion(ruta, sha256, hilos):
    # Cargamos los bytes del grafo local antes de instanciar el motor de inferencia.
    grafo = ruta.read_bytes()
    # Comparamos la huella calculada con la de la exportación original.
    if hashlib.sha256(grafo).hexdigest() != sha256:
        # Rechazamos un archivo incompatible o alterado e identificamos su nombre.
        raise ValueError(f"El SHA-256 de {ruta.name} no coincide con sus metadatos.")

    # Creamos las opciones que enviamos al motor de inferencia.
    opciones = ort.SessionOptions()
    # Limitamos cuántos hilos usa cada operación dentro de la sesión.
    opciones.intra_op_num_threads = hilos
    # Creamos la sesión verificada usando explícitamente el proveedor de CPU.
    return ort.InferenceSession(grafo, sess_options=opciones, providers=["CPUExecutionProvider"])
