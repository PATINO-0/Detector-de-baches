"""Composición y codificación de la imagen anotada."""

# Convertimos los bytes de la imagen en texto transportable en JSON.
from base64 import b64encode

# Usamos OpenCV para dibujar marcas y codificar el JPEG.
import cv2
# Usamos NumPy para mezclar colores en los píxeles seleccionados.
import numpy as np


# Definimos el color RGB ámbar de las cajas de baches.
COLOR_BACHE = (255, 182, 74)
# Definimos el color RGB magenta de la máscara de grietas.
COLOR_GRIETA = (255, 61, 128)
# Usamos un tono oscuro para dar contraste al texto sobre la etiqueta ámbar.
COLOR_TEXTO = (28, 23, 14)
# Seleccionamos la tipografía interna que utiliza OpenCV.
TIPOGRAFIA = cv2.FONT_HERSHEY_SIMPLEX


# Recibimos un lienzo mutable y una detección con caja y confianza.
def marcar_bache(imagen, deteccion):
    """Dibujar una caja y su confianza en el sistema de píxeles analizado."""
    # Obtenemos las dimensiones del lienzo para dimensionar y ubicar las marcas.
    alto, ancho = imagen.shape[:2]
    # Redondeamos las esquinas a coordenadas enteras de píxel.
    x1, y1, x2, y2 = map(round, deteccion["box_xyxy"])
    # Dibujamos el contorno con un grosor proporcional y un mínimo de 2 píxeles.
    cv2.rectangle(imagen, (x1, y1), (x2, y2), COLOR_BACHE, max(2, round(max(alto, ancho) / 450)))

    # Convertimos la confianza a porcentaje entero para rotular la caja.
    etiqueta = f"Bache {deteccion['confidence']:.0%}"
    # Escalamos el texto con el lado mayor de la imagen y un tamaño mínimo.
    escala = max(0.43, max(alto, ancho) / 1550)
    # Medimos la etiqueta y su línea de base con el grosor de texto final.
    (ancho_texto, alto_texto), base = cv2.getTextSize(etiqueta, TIPOGRAFIA, escala, 1)
    # Reservamos márgenes alrededor del texto y espacio para la línea de base.
    ancho_etiqueta, alto_etiqueta = ancho_texto + 10, alto_texto + base + 9
    # Limitamos la posición horizontal para mantener el fondo de la etiqueta visible.
    x = min(x1, max(0, ancho - ancho_etiqueta))
    # Ubicamos la etiqueta arriba si cabe y ajustamos su posición al límite inferior.
    y = min(y1 - alto_etiqueta if y1 >= alto_etiqueta else y1, max(0, alto - alto_etiqueta))
    # Dibujamos el fondo sólido de la etiqueta en el mismo color que la caja.
    cv2.rectangle(imagen, (x, y), (x + ancho_etiqueta, y + alto_etiqueta), COLOR_BACHE, cv2.FILLED)
    # Pintamos el texto con márgenes y suavizado de los bordes de las letras.
    cv2.putText(imagen, etiqueta, (x + 5, y + alto_texto + 4), TIPOGRAFIA, escala, COLOR_TEXTO, 1, cv2.LINE_AA)


# Recibimos la imagen original, las cajas y la máscara de grietas.
def imagen_anotada(imagen, baches, mascara):
    """Superponer la máscara de grietas y las cajas de baches en el mismo JPEG."""
    # Copiamos los píxeles para preservar la imagen utilizada por los predictores.
    salida = imagen.copy()
    # Mezclamos el fondo al 40 por ciento y el magenta al 60 por ciento en la máscara.
    salida[mascara] = 0.40 * salida[mascara] + 0.60 * np.asarray(COLOR_GRIETA)
    # Procesamos cada detección para superponer su contorno y su confianza.
    for bache in baches:
        # Dibujamos las cajas después de la máscara para que el rótulo se lea encima.
        marcar_bache(salida, bache)

    # Convertimos RGB al orden BGR que interpreta el codificador de OpenCV.
    bgr = cv2.cvtColor(salida, cv2.COLOR_RGB2BGR)
    # Codificamos la composición como JPEG con calidad 92.
    exito, jpeg = cv2.imencode(".jpg", bgr, [cv2.IMWRITE_JPEG_QUALITY, 92])
    # Verificamos que OpenCV haya generado el archivo codificado.
    if not exito:
        # Informamos un fallo de composición que la vista convierte en error de servicio.
        raise RuntimeError("No se pudo codificar la imagen de resultado.")
    # Construimos una URL de datos JPEG en base64 que el navegador puede mostrar y descargar.
    return "data:image/jpeg;base64," + b64encode(jpeg).decode("ascii")
