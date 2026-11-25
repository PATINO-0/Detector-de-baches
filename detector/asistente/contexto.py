"""Firmamos un resumen del análisis para responder sin guardar imágenes ni historial."""

# Agrupamos las cajas por zona mediante un contador.
from collections import Counter
# Calculamos la confianza promedio con la media para valores de punto flotante.
from statistics import fmean

# Usamos el firmador de Django para autenticar el resumen entre solicitudes.
from django.core import signing


# Separamos las firmas del asistente de otros usos de la clave de Django.
SALT_CONTEXTO = "roadvision.asistente.resultado.v1"
# Nombramos las tres franjas horizontales del encuadre.
FILAS = ("superior", "central", "inferior")
# Nombramos las tres posiciones horizontales dentro de cada franja.
COLUMNAS = ("izquierda", "central", "derecha")


# Traducimos el centro de una caja a una de nueve zonas de la imagen.
def zona_bache(caja, ancho, alto):
    # Obtenemos las esquinas en la resolución que analizó Django.
    x1, y1, x2, y2 = caja
    # Convertimos la posición horizontal relativa a un índice de columna.
    columna = min(2, int(3 * (x1 + x2) / (2 * ancho)))
    # Convertimos la posición vertical relativa a un índice de fila.
    fila = min(2, int(3 * (y1 + y2) / (2 * alto)))
    # Damos a la intersección central un nombre que evita repetir los dos ejes.
    if fila == columna == 1:
        # Identificamos la zona donde coinciden la fila y la columna centrales.
        return "el centro de la imagen"
    # Describimos las otras zonas con sus posiciones vertical y horizontal.
    return f"la zona {FILAS[fila]} {COLUMNAS[columna]}"


# Preparamos un contexto compacto a partir de detecciones generadas por el servidor.
def firmar_resultado(resultado):
    # Usamos las cajas finales devueltas por el servicio de imágenes.
    baches = resultado["baches"]
    # Convertimos sus centros en zonas de la resolución que analizó el detector.
    ancho, alto = resultado["ancho"], resultado["alto"]
    # Contamos cuántos centros de cajas caen en cada zona para evitar listas largas.
    ubicaciones = Counter(zona_bache(bache["box_xyxy"], ancho, alto) for bache in baches)
    # Seleccionamos únicamente los datos que pueden aparecer en una respuesta.
    contexto = {
        # Contamos las cajas de baches que pasaron el posprocesamiento.
        "cantidad_baches": len(baches),
        # Conservamos la presencia de grietas, incluso con coberturas muy pequeñas.
        "hay_grietas": resultado["grietas"]["detectadas"],
        # Conservamos el porcentaje de píxeles marcados antes de la anotación.
        "cobertura_grietas_pct": resultado["grietas"]["cobertura"],
        # Calculamos el promedio solamente cuando tenemos detecciones de baches.
        "confianza_baches_promedio": fmean(bache["confidence"] for bache in baches) if baches else None,
        # Conservamos los conteos por zona para responder preguntas de ubicación.
        "ubicaciones_baches": dict(ubicaciones),
    }
    # Firmamos y comprimimos el resumen que devolvemos junto al resultado.
    return signing.dumps(contexto, salt=SALT_CONTEXTO, compress=True)


# Recuperamos el contexto sólo después de verificar la firma del servidor.
def abrir_contexto(token):
    # Permitimos preguntas generales sin haber ejecutado antes un análisis.
    return signing.loads(token, salt=SALT_CONTEXTO) if token else None
