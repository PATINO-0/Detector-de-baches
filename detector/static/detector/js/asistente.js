/* Coordinamos el diálogo de inspección y el contexto firmado por Django. */

// Usamos el cliente HTTP común de la aplicación.
import { solicitarRespuestaAsistente } from "./api.js";

// Conservamos el formulario que contiene el endpoint y el token CSRF.
const formulario = document.getElementById("formulario-asistente");
// Localizamos el campo de texto que recibe la pregunta.
const entrada = document.getElementById("pregunta-asistente");
// Conservamos el botón para bloquear solicitudes simultáneas.
const botonEnviar = document.getElementById("enviar-pregunta");
// Obtenemos los tres ejemplos de pregunta que pueden enviarse como atajos.
const sugerencias = Array.from(document.querySelectorAll("#sugerencias-asistente button"));
// Localizamos la lista donde se agregan las intervenciones.
const mensajes = document.getElementById("mensajes-asistente");
// Actualizamos este indicador cuando la fuente de detecciones cambia.
const indicador = document.getElementById("contexto-asistente");
// Usamos la región accesible que anuncia el estado de la consulta.
const estado = document.getElementById("estado-asistente");

// Iniciamos el panel sin inspección asociada a las preguntas.
let inspeccion = { token: null, fuente: "" };
// Admitimos el primer envío antes de que haya una consulta en curso.
let consultando = false;

// Actualizamos la inspección al seleccionar una fuente o terminar de analizarla.
export function actualizarContextoAsistente(token = null, fuente = "") {
    // Sustituimos el objeto para que cada consulta pueda conservar su referencia original.
    inspeccion = { token: token || null, fuente };
    // Nombramos la imagen o cámara que respalda la siguiente pregunta.
    const texto = token ? `Análisis actual · ${fuente}` : "Analiza una imagen para consultar sus detecciones.";
    // Evitamos repetir el mismo aviso visual con cada fotograma de cámara.
    if (indicador.textContent !== texto) indicador.textContent = texto;
}

// Mostramos cada intervención como texto para preservar los datos de entrada del usuario.
function agregarMensaje(autor, texto, fuente = "") {
    // Creamos una fila y asociamos la variante visual con su autor.
    const fila = document.createElement("li");
    // Aplicamos el atributo que usan las reglas de presentación de cada autor.
    fila.dataset.autor = autor;
    // Identificamos el origen del mensaje con un rótulo legible.
    const nombre = document.createElement("strong");
    // Elegimos el texto del autor o el rótulo de aviso cuando hubo un fallo.
    nombre.textContent = autor === "usuario" ? "Tú" : autor === "error" ? "Aviso" : "RoadVision";
    // Insertamos la pregunta o la respuesta mediante la API de texto del DOM.
    const cuerpo = document.createElement("p");
    // Mostramos los caracteres tal como fueron escritos o devueltos por Django.
    cuerpo.textContent = texto;
    // Presentamos primero al autor y después su intervención.
    fila.append(nombre, cuerpo);
    // Mostramos el contexto que se envió aunque ya esté visible otra inspección.
    if (fuente) {
        // Reservamos una línea secundaria para la referencia a la foto o cámara.
        const referencia = document.createElement("small");
        // Identificamos la fuente del contexto que acompañó al texto.
        referencia.textContent = `Contexto de la consulta · ${fuente}`;
        // Añadimos la referencia debajo de la respuesta.
        fila.append(referencia);
    }
    // Incorporamos la intervención a la conversación de esta página.
    mensajes.append(fila);
    // Desplazamos solo la conversación para presentar el intercambio reciente.
    mensajes.scrollTop = mensajes.scrollHeight;
}

// Impedimos envíos simultáneos y comunicamos cuándo está trabajando el asistente.
function actualizarConsulta(ocupada) {
    // Registramos si ya se está clasificando una pregunta.
    consultando = ocupada;
    // Bloqueamos el envío manual mientras la petición siga pendiente.
    botonEnviar.disabled = ocupada;
    // Aplicamos el mismo bloqueo a los atajos de preguntas sugeridas.
    for (const boton of sugerencias) boton.disabled = ocupada;
    // Anunciamos el progreso mediante la región de estado.
    estado.textContent = ocupada ? "Consultando al asistente…" : "";
}

// Resolvemos el formulario sin abandonar la fotografía ni la cámara.
formulario.addEventListener("submit", async (evento) => {
    // Sustituimos el envío HTML por el cliente de consultas JSON.
    evento.preventDefault();
    // Quitamos espacios exteriores y omitimos un envío vacío o duplicado.
    const pregunta = entrada.value.trim();
    // Evitamos el envío de solo espacios y la segunda consulta simultánea.
    if (!pregunta || consultando) return;
    // Fijamos la inspección existente al enviar, especialmente durante el análisis en vivo.
    const contextoPregunta = inspeccion;
    // Hacemos visible la pregunta y dejamos el campo listo para otro texto.
    agregarMensaje("usuario", pregunta);
    // Liberamos el campo para permitir que se escriba la siguiente pregunta.
    entrada.value = "";
    // Bloqueamos el envío hasta que termine esta solicitud.
    actualizarConsulta(true);

    // Esperamos la clasificación y la respuesta en español de Django.
    try {
        // Enviamos la referencia fijada al comenzar la consulta.
        const datos = await solicitarRespuestaAsistente(formulario, pregunta, contextoPregunta.token);
        // Presentamos el texto junto con la fuente usada en esa consulta.
        agregarMensaje("asistente", datos.respuesta, contextoPregunta.fuente);
    } catch (error) {
        // Informamos del fallo en el panel del asistente y permitimos volver a enviar.
        const mensaje = error instanceof TypeError ? "No se pudo conectar con el asistente." : error.message;
        // Presentamos problemas del asistente dentro de la conversación.
        agregarMensaje("error", mensaje);
        // Restauramos la pregunta si el usuario todavía no ha escrito otra.
        if (!entrada.value) entrada.value = pregunta;
    } finally {
        // Liberamos el formulario después de recibir una respuesta o un error.
        actualizarConsulta(false);
    }
});

// Enviamos las preguntas predefinidas mediante el mismo formulario validado.
for (const boton of sugerencias) {
    // Usamos el texto definido en la plantilla como valor de la pregunta.
    boton.addEventListener("click", () => {
        // Copiamos el atajo al mismo campo que usa la consulta manual.
        entrada.value = boton.dataset.pregunta;
        // Conservamos la validación del campo y el recorrido del evento de formulario.
        formulario.requestSubmit();
    });
}
