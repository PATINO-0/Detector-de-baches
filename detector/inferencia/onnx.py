"""Carga en CPU y comprobación de integridad de los pesos exportados."""

import hashlib
import json

import onnxruntime as ort


def cargar_metadatos(ruta):
    return json.loads(ruta.with_suffix(".json").read_text(encoding="utf-8"))


def cargar_sesion(ruta, sha256, hilos, *, leer_pesos=None):
    """Validar el grafo local o descargado antes de abrir la sesión ONNX."""
    grafo = ruta.read_bytes() if leer_pesos is None else leer_pesos(ruta.name)
    if hashlib.sha256(grafo).hexdigest() != sha256:
        raise ValueError(f"El SHA-256 de {ruta.name} no coincide con sus metadatos.")

    opciones = ort.SessionOptions()
    opciones.intra_op_num_threads = hilos
    return ort.InferenceSession(grafo, sess_options=opciones, providers=["CPUExecutionProvider"])
