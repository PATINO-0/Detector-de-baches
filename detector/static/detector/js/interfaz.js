/* Coordinar la fuente, la vista y el estado de cada análisis. */

import { cargarEjemplo, solicitarAnalisis } from "./api.js";
import { Camara } from "./camara.js";

const elemento = (id) => document.getElementById(id);
const formulario = elemento("formulario");
const original = elemento("imagen-original");
const anotada = elemento("imagen-resultado");
const video = elemento("video");
const archivo = elemento("archivo");
const zonaArchivo = elemento("zona-archivo");
const descarga = elemento("descargar-resultado");
const estado = elemento("estado");
const porcentaje = new Intl.NumberFormat("es-CO", { style: "percent", maximumFractionDigits: 2 });

const camara = new Camara(video, () => {
    apagarCamara();
    informar("La cámara se desconectó.", true);
});

let modo = "archivo";
let vista = "original";
let imagenElegida = null;
let urlOriginal = null;
let resultado = null;
let solicitud = null;
let inicioCamara = null;
let sesionEnVivo = null;

function informar(mensaje = "", error = false) {
    estado.dataset.error = String(error);
    if (estado.textContent !== mensaje) estado.textContent = mensaje;
}

function actualizarVisor() {
    const camaraActiva = Boolean(camara.flujo);
    const verDetecciones = vista === "resultado" && Boolean(resultado);
    original.hidden = modo !== "archivo" || verDetecciones;
    anotada.hidden = !verDetecciones;
    // Mantener el vídeo activo detrás del resultado para capturar el siguiente fotograma.
    video.hidden = modo !== "camara" || !camaraActiva;
    video.setAttribute("aria-hidden", String(verDetecciones));
    elemento("camara-sin-video").hidden = modo !== "camara" || camaraActiva || verDetecciones;
    elemento("ver-original").setAttribute("aria-pressed", String(!verDetecciones));
    elemento("ver-resultado").setAttribute("aria-pressed", String(verDetecciones));
    elemento("ver-resultado").disabled = !resultado;

    const ancho = verDetecciones ? resultado.ancho : modo === "archivo" ? original.naturalWidth : video.videoWidth;
    const alto = verDetecciones ? resultado.alto : modo === "archivo" ? original.naturalHeight : video.videoHeight;
    elemento("resolucion").textContent = ancho && alto ? `${ancho} × ${alto} px` : "";
}

function actualizarControles() {
    const camaraActiva = Boolean(camara.flujo);
    const enVivo = Boolean(sesionEnVivo);
    const ocupado = Boolean(solicitud);
    elemento("controles-archivo").hidden = modo !== "archivo";
    elemento("controles-camara").hidden = modo !== "camara";
    elemento("modo-archivo").setAttribute("aria-pressed", String(modo === "archivo"));
    elemento("modo-camara").setAttribute("aria-pressed", String(modo === "camara"));
    elemento("usar-ejemplo").hidden = !imagenElegida;
    elemento("analizar-archivo").disabled = ocupado;
    elemento("analizar-archivo").textContent = ocupado ? "Analizando…" : "Analizar imagen";

    elemento("activar-camara").hidden = camaraActiva;
    elemento("activar-camara").disabled = Boolean(inicioCamara);
    elemento("activar-camara").textContent = inicioCamara ? "Abriendo cámara…" : "Activar cámara";
    elemento("cerrar-camara").hidden = !camaraActiva;
    elemento("capturar-fotograma").hidden = !camaraActiva;
    elemento("capturar-fotograma").disabled = ocupado || enVivo;
    elemento("analizar-en-vivo").hidden = !camaraActiva;
    elemento("analizar-en-vivo").disabled = ocupado && !enVivo;
    elemento("analizar-en-vivo").textContent = enVivo ? "Detener análisis en vivo" : "Analizar en vivo";
    elemento("ayuda-camara").textContent = camaraActiva
        ? "Apunta al pavimento y elige cómo analizar la imagen."
        : "Activa la cámara y apunta hacia el pavimento.";
}

function borrarResultado() {
    resultado = null;
    vista = "original";
    anotada.removeAttribute("src");
    descarga.removeAttribute("href");
    descarga.hidden = true;
    elemento("cantidad-baches").textContent = "—";
    elemento("cobertura-grietas").textContent = "—";
    elemento("detalle-baches").hidden = true;
    elemento("detalle-baches").open = false;
    elemento("lista-baches").replaceChildren();
    elemento("resumen-resultado").textContent = "Analiza una imagen para ver las detecciones.";
    actualizarVisor();
}

function mostrarResultado(datos, cambiarVista) {
    resultado = datos;
    if (cambiarVista) vista = "resultado";
    anotada.src = datos.imagen;
    descarga.href = datos.imagen;
    descarga.hidden = false;

    const baches = datos.baches.length;
    const { cobertura, detectadas } = datos.grietas;
    elemento("cantidad-baches").textContent = baches;
    elemento("cobertura-grietas").textContent = detectadas && cobertura < 0.01
        ? "<0,01 %"
        : porcentaje.format(cobertura / 100);
    elemento("resumen-resultado").textContent = baches || detectadas
        ? "La cobertura indica la proporción de la imagen cubierta por grietas."
        : "Los modelos no detectaron baches ni grietas en esta imagen.";
    elemento("detalle-baches").hidden = !baches;
    elemento("lista-baches").replaceChildren(...datos.baches.map((bache) => {
        const fila = document.createElement("li");
        fila.textContent = `${porcentaje.format(bache.confidence)} de confianza`;
        return fila;
    }));
    actualizarVisor();
}

