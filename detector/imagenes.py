"""Validación, decodificación y preparación de las imágenes recibidas."""

# Usamos NumPy para entregar los píxeles como matriz.
import numpy as np
# Reutilizamos los límites definidos por Django para validar las cargas.
from django.conf import settings
# Extendemos el mecanismo de subida y usamos su excepción de interrupción.
from django.core.files.uploadhandler import FileUploadHandler, StopUpload
# Usamos Pillow para decodificar formatos y aplicar la orientación EXIF.
from PIL import Image, ImageOps


# Definimos la familia de errores de imagen que la vista puede presentar al usuario.
class ImagenInvalida(ValueError):
    """Error de entrada con un mensaje que puede mostrarse al usuario."""


# Distinguimos los límites de tamaño de los demás errores de entrada.
class ImagenDemasiadoGrande(ImagenInvalida):
    """La imagen supera el presupuesto de bytes o píxeles."""


# Interponemos un manejador antes de que Django almacene el archivo completo.
class LimiteCargaImagen(FileUploadHandler):
    """Interrumpir el almacenamiento de un archivo que sobrepasa el límite."""

    # Recibimos cada bloque binario y su posición dentro del archivo.
    def receive_data_chunk(self, raw_data, start):
        # Sumamos la posición y la longitud para detectar el primer bloque que excede el límite.
        if start + len(raw_data) > settings.MAX_BYTES_IMAGEN:
            # Registramos el motivo de la interrupción en la petición actual.
            self.request.imagen_demasiado_grande = True
            # Detenemos la escritura y permitimos que Django termine de consumir la solicitud.
            raise StopUpload(connection_reset=False)
        # Pasamos el bloque admitido al siguiente manejador de la cadena.
        return raw_data

    # Atendemos el aviso de que terminó un archivo recibido.
    def file_complete(self, file_size):
        # Dejamos que el siguiente manejador construya el objeto UploadedFile.
        return None


# Tomamos un archivo de Django para obtener la matriz que recibe el servicio.
def leer_imagen(archivo):
    """Obtener RGB de una imagen estática respetando su orientación EXIF."""
    # Volvemos a validar el tamaño al acceder al contenido del archivo.
    if archivo.size > settings.MAX_BYTES_IMAGEN:
        # Comunicamos el máximo admitido por la aplicación para el archivo.
        raise ImagenDemasiadoGrande("La imagen debe pesar como máximo 10 MB.")

    # Separamos la apertura y transformación de los errores que puede emitir Pillow.
    try:
        # Abrimos el flujo con una lista explícita de formatos aceptados.
        with Image.open(archivo, formats=("JPEG", "PNG", "WEBP")) as imagen:
            # Inspeccionamos las dimensiones antes de aplicar las transformaciones.
            if imagen.width * imagen.height > settings.MAX_PIXELES_IMAGEN:
                # Rechazamos la imagen si su superficie supera el presupuesto de píxeles.
                raise ImagenDemasiadoGrande("La imagen debe tener como máximo 24 megapíxeles.")
            # Consultamos si el contenedor tiene fotogramas animados.
            if getattr(imagen, "is_animated", False):
                # Pedimos una imagen estática para conservar un análisis de una sola escena.
                raise ImagenInvalida("Selecciona una imagen estática en JPG, PNG o WebP.")
            # Aplicamos el giro o reflejo indicado por la orientación EXIF.
            imagen = ImageOps.exif_transpose(imagen)
            # Reducimos el tamaño, si hace falta, manteniendo la relación de aspecto.
            imagen.thumbnail((settings.MAX_LADO_ANALISIS, settings.MAX_LADO_ANALISIS))
            # Entregamos el contenido como una matriz alto por ancho por 3 canales RGB.
            return np.asarray(imagen.convert("RGB"))
    # Reconocemos la señal de Pillow para imágenes de dimensiones excesivas.
    except Image.DecompressionBombError as error:
        # Exponemos el límite de píxeles y conservamos la causa para diagnóstico.
        raise ImagenDemasiadoGrande("La imagen debe tener como máximo 24 megapíxeles.") from error
    # Convertimos fallos de lectura y sintaxis en un error de entrada controlado.
    except (OSError, SyntaxError) as error:
        # Pedimos uno de los formatos admitidos y conservamos la excepción original.
        raise ImagenInvalida("No se pudo leer la imagen. Usa un archivo JPG, PNG o WebP válido.") from error
