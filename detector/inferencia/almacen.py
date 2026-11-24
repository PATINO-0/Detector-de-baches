"""Descarga de los pesos desde Supabase Storage con una clave pública."""

from dataclasses import dataclass, field
from http.client import HTTPException
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen


MAX_BYTES_PESOS = 32 * 1024 * 1024


@dataclass(frozen=True)
class AlmacenSupabase:
    url: str
    bucket: str
    clave: str = field(repr=False)

    def leer(self, nombre):
        """Leer un objeto privado sin guardar los pesos en el disco de Vercel."""
        objeto = f"{quote(self.bucket, safe='')}/{quote(nombre, safe='')}"
        encabezados = {"apikey": self.clave}
        # La clave anon heredada es un JWT. La publicable viaja solo en apikey.
        if not self.clave.startswith("sb_publishable_"):
            encabezados["Authorization"] = f"Bearer {self.clave}"
        solicitud = Request(
            f"{self.url}/storage/v1/object/authenticated/{objeto}", headers=encabezados
        )
        try:
            with urlopen(solicitud, timeout=15) as respuesta:
                pesos = respuesta.read(MAX_BYTES_PESOS + 1)
        except HTTPError as error:
            error.close()
            raise RuntimeError(f"Supabase devolvió HTTP {error.code} al descargar {nombre}.") from error
        except (OSError, HTTPException) as error:
            raise RuntimeError(f"No se pudo descargar {nombre} desde Supabase.") from error

        if not pesos or len(pesos) > MAX_BYTES_PESOS:
            raise ValueError(f"El tamaño de {nombre} descargado de Supabase no es válido.")
        return pesos
