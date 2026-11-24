/* Coordinar la fuente, la vista y el estado de cada análisis. */

// Importamos la descarga del ejemplo y el envío a la API.
import { cargarEjemplo, solicitarAnalisis } from "./api.js";
// Importamos la clase que controla el dispositivo de vídeo.
import { Camara } from "./camara.js";

// Centralizamos el acceso a elementos de la plantilla por su identificador.
const elemento = (id) => document.getElementById(id);
// Guardamos el formulario que contiene la URL, el token y el límite de archivo.
const formulario = elemento("formulario");
// Guardamos el elemento que muestra la foto de origen.
const original = elemento("imagen-original");
// Guardamos el elemento que presenta el JPEG devuelto por Django.
const anotada = elemento("imagen-resultado");
// Guardamos el elemento que reproduce el flujo de la cámara.
const video = elemento("video");
// Guardamos el selector nativo de archivos del navegador.
const archivo = elemento("archivo");
// Guardamos la zona donde se puede soltar una imagen.
const zonaArchivo = elemento("zona-archivo");
// Guardamos el enlace que permitirá descargar el resultado anotado.
const descarga = elemento("descargar-resultado");
// Guardamos la región accesible donde notificamos el estado de la operación.
const estado = elemento("estado");
// Formateamos proporciones como porcentajes en español de Colombia con hasta dos decimales.
const porcentaje = new Intl.NumberFormat("es-CO", { style: "percent", maximumFractionDigits: 2 });

// Instanciamos el controlador del visor y registramos la reacción ante una desconexión.
const camara = new Camara(video, () => {
    // Liberamos la cámara y las tareas pendientes si el dispositivo se desconecta.
    apagarCamara();
    // Mostramos una explicación de la interrupción como error.
    informar("La cámara se desconectó.", true);
});

// Empezamos en la fuente de archivos.
let modo = "archivo";
// Empezamos mostrando el contenido original.
let vista = "original";
// Reservamos el archivo seleccionado y usamos null para representar el ejemplo.
let imagenElegida = null;
// Guardamos la URL de objeto que concede acceso temporal a la vista previa local.
let urlOriginal = null;
// Guardamos la última respuesta del análisis para actualizar métricas y visor.
let resultado = null;
// Guardamos el controlador de la petición activa para impedir llamadas simultáneas.
let solicitud = null;
// Identificamos una activación de cámara pendiente con un símbolo.
let inicioCamara = null;
// Guardamos la sesión de análisis periódico y el temporizador de su próxima captura.
let sesionEnVivo = null;

// Actualizamos el texto de estado y admitimos una presentación de error.
function informar(mensaje = "", error = false) {
    // Ponemos el indicador que usa CSS para diferenciar el error.
    estado.dataset.error = String(error);
    // Evitamos volver a anunciar un mensaje idéntico en la región accesible.
    if (estado.textContent !== mensaje) estado.textContent = mensaje;
}

// Sincronizamos el contenido visible y la resolución del visor.
function actualizarVisor() {
    // Comprobamos si realmente tenemos un flujo de vídeo abierto.
    const camaraActiva = Boolean(camara.flujo);
    // Mostramos detecciones solo cuando el usuario eligió la vista y existe una respuesta.
    const verDetecciones = vista === "resultado" && Boolean(resultado);
    // Mostramos la foto original únicamente si es la fuente activa y corresponde a la vista.
    original.hidden = modo !== "archivo" || verDetecciones;
    // Mostramos u ocultamos el JPEG anotado según la vista que resolvimos.
    anotada.hidden = !verDetecciones;
    // Mantener el vídeo activo detrás del resultado para capturar el siguiente fotograma.
    // Mostramos el vídeo cuando la cámara es la fuente activa, incluso detrás de la anotación.
    video.hidden = modo !== "camara" || !camaraActiva;
    // Ocultamos el vídeo a los lectores de pantalla cuando el resultado está encima.
    video.setAttribute("aria-hidden", String(verDetecciones));
    // Advertimos que falta activar la cámara solo si todavía no hay vídeo ni anotación.
    elemento("camara-sin-video").hidden = modo !== "camara" || camaraActiva || verDetecciones;
    // Reflejamos la selección de la vista original mediante aria-pressed.
    elemento("ver-original").setAttribute("aria-pressed", String(!verDetecciones));
    // Reflejamos la selección de detecciones de la misma forma.
    elemento("ver-resultado").setAttribute("aria-pressed", String(verDetecciones));
    // Deshabilitamos detecciones hasta que haya un análisis disponible.
    elemento("ver-resultado").disabled = !resultado;

    // Leemos el ancho de la imagen anotada, la fotografía original o el vídeo.
    const ancho = verDetecciones ? resultado.ancho : modo === "archivo" ? original.naturalWidth : video.videoWidth;
    // Seleccionamos el alto con el mismo criterio que el ancho.
    const alto = verDetecciones ? resultado.alto : modo === "archivo" ? original.naturalHeight : video.videoHeight;
    // Presentamos la resolución solo cuando conocemos ambos valores.
    elemento("resolucion").textContent = ancho && alto ? `${ancho} × ${alto} px` : "";
}