function detenerAnalisis() {
    clearTimeout(sesionEnVivo?.temporizador);
    sesionEnVivo = null;
    solicitud?.abort();
    solicitud = null;
    actualizarControles();
}

function elegirImagen(nuevaImagen) {
    detenerAnalisis();
    imagenElegida = nuevaImagen;
    if (urlOriginal) URL.revokeObjectURL(urlOriginal);
    urlOriginal = nuevaImagen ? URL.createObjectURL(nuevaImagen) : null;
    original.src = urlOriginal || formulario.dataset.ejemplo;
    elemento("nombre-fuente").textContent = nuevaImagen?.name || "Imagen de ejemplo";
    borrarResultado();
    informar();
    actualizarControles();
}

function recibirArchivo(lista) {
    if (!lista.length) return;
    if (lista.length > 1) return informar("Selecciona una sola imagen para analizar.", true);
    const nuevaImagen = lista[0];
    if (nuevaImagen.size > Number(formulario.dataset.maxBytes)) {
        return informar("La imagen debe pesar como máximo 10 MB.", true);
    }
    if (!/\.(jpe?g|png|webp)$/i.test(nuevaImagen.name) && !["image/jpeg", "image/png", "image/webp"].includes(nuevaImagen.type)) {
        return informar("Selecciona un archivo JPG, PNG o WebP.", true);
    }
    elegirImagen(nuevaImagen);
}

function apagarCamara() {
    inicioCamara = null;
    detenerAnalisis();
    camara.detener();
    borrarResultado();
    informar();
    actualizarControles();
}

function cambiarModo(nuevoModo) {
    if (modo === nuevoModo) return;
    modo = nuevoModo;
    apagarCamara();
    elemento("nombre-fuente").textContent = modo === "camara" ? "Cámara web" : imagenElegida?.name || "Imagen de ejemplo";
}

async function activarCamara() {
    const turno = Symbol();
    inicioCamara = turno;
    actualizarControles();
    informar("Esperando acceso a la cámara…");
    try {
        if (await camara.iniciar()) informar("Cámara lista.");
    } catch (error) {
        informar(error.message, true);
    } finally {
        if (inicioCamara === turno) {
            inicioCamara = null;
            actualizarControles();
            actualizarVisor();
        }
    }
}

async function analizar(obtenerImagen, continua = false) {
    if (solicitud) return false;
    const controlador = new AbortController();
    const señal = controlador.signal;
    solicitud = controlador;
    actualizarControles();
    if (!continua || !resultado) informar("Analizando con los dos modelos…");

    try {
        const imagen = await obtenerImagen(señal);
        if (señal.aborted) return false;
        const datos = await solicitarAnalisis(formulario, imagen, señal);
        if (señal.aborted) return false;
        mostrarResultado(datos, !continua);
        informar(continua ? "Análisis en vivo activo." : "Análisis completado.");
        return true;
    } catch (error) {
        if (!señal.aborted) {
            informar(error instanceof TypeError ? "No se pudo conectar con el servidor." : error.message, true);
        }
        return false;
    } finally {
        if (solicitud === controlador) {
            solicitud = null;
            actualizarControles();
        }
    }
}

async function analizarFotogramas(sesion) {
    const exito = await analizar(() => camara.capturar(), true);
    if (sesionEnVivo !== sesion) return;
    if (exito) {
        // Esperar el resultado antes de enviar otro fotograma evita acumular solicitudes.
        sesion.temporizador = setTimeout(() => analizarFotogramas(sesion), 450);
    } else {
        detenerAnalisis();
    }
}

formulario.addEventListener("submit", (evento) => {
    evento.preventDefault();
    if (modo === "archivo") analizar((señal) => imagenElegida || cargarEjemplo(formulario.dataset.ejemplo, señal));
});
archivo.addEventListener("change", () => {
    recibirArchivo(archivo.files);
    archivo.value = "";
});
zonaArchivo.addEventListener("dragover", (evento) => {
    evento.preventDefault();
    zonaArchivo.classList.add("arrastrando");
});
zonaArchivo.addEventListener("dragleave", (evento) => {
    if (!zonaArchivo.contains(evento.relatedTarget)) zonaArchivo.classList.remove("arrastrando");
});
zonaArchivo.addEventListener("drop", (evento) => {
    evento.preventDefault();
    zonaArchivo.classList.remove("arrastrando");
    recibirArchivo(evento.dataTransfer.files);
});
elemento("modo-archivo").addEventListener("click", () => cambiarModo("archivo"));
elemento("modo-camara").addEventListener("click", () => cambiarModo("camara"));
elemento("usar-ejemplo").addEventListener("click", () => elegirImagen(null));
elemento("activar-camara").addEventListener("click", activarCamara);
elemento("cerrar-camara").addEventListener("click", apagarCamara);
elemento("capturar-fotograma").addEventListener("click", () => analizar(() => camara.capturar()));
elemento("analizar-en-vivo").addEventListener("click", () => {
    if (sesionEnVivo) {
        detenerAnalisis();
        informar("Análisis en vivo detenido.");
    } else {
        vista = "resultado";
        sesionEnVivo = {};
        analizarFotogramas(sesionEnVivo);
    }
});
elemento("ver-original").addEventListener("click", () => { vista = "original"; actualizarVisor(); });
elemento("ver-resultado").addEventListener("click", () => { vista = "resultado"; actualizarVisor(); });
original.addEventListener("load", actualizarVisor);
video.addEventListener("loadedmetadata", actualizarVisor);
video.addEventListener("resize", actualizarVisor);
window.addEventListener("pagehide", apagarCamara);
actualizarControles();
actualizarVisor();
