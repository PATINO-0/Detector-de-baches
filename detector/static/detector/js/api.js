/* Enviamos imágenes y preguntas a Django y leemos sus respuestas JSON. */

// Unificamos el tratamiento de respuestas de los dos endpoints.
async function leerRespuesta(respuesta, mensajeAlternativo) {
    // Intentamos interpretar el cuerpo como JSON aunque el servidor responda con error.
    const datos = await respuesta.json().catch(() => null);
    // Consideramos un fallo tanto el estado HTTP desfavorable como un cuerpo ilegible.
    if (!respuesta.ok || !datos) {
        // Preferimos la explicación de Django cuando está disponible.
        throw new Error(datos?.error || mensajeAlternativo);
    }
    // Entregamos los datos válidos a quien solicitó la operación.
    return datos;
}

// Exportamos el cliente del análisis para compartirlo entre foto, ejemplo y cámara.
export async function solicitarAnalisis(formulario, imagen, señal) {
    // Creamos un formulario multipart para enviar el archivo binario.
    const datos = new FormData();
    // Usamos el campo imagen y asignamos un nombre JPEG a los fotogramas anónimos.
    datos.append("imagen", imagen, imagen.name || "fotograma.jpg");

    // Abrimos la solicitud contra la URL que resolvió Django en el formulario.
    const respuesta = await fetch(formulario.action, {
        // Enviamos POST, el método que acepta la ruta de análisis.
        method: "POST",
        // Dejamos que el navegador construya el cuerpo y su separador multipart.
        body: datos,
        // Enviamos en la cabecera el token CSRF que Django insertó en el formulario.
        headers: { "X-CSRFToken": formulario.elements.csrfmiddlewaretoken.value },
        // Asociamos la señal que permite cancelar una solicitud cuando cambia la fuente.
        signal: señal,
    });
    // Entregamos los datos de detección usando el tratamiento común de la API.
    return leerRespuesta(respuesta, "El servidor no pudo completar el análisis.");
}

// Exportamos la descarga del ejemplo para analizarlo como un archivo adicional.
export async function cargarEjemplo(url, señal) {
    // Obtenemos el recurso estático respetando la misma señal de cancelación.
    const respuesta = await fetch(url, { signal: señal });
    // Comprobamos que el recurso se haya servido correctamente.
    if (!respuesta.ok) {
        // Informamos si el ejemplo no está disponible.
        throw new Error("No se pudo cargar la imagen de ejemplo.");
    }
    // Convertimos la respuesta en un Blob para enviarlo por el mismo formulario.
    return respuesta.blob();
}

// Enviamos una pregunta con el resumen firmado de la inspección que la acompaña.
export async function solicitarRespuestaAsistente(formulario, pregunta, contexto) {
    // Hacemos una solicitud separada de la carga de imágenes y de la cámara.
    const respuesta = await fetch(formulario.action, {
        // Usamos el método que espera el endpoint del asistente.
        method: "POST",
        // Declaramos JSON y reutilizamos el token CSRF que emitió Django en este formulario.
        headers: { "Content-Type": "application/json", "X-CSRFToken": formulario.elements.csrfmiddlewaretoken.value },
        // Enviamos texto y un token opcional, sin adjuntar el contenido de la imagen.
        body: JSON.stringify({ pregunta, contexto }),
    });
    // Recuperamos la respuesta redactada o una indicación de error.
    return leerRespuesta(respuesta, "El asistente no pudo responder. Inténtalo de nuevo.");
}