// Sincronizamos los botones con la fuente y las operaciones activas.
function actualizarControles() {
    // Consultamos si la cámara tiene un flujo que se pueda utilizar.
    const camaraActiva = Boolean(camara.flujo);
    // Consultamos si está activo el análisis continuo de fotogramas.
    const enVivo = Boolean(sesionEnVivo);
    // Consultamos si se está preparando o enviando una solicitud.
    const ocupado = Boolean(solicitud);
    // Mostramos los controles de carga en el modo archivo.
    elemento("controles-archivo").hidden = modo !== "archivo";
    // Mostramos los controles de captura en el modo cámara.
    elemento("controles-camara").hidden = modo !== "camara";
    // Indicamos al lector de pantalla cuándo está seleccionado el botón Archivo.
    elemento("modo-archivo").setAttribute("aria-pressed", String(modo === "archivo"));
    // Indicamos del mismo modo la selección del botón Cámara web.
    elemento("modo-camara").setAttribute("aria-pressed", String(modo === "camara"));
    // Ofrecemos volver al ejemplo cuando hay un archivo personalizado seleccionado.
    elemento("usar-ejemplo").hidden = !imagenElegida;
    // Bloqueamos un segundo envío de archivo mientras exista una solicitud activa.
    elemento("analizar-archivo").disabled = ocupado;
    // Cambiamos el texto del botón para reflejar el progreso.
    elemento("analizar-archivo").textContent = ocupado ? "Analizando…" : "Analizar imagen";

    // Ocultamos el botón de activación si la cámara ya está disponible.
    elemento("activar-camara").hidden = camaraActiva;
    // Impedimos una segunda petición de permiso durante la activación.
    elemento("activar-camara").disabled = Boolean(inicioCamara);
    // Marcamos el botón como pendiente mientras el navegador abre la cámara.
    elemento("activar-camara").textContent = inicioCamara ? "Abriendo cámara…" : "Activar cámara";
    // Ofrecemos apagar la cámara si tenemos un flujo abierto.
    elemento("cerrar-camara").hidden = !camaraActiva;
    // Ofrecemos la captura puntual si tenemos una cámara activa.
    elemento("capturar-fotograma").hidden = !camaraActiva;
    // Evitamos capturas puntuales durante un análisis en curso o en vivo.
    elemento("capturar-fotograma").disabled = ocupado || enVivo;
    // Mostramos el botón de análisis en vivo cuando tenemos cámara.
    elemento("analizar-en-vivo").hidden = !camaraActiva;
    // Impedimos iniciar el bucle durante una petición puntual y permitimos detenerlo cuando ya está activo.
    elemento("analizar-en-vivo").disabled = ocupado && !enVivo;
    // Identificamos con el texto si el botón iniciará o detendrá el análisis en vivo.
    elemento("analizar-en-vivo").textContent = enVivo ? "Detener análisis en vivo" : "Analizar en vivo";
    // Seleccionamos la ayuda contextual según el estado de la cámara.
    elemento("ayuda-camara").textContent = camaraActiva
        // Pedimos elegir una forma de análisis después de abrir el vídeo.
        ? "Apunta al pavimento y elige cómo analizar la imagen."
        // Indicamos cómo preparar la cámara mientras está apagada.
        : "Activa la cámara y apunta hacia el pavimento.";
}

