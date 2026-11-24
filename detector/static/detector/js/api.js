/* Enviar imágenes a Django y recuperar la respuesta de ambos modelos. */

export async function solicitarAnalisis(formulario, imagen, señal) {
    const datos = new FormData();
    datos.append("imagen", imagen, imagen.name || "fotograma.jpg");

    const respuesta = await fetch(formulario.action, {
        method: "POST",
        body: datos,
        headers: { "X-CSRFToken": formulario.elements.csrfmiddlewaretoken.value },
        signal: señal,
    });
    const resultado = await respuesta.json().catch(() => null);
    if (!respuesta.ok || !resultado) {
        if (respuesta.status === 413 && !resultado?.error) {
            throw new Error(`La imagen debe pesar como máximo ${formulario.dataset.maxMb} MB.`);
        }
        throw new Error(resultado?.error || "El servidor no pudo completar el análisis.");
    }
    return resultado;
}

export async function cargarEjemplo(url, señal) {
    const respuesta = await fetch(url, { signal: señal });
    if (!respuesta.ok) {
        throw new Error("No se pudo cargar la imagen de ejemplo.");
    }
    return respuesta.blob();
}
