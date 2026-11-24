/* Enviar imágenes a Django y recuperar la respuesta de ambos modelos. */

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
    // Intentamos interpretar el cuerpo como JSON aunque el servidor responda con error.
    const resultado = await respuesta.json().catch(() => null);
    // Consideramos un fallo tanto el estado HTTP desfavorable como una respuesta ilegible.
    if (!respuesta.ok || !resultado) {
        // Preferimos el mensaje de Django o usamos una explicación cuando no hay JSON útil.
        throw new Error(resultado?.error || "El servidor no pudo completar el análisis.");
    }
    // Entregamos los datos de detección a la interfaz.
    return resultado;
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