// Limpiamos las detecciones de una fuente o captura anterior.
function borrarResultado() {
    // Quitamos la última respuesta de la memoria de la interfaz.
    resultado = null;
    // Volvemos al contenido original mientras esperamos otro análisis.
    vista = "original";
    // Retiramos la referencia del elemento de imagen anotada.
    anotada.removeAttribute("src");
    // Retiramos la URL que permitía descargar el resultado anterior.
    descarga.removeAttribute("href");
    // Ocultamos el enlace de descarga hasta tener otro resultado.
    descarga.hidden = true;
    // Mostramos un guion para indicar que falta calcular la cantidad de baches.
    elemento("cantidad-baches").textContent = "—";
    // Mostramos un guion mientras aún no se calcula el área de grietas.
    elemento("cobertura-grietas").textContent = "—";
    // Ocultamos el detalle cuando todavía no hay detecciones que presentar.
    elemento("detalle-baches").hidden = true;
    // Volvemos a cerrar el desplegable para el próximo resultado.
    elemento("detalle-baches").open = false;
    // Vaciamos la lista de confianzas de las cajas anteriores.
    elemento("lista-baches").replaceChildren();
    // Recuperamos la indicación inicial junto al panel de resultados.
    elemento("resumen-resultado").textContent = "Analiza una imagen para ver las detecciones.";
    // Actualizamos la imagen visible y el estado de su selector tras el reinicio.
    actualizarVisor();
}

// Renderizamos una respuesta nueva y recibimos la preferencia de cambiar de vista.
function mostrarResultado(datos, cambiarVista) {
    // Conservamos el resultado para futuras comparaciones y actualizaciones del visor.
    resultado = datos;
    // Seleccionamos detecciones cuando el modo de análisis así lo solicita.
    if (cambiarVista) vista = "resultado";
    // Asignamos al visor el JPEG codificado que devolvió Django.
    anotada.src = datos.imagen;
    // Usamos la misma URL de datos como destino de la descarga.
    descarga.href = datos.imagen;
    // Hacemos visible el enlace porque ya hay un resultado válido.
    descarga.hidden = false;

    // Calculamos el número de baches a partir de la cantidad de cajas.
    const baches = datos.baches.length;
    // Leemos la cobertura y la presencia de píxeles marcados en la máscara.
    const { cobertura, detectadas } = datos.grietas;
    // Mostramos el conteo que calculamos a partir de las cajas.
    elemento("cantidad-baches").textContent = baches;
    // Distinguimos las detecciones menores que la resolución decimal visible.
    elemento("cobertura-grietas").textContent = detectadas && cobertura < 0.01
        // Mostramos un rango de cobertura cuando existe una grieta por debajo de 0,01 por ciento.
        ? "<0,01 %"
        // Convertimos el porcentaje del servidor a la proporción que espera el formateador.
        : porcentaje.format(cobertura / 100);
    // Seleccionamos una explicación distinta según se hayan detectado daños.
    elemento("resumen-resultado").textContent = baches || detectadas
        // Cuando hay daños, aclaramos que la cobertura describe una parte de la imagen.
        ? "La cobertura indica la proporción de la imagen cubierta por grietas."
        // Cuando las dos salidas están vacías, indicamos que los modelos no marcaron daños.
        : "Los modelos no detectaron baches ni grietas en esta imagen.";
    // Ocultamos la lista expandible cuando no tenemos cajas de baches.
    elemento("detalle-baches").hidden = !baches;
    // Sustituimos la lista con un elemento nuevo por cada detección.
    elemento("lista-baches").replaceChildren(...datos.baches.map((bache) => {
        // Creamos una fila de la lista para esta caja.
        const fila = document.createElement("li");
        // Insertamos la confianza como texto formateado en porcentaje.
        fila.textContent = `${porcentaje.format(bache.confidence)} de confianza`;
        // Entregamos el nodo al conjunto de filas que se insertará.
        return fila;
    }));
    // Refrescamos la imagen, la resolución y los botones después de pintar los datos.
    actualizarVisor();
}

// Cancelamos el ciclo de captura y la solicitud activa del navegador.
function detenerAnalisis() {
    // Eliminamos la próxima captura programada si existe.
    clearTimeout(sesionEnVivo?.temporizador);
    // Invalidamos la sesión para que una captura anterior no reprograme el bucle.
    sesionEnVivo = null;
    // Pedimos cancelar la petición que permanece activa en el navegador.
    solicitud?.abort();
    // Liberamos el identificador de solicitud para admitir una operación nueva.
    solicitud = null;
    // Volvemos a calcular qué acciones pueden seleccionarse.
    actualizarControles();
}

