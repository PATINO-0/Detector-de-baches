"""Codificamos las consultas con el vocabulario y las fusiones BPE originales."""

# Usamos la misma expresión regular que se aplicó durante el entrenamiento.
import re
# Aplicamos la descomposición Unicode que espera el vocabulario.
import unicodedata


# Seleccionamos las palabras y los números que reconoce el modelo V4.
PATRON_PALABRA = re.compile(r"[a-z0-9]+")


# Encapsulamos la configuración reutilizable de la segmentación de texto.
class TokenizadorBPE:
    """Convertimos preguntas a secuencias de identificadores del modelo."""

    # Recibimos el vocabulario, las fusiones por prioridad y el tamaño de entrada.
    def __init__(self, vocabulario, fusiones, longitud):
        # Conservamos los identificadores aprendidos durante el entrenamiento.
        self.vocabulario = vocabulario
        # Indexamos cada pareja por el orden en que se aprendió su fusión.
        self.prioridad = {tuple(pareja): indice for indice, pareja in enumerate(fusiones)}
        # Reservamos una secuencia de longitud fija para el grafo ONNX.
        self.longitud = longitud

    # Permitimos usar la fusión sin consultar el estado del tokenizador.
    @staticmethod
    # Aplicamos una fusión de izquierda a derecha sin reutilizar piezas solapadas.
    def _fusionar(piezas, pareja):
        # Acumulamos las piezas resultantes de una pasada.
        nuevas = []
        # Empezamos por la primera pieza de la palabra.
        posicion = 0
        # Recorremos todas las piezas, incluidas las que no cambian.
        while posicion < len(piezas):
            # Comprobamos si las dos piezas consecutivas coinciden con la pareja elegida.
            if piezas[posicion:posicion + 2] == pareja:
                # Unimos ambas piezas y avanzamos sobre la pareja completa.
                nuevas.append("".join(pareja))
                # Saltamos la segunda pieza de la pareja que acabamos de combinar.
                posicion += 2
            else:
                # Conservamos la pieza actual y avanzamos solo un lugar.
                nuevas.append(piezas[posicion])
                # Dejamos la pieza siguiente disponible para buscar otra pareja.
                posicion += 1
        # Devolvemos la misma representación que usamos para buscar parejas.
        return tuple(nuevas)

    # Reproducimos la normalización, las fusiones y el relleno del modelo V4.
    def codificar(self, texto):
        # Pasamos a minúsculas y separamos los diacríticos de las letras.
        normalizado = unicodedata.normalize("NFKD", texto.lower())
        # Retiramos los diacríticos y extraemos los fragmentos alfanuméricos.
        sin_tildes = "".join(c for c in normalizado if not unicodedata.combining(c))
        # Dividimos el texto en los fragmentos que procesa BPE.
        palabras = PATRON_PALABRA.findall(sin_tildes)
        # Reservamos la ruta de rechazo original para preguntas sin palabras.
        if not palabras:
            # Indicamos al llamador que no corresponde ejecutar la red.
            return None

        # Acumulamos las piezas en el orden de lectura de la pregunta.
        piezas = []
        # Conservamos el mismo límite de palabras y caracteres por palabra de la exportación.
        for palabra in palabras[:self.longitud]:
            # Marcamos el inicio de palabra con el símbolo BPE del vocabulario original.
            secuencia = tuple("▁" + palabra[:100])
            # Aplicamos las fusiones disponibles hasta que dejen de existir parejas válidas.
            while len(secuencia) > 1:
                # Consideramos únicamente parejas contiguas que aparecen en la tabla aprendida.
                parejas = [p for p in zip(secuencia, secuencia[1:]) if p in self.prioridad]
                # Terminamos esta palabra si el vocabulario indica que ya está segmentada.
                if not parejas:
                    # Dejamos la secuencia como quedó en la última fusión.
                    break
                # Seleccionamos la fusión de mayor prioridad y actualizamos la secuencia.
                pareja = min(parejas, key=self.prioridad.__getitem__)
                # Volvemos a buscar fusiones sobre las piezas que quedaron agrupadas.
                secuencia = self._fusionar(secuencia, pareja)
            # Agregamos las piezas y reservamos la primera posición para el token de clasificación.
            piezas.extend(secuencia)
            # Detenemos la codificación cuando ya se llenaron las posiciones útiles.
            if len(piezas) >= self.longitud - 1:
                # Omitimos las palabras posteriores, que quedarían fuera del tensor.
                break

        # Convertimos las piezas a sus índices, con un identificador para piezas desconocidas.
        vocab = self.vocabulario
        # Añadimos CLS y conservamos como máximo la longitud que admite el modelo.
        ids = [vocab["<CLS>"]] + [vocab.get(pieza, vocab["<UNK>"]) for pieza in piezas[:self.longitud - 1]]
        # Completamos las posiciones libres con el identificador de relleno.
        return ids + [vocab["<PAD>"]] * (self.longitud - len(ids))
