"""Validación, decodificación y preparación de las imágenes recibidas."""

import numpy as np
from django.conf import settings
from django.core.files.uploadhandler import FileUploadHandler, StopUpload
from PIL import Image, ImageOps


class ImagenInvalida(ValueError):
    """Error de entrada con un mensaje que puede mostrarse al usuario."""


class ImagenDemasiadoGrande(ImagenInvalida):
    """La imagen supera el presupuesto de bytes o píxeles."""


def mensaje_limite_archivo():
    return f"La imagen debe pesar como máximo {settings.MAX_MB_IMAGEN} MB."


class LimiteCargaImagen(FileUploadHandler):
    """Interrumpir el almacenamiento de un archivo que sobrepasa el límite."""

    def receive_data_chunk(self, raw_data, start):
        if start + len(raw_data) > settings.MAX_BYTES_IMAGEN:
            self.request.imagen_demasiado_grande = True
            raise StopUpload(connection_reset=False)
        return raw_data

    def file_complete(self, file_size):
        return None


def leer_imagen(archivo):
    """Obtener RGB de una imagen estática respetando su orientación EXIF."""
    if archivo.size > settings.MAX_BYTES_IMAGEN:
        raise ImagenDemasiadoGrande(mensaje_limite_archivo())

    try:
        with Image.open(archivo, formats=("JPEG", "PNG", "WEBP")) as imagen:
            if imagen.width * imagen.height > settings.MAX_PIXELES_IMAGEN:
                raise ImagenDemasiadoGrande("La imagen debe tener como máximo 24 megapíxeles.")
            if getattr(imagen, "is_animated", False):
                raise ImagenInvalida("Selecciona una imagen estática en JPG, PNG o WebP.")
            imagen = ImageOps.exif_transpose(imagen)
            imagen.thumbnail((settings.MAX_LADO_ANALISIS, settings.MAX_LADO_ANALISIS))
            return np.asarray(imagen.convert("RGB"))
    except Image.DecompressionBombError as error:
        raise ImagenDemasiadoGrande("La imagen debe tener como máximo 24 megapíxeles.") from error
    except (OSError, SyntaxError) as error:
        raise ImagenInvalida("No se pudo leer la imagen. Usa un archivo JPG, PNG o WebP válido.") from error