// Seleccionamos una foto nueva o cambiamos de vuelta al ejemplo.
function elegirImagen(nuevaImagen) {
    // Cancelamos los análisis de la fuente anterior.
    detenerAnalisis();
    // Registramos qué objeto File debe procesarse.
    imagenElegida = nuevaImagen;
    // Liberamos la URL de objeto de la foto anterior para evitar retenerla en memoria.
    if (urlOriginal) URL.revokeObjectURL(urlOriginal);
    // Creamos una URL de vista previa solamente cuando elegimos un archivo local.
    urlOriginal = nuevaImagen ? URL.createObjectURL(nuevaImagen) : null;
    // Mostramos la foto local si existe y usamos el ejemplo como alternativa.
    original.src = urlOriginal || formulario.dataset.ejemplo;
    // Etiquetamos el origen con el nombre del archivo o una indicación de ejemplo.
    elemento("nombre-fuente").textContent = nuevaImagen?.name || "Imagen de ejemplo";
    // Retiramos resultados que pertenecían a otra imagen.
    borrarResultado();
    // Limpiamos avisos de la operación anterior.
    informar();
    // Actualizamos los controles que dependen de la fuente seleccionada.
    actualizarControles();
}

// Validamos una selección del explorador o un grupo de archivos soltados.
function recibirArchivo(lista) {
    // Ignoramos listas vacías, por ejemplo al cancelar el explorador.
    if (!lista.length) return;
    // Rechazamos selecciones múltiples porque cada análisis recibe una sola imagen.
    if (lista.length > 1) return informar("Selecciona una sola imagen para analizar.", true);
    // Extraemos el único archivo elegido.
    const nuevaImagen = lista[0];
    // Verificamos el límite de bytes que Django publicó en la plantilla.
    if (nuevaImagen.size > Number(formulario.dataset.maxBytes)) {
        // Advertimos sobre el tamaño máximo antes de realizar una subida.
        return informar("La imagen debe pesar como máximo 10 MB.", true);
    }
    // Aceptamos nombres o tipos MIME de los formatos previstos como comprobación inicial.
    if (!/\.(jpe?g|png|webp)$/i.test(nuevaImagen.name) && !["image/jpeg", "image/png", "image/webp"].includes(nuevaImagen.type)) {
        // Mostramos la lista de formatos admitidos si falla esa comprobación.
        return informar("Selecciona un archivo JPG, PNG o WebP.", true);
    }
    // Preparamos la vista previa cuando la selección supera las comprobaciones iniciales.
    elegirImagen(nuevaImagen);
}

// Liberamos la cámara y restablecemos la interfaz que depende de ella.
function apagarCamara() {
    // Invalidamos una apertura pendiente que aún espera respuesta del usuario.
    inicioCamara = null;
    // Cancelamos capturas periódicas y solicitudes pendientes del navegador.
    detenerAnalisis();
    // Cerramos el flujo de vídeo y sus pistas.
    camara.detener();
    // Limpiamos métricas, anotaciones y descarga de la captura anterior.
    borrarResultado();
    // Limpiamos el estado antes de volver al punto inicial.
    informar();
    // Actualizamos las acciones con la cámara ya cerrada.
    actualizarControles();
}

// Cambiamos entre carga de archivos y cámara web.
function cambiarModo(nuevoModo) {
    // Evitamos reiniciar el estado si se eligió el modo que ya estaba activo.
    if (modo === nuevoModo) return;
    // Registramos la nueva fuente de trabajo.
    modo = nuevoModo;
    // Ejecutamos la limpieza de la fuente anterior.
    apagarCamara();
    // Actualizamos el nombre que identifica la imagen o el dispositivo en el visor.
    elemento("nombre-fuente").textContent = modo === "camara" ? "Cámara web" : imagenElegida?.name || "Imagen de ejemplo";
}

// Coordinamos el inicio asíncrono de la cámara y el estado del botón.
async function activarCamara() {
    // Creamos un identificador único para esta activación de interfaz.
    const turno = Symbol();
    // Registramos la activación para deshabilitar peticiones repetidas.
    inicioCamara = turno;
    // Reflejamos que estamos esperando al navegador.
    actualizarControles();
    // Informamos que el acceso requiere la respuesta al permiso del navegador.
    informar("Esperando acceso a la cámara…");
    // Esperamos el inicio del vídeo y gestionamos posibles errores.
    try {
        // Avisamos que la cámara está lista si la activación sigue vigente.
        if (await camara.iniciar()) informar("Cámara lista.");
    // Interceptamos los fallos que entregó el controlador de cámara.
    } catch (error) {
        // Mostramos el mensaje en español que preparó la clase Camara.
        informar(error.message, true);
    // Ejecutamos la actualización final tanto si se abrió la cámara como si falló.
    } finally {
        // Comprobamos que otra activación posterior no haya sustituido este turno.
        if (inicioCamara === turno) {
            // Retiramos la marca de activación pendiente.
            inicioCamara = null;
            // Actualizamos qué acciones permite el estado final del dispositivo.
            actualizarControles();
            // Actualizamos el contenido visible y las dimensiones del visor.
            actualizarVisor();
        }
    }
}

