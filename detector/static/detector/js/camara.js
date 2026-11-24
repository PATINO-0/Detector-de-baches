/* Controlar la cámara del navegador y convertir un fotograma en JPEG. */

// Encapsulamos la autorización, el ciclo de vida de la cámara y la captura de imágenes.
export class Camara {
    // Inicializamos la cámara con el visor y la función que informa una desconexión.
    constructor(video, alDesconectar) {
        // Guardamos el elemento de vídeo donde reproduciremos la señal.
        this.video = video;
        // Guardamos la acción que ejecutamos cuando termina una pista.
        this.alDesconectar = alDesconectar;
        // Creamos un lienzo fuera de la página que reutilizamos para cada captura.
        this.lienzo = document.createElement("canvas");
        // Indicamos que todavía no tenemos un MediaStream activo.
        this.flujo = null;
        // Inicializamos el contador que distingue solicitudes vigentes y canceladas.
        this.turno = 0;
    }

    // Solicitamos una pista de vídeo y esperamos hasta que se pueda reproducir.
    async iniciar() {
        // Comprobamos que getUserMedia esté disponible en el contexto actual.
        if (!navigator.mediaDevices?.getUserMedia) {
            // Explicamos los requisitos de navegador y contexto seguro si falta la API.
            throw new Error("La cámara requiere un navegador compatible abierto en localhost o HTTPS.");
        }
        // Reservamos un identificador distinto para esta solicitud de permiso.
        const turno = ++this.turno;
        // Controlamos errores de permisos, dispositivos y reproducción en el mismo bloque.
        try {
            // Pedimos el acceso mediante la API que muestra el diálogo del navegador.
            const flujo = await navigator.mediaDevices.getUserMedia({
                // Pedimos solo vídeo y evitamos acceder al micrófono.
                audio: false,
                // Preferimos la cámara trasera y 1.280 por 720 píxeles cuando el dispositivo lo permite.
                video: { facingMode: { ideal: "environment" }, width: { ideal: 1280 }, height: { ideal: 720 } },
            });
            // El permiso puede llegar después de que el usuario cambie de fuente.
            // Detectamos si esta petición dejó de ser la solicitud activa.
            if (turno !== this.turno) {
                // Cerramos todas las pistas que devolvió un permiso que llegó tarde.
                flujo.getTracks().forEach((pista) => pista.stop());
                // Indicamos que la activación quedó cancelada.
                return false;
            }

            // Conservamos el flujo que autorizó el usuario.
            this.flujo = flujo;
            // Enlazamos la señal en directo con el elemento video.
            this.video.srcObject = flujo;
            // Registramos la desconexión para cada pista de vídeo del flujo.
            for (const pista of flujo.getVideoTracks()) {
                // Reaccionamos una sola vez si el navegador o dispositivo termina la pista.
                pista.addEventListener("ended", this.alDesconectar, { once: true });
            }
            // Esperamos a que comience la reproducción para comunicar disponibilidad.
            await this.video.play();
            // Confirmamos que la activación sigue vigente al terminar la espera.
            return turno === this.turno;
        // Tratamos cualquier excepción del permiso o de la reproducción.
        } catch (error) {
            // Ignoramos el fallo si la activación ya había sido cancelada.
            if (turno !== this.turno) return false;
            // Cerramos recursos que pudieron quedar abiertos antes del fallo.
            this.detener();
            // Devolvemos una explicación en español según el tipo de error.
            throw new Error(mensajeCamara(error));
        }
    }

    // Liberamos el dispositivo y anulamos activaciones en espera.
    detener() {
        // Cambiamos el contador para invalidar permisos que todavía no han llegado.
        this.turno++;
        // Detenemos todas las pistas cuando existe un flujo activo.
        this.flujo?.getTracks().forEach((pista) => pista.stop());
        // Quitamos el flujo del elemento de vídeo.
        this.video.srcObject = null;
        // Limpiamos la referencia para que la interfaz reconozca que está apagada.
        this.flujo = null;
    }

    // Extraemos la imagen que la cámara está reproduciendo en ese instante.
    capturar() {
        // Leemos las dimensiones del fotograma, que pueden diferir de las preferencias.
        const { videoWidth: ancho, videoHeight: alto } = this.video;
        // Comprobamos flujo, dimensiones y disponibilidad de los datos del fotograma actual.
        if (!this.flujo || !ancho || !alto || this.video.readyState < 2) {
            // Explicamos por qué todavía no se puede capturar la imagen.
            throw new Error("La cámara todavía no tiene un fotograma disponible.");
        }

        // Limitamos el lado mayor a 1.280 píxeles y evitamos ampliar el fotograma.
        const escala = Math.min(1, 1280 / Math.max(ancho, alto));
        // Cambiamos el tamaño del lienzo solo si difiere del tamaño calculado.
        if (this.lienzo.width !== Math.round(ancho * escala) || this.lienzo.height !== Math.round(alto * escala)) {
            // Ajustamos el ancho y garantizamos que el lienzo tenga al menos una columna.
            this.lienzo.width = Math.max(1, Math.round(ancho * escala));
            // Ajustamos el alto con la misma escala y garantizamos al menos una fila.
            this.lienzo.height = Math.max(1, Math.round(alto * escala));
        }
        // Dibujamos el fotograma completo, proporcionalmente reducido si correspondía.
        this.lienzo.getContext("2d").drawImage(this.video, 0, 0, this.lienzo.width, this.lienzo.height);
        // Usamos una promesa para integrar la codificación asíncrona de canvas.
        return new Promise((resolver, rechazar) => {
            // Solicitamos la codificación del lienzo a una imagen binaria.
            this.lienzo.toBlob((imagen) => {
                // Resolvemos la promesa con el Blob que insertamos en el formulario.
                if (imagen) resolver(imagen);
                // Rechazamos la captura si el navegador no pudo producir el Blob.
                else rechazar(new Error("No se pudo capturar el fotograma."));
            // Elegimos JPEG con calidad solicitada de 0,9.
            }, "image/jpeg", 0.9);
        });
    }
}

// Convertimos los nombres de error del navegador en acciones comprensibles.
function mensajeCamara(error) {
    // Agrupamos los mensajes de los errores de cámara más habituales.
    const mensajes = {
        // Indicamos cómo recuperar un permiso denegado o bloqueado.
        NotAllowedError: "Permite el acceso a la cámara en el navegador e inténtalo de nuevo.",
        // Informamos si no se encontró un dispositivo de vídeo.
        NotFoundError: "No se encontró una cámara web disponible.",
        // Informamos si existe una cámara que no se pudo abrir.
        NotReadableError: "No se pudo abrir la cámara. Comprueba si otra aplicación la está usando.",
    };
    // Usamos el mensaje específico o uno general si el navegador devuelve otro error.
    return mensajes[error.name] || "No se pudo iniciar la cámara web.";
}
