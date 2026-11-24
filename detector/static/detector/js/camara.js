/* Controlar la cámara del navegador y convertir un fotograma en JPEG. */

export class Camara {
    constructor(video, alDesconectar) {
        this.video = video;
        this.alDesconectar = alDesconectar;
        this.lienzo = document.createElement("canvas");
        this.flujo = null;
        this.turno = 0;
    }

    async iniciar() {
        if (!navigator.mediaDevices?.getUserMedia) {
            throw new Error("La cámara requiere un navegador compatible abierto en localhost o HTTPS.");
        }
        const turno = ++this.turno;
        try {
            const flujo = await navigator.mediaDevices.getUserMedia({
                audio: false,
                video: { facingMode: { ideal: "environment" }, width: { ideal: 1280 }, height: { ideal: 720 } },
            });
            // El permiso puede llegar después de que el usuario cambie de fuente.
            if (turno !== this.turno) {
                flujo.getTracks().forEach((pista) => pista.stop());
                return false;
            }

            this.flujo = flujo;
            this.video.srcObject = flujo;
            for (const pista of flujo.getVideoTracks()) {
                pista.addEventListener("ended", this.alDesconectar, { once: true });
            }
            await this.video.play();
            return turno === this.turno;
        } catch (error) {
            if (turno !== this.turno) return false;
            this.detener();
            throw new Error(mensajeCamara(error));
        }
    }

    detener() {
        this.turno++;
        this.flujo?.getTracks().forEach((pista) => pista.stop());
        this.video.srcObject = null;
        this.flujo = null;
    }

    capturar() {
        const { videoWidth: ancho, videoHeight: alto } = this.video;
        if (!this.flujo || !ancho || !alto || this.video.readyState < 2) {
            throw new Error("La cámara todavía no tiene un fotograma disponible.");
        }

        const escala = Math.min(1, 1280 / Math.max(ancho, alto));
        if (this.lienzo.width !== Math.round(ancho * escala) || this.lienzo.height !== Math.round(alto * escala)) {
            this.lienzo.width = Math.max(1, Math.round(ancho * escala));
            this.lienzo.height = Math.max(1, Math.round(alto * escala));
        }
        this.lienzo.getContext("2d").drawImage(this.video, 0, 0, this.lienzo.width, this.lienzo.height);
        return new Promise((resolver, rechazar) => {
            this.lienzo.toBlob((imagen) => {
                if (imagen) resolver(imagen);
                else rechazar(new Error("No se pudo capturar el fotograma."));
            }, "image/jpeg", 0.9);
        });
    }
}

function mensajeCamara(error) {
    const mensajes = {
        NotAllowedError: "Permite el acceso a la cámara en el navegador e inténtalo de nuevo.",
        NotFoundError: "No se encontró una cámara web disponible.",
        NotReadableError: "No se pudo abrir la cámara. Comprueba si otra aplicación la está usando.",
    };
    return mensajes[error.name] || "No se pudo iniciar la cámara web.";
}