// Unificamos el análisis de archivos, capturas puntuales y capturas periódicas.
async function analizar(obtenerImagen, continua = false) {
    // Omitimos una llamada si ya estamos preparando o enviando otra.
    if (solicitud) return false;
    // Creamos un controlador para cancelar esta operación concreta.
    const controlador = new AbortController();
    // Obtenemos la señal que consume el cliente HTTP.
    const señal = controlador.signal;
    // Registramos el controlador para impedir duplicados y permitir cancelación.
    solicitud = controlador;
    // Actualizamos botones mientras hay una operación en curso.
    actualizarControles();
    // Anunciamos la espera inicial sin repetirla para cada fotograma en vivo.
    if (!continua || !resultado) informar("Analizando con los dos modelos…");

    // Reunimos el procesamiento y el tratamiento de errores de la operación.
    try {
        // Esperamos la foto, el ejemplo descargado o el Blob de cámara.
        const imagen = await obtenerImagen(señal);
        // Interrumpimos el flujo antes de subir la imagen si se canceló entre tanto.
        if (señal.aborted) return false;
        // Enviamos la imagen al endpoint configurado en el formulario.
        const datos = await solicitarAnalisis(formulario, imagen, señal);
        // Ignoramos una respuesta que llegó cuando la operación ya estaba cancelada.
        if (señal.aborted) return false;
        // Mostramos la respuesta y cambiamos de vista solo en el análisis puntual.
        mostrarResultado(datos, !continua);
        // Comunicamos que terminó el análisis puntual o que la sesión en vivo continúa.
        informar(continua ? "Análisis en vivo activo." : "Análisis completado.");
        // Indicamos que la operación logró obtener y presentar un resultado.
        return true;
    // Interceptamos los errores de preparación, red y respuesta de Django.
    } catch (error) {
        // Omitimos avisos de error cuando fue el usuario quien canceló.
        if (!señal.aborted) {
            // Distinguimos un posible fallo de conexión de un mensaje específico de la operación.
            informar(error instanceof TypeError ? "No se pudo conectar con el servidor." : error.message, true);
        }
        // Indicamos el fallo al ciclo de análisis en vivo para que pueda detenerse.
        return false;
    // Ejecutamos la liberación de la solicitud después de éxito, error o cancelación.
    } finally {
        // Comprobamos si esta operación todavía es la solicitud registrada.
        if (solicitud === controlador) {
            // Quitamos el controlador de la operación completada.
            solicitud = null;
            // Volvemos a habilitar las acciones disponibles.
            actualizarControles();
        }
    }
}

// Encadenamos capturas de la misma sesión de análisis en vivo.
async function analizarFotogramas(sesion) {
    // Capturamos y enviamos un fotograma con el flujo común de análisis.
    const exito = await analizar(() => camara.capturar(), true);
    // Comprobamos que no se haya detenido o sustituido la sesión durante la espera.
    if (sesionEnVivo !== sesion) return;
    // Programamos otra captura solo cuando la operación terminó con éxito.
    if (exito) {
        // Esperar el resultado antes de enviar otro fotograma evita acumular solicitudes.
        // Aplicamos una espera de 450 milisegundos tras recibir la respuesta.
        sesion.temporizador = setTimeout(() => analizarFotogramas(sesion), 450);
    // Tratamos la rama en que la captura o el envío fallaron.
    } else {
        // Cerramos el análisis continuo para evitar repetir la solicitud fallida.
        detenerAnalisis();
    }
}

// Interceptamos el envío del formulario para procesarlo asíncronamente.
formulario.addEventListener("submit", (evento) => {
    // Evitamos una navegación normal a la respuesta JSON de Django.
    evento.preventDefault();
    // Enviamos el archivo elegido o descargamos el ejemplo cuando estamos en modo archivo.
    if (modo === "archivo") analizar((señal) => imagenElegida || cargarEjemplo(formulario.dataset.ejemplo, señal));
});
// Atendemos la selección de archivos del control nativo.
archivo.addEventListener("change", () => {
    // Pasamos los archivos seleccionados por la validación compartida.
    recibirArchivo(archivo.files);
    // Limpiamos el selector para que volver a elegir el mismo archivo dispare el evento.
    archivo.value = "";
});
// Detectamos que un archivo está sobre la zona de carga.
zonaArchivo.addEventListener("dragover", (evento) => {
    // Habilitamos la operación de soltar mediante el manejo del evento.
    evento.preventDefault();
    // Resaltamos visualmente la zona que recibe el archivo.
    zonaArchivo.classList.add("arrastrando");
});
// Detectamos que el elemento arrastrado sale de la zona de carga.
zonaArchivo.addEventListener("dragleave", (evento) => {
    // Quitamos el resaltado solo si realmente salió de la zona y sus hijos.
    if (!zonaArchivo.contains(evento.relatedTarget)) zonaArchivo.classList.remove("arrastrando");
});
// Recibimos los archivos cuando se sueltan sobre la zona de carga.
zonaArchivo.addEventListener("drop", (evento) => {
    // Evitamos que el navegador navegue a la imagen arrastrada.
    evento.preventDefault();
    // Quitamos el estilo de arrastre al completar la acción.
    zonaArchivo.classList.remove("arrastrando");
    // Validamos los archivos que contiene el objeto de transferencia.
    recibirArchivo(evento.dataTransfer.files);
});
// Vinculamos el botón Archivo con el selector de fuente.
elemento("modo-archivo").addEventListener("click", () => cambiarModo("archivo"));
// Vinculamos el botón Cámara web con el mismo selector de fuente.
elemento("modo-camara").addEventListener("click", () => cambiarModo("camara"));
// Reiniciamos la selección al ejemplo sin un archivo personalizado.
elemento("usar-ejemplo").addEventListener("click", () => elegirImagen(null));
// Iniciamos la captura de vídeo únicamente por interacción con su botón.
elemento("activar-camara").addEventListener("click", activarCamara);
// Liberamos cámara y análisis con el botón correspondiente.
elemento("cerrar-camara").addEventListener("click", apagarCamara);
// Enviamos una única captura del flujo de vídeo al pulsar el botón puntual.
elemento("capturar-fotograma").addEventListener("click", () => analizar(() => camara.capturar()));
// Alternamos el análisis en vivo mediante su botón.
elemento("analizar-en-vivo").addEventListener("click", () => {
    // Comprobamos si el usuario intenta detener una sesión existente.
    if (sesionEnVivo) {
        // Cancelamos el ciclo y las solicitudes pendientes de la sesión.
        detenerAnalisis();
        // Actualizamos el mensaje de estado al detener el análisis.
        informar("Análisis en vivo detenido.");
    // Iniciamos una nueva sesión cuando no hay ninguna activa.
    } else {
        // Elegimos la vista de detecciones para presentar los próximos resultados.
        vista = "resultado";
        // Creamos un objeto nuevo que identifica esta sesión.
        sesionEnVivo = {};
        // Disparamos la primera captura y dejamos que el ciclo programe las siguientes.
        analizarFotogramas(sesionEnVivo);
    }
});
// Mostramos la fuente original y actualizamos los botones y dimensiones.
elemento("ver-original").addEventListener("click", () => { vista = "original"; actualizarVisor(); });
// Mostramos las detecciones y actualizamos los mismos controles.
elemento("ver-resultado").addEventListener("click", () => { vista = "resultado"; actualizarVisor(); });
// Recalculamos el tamaño cuando acaba de cargarse la imagen original.
original.addEventListener("load", actualizarVisor);
// Recalculamos el tamaño cuando conocemos las dimensiones iniciales del vídeo.
video.addEventListener("loadedmetadata", actualizarVisor);
// Actualizamos la resolución si cambia el tamaño de los fotogramas.
video.addEventListener("resize", actualizarVisor);
// Apagamos la cámara al abandonar la página para liberar el dispositivo.
window.addEventListener("pagehide", apagarCamara);
// Alineamos los controles con el estado inicial antes de cualquier interacción.
actualizarControles();
// Alineamos el visor con el archivo de ejemplo y la vista original.
actualizarVisor();
