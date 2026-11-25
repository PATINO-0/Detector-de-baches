"""Redactamos respuestas en español a partir de la intención y la inspección activa."""


# Mostramos los porcentajes con separador decimal en español.
def porcentaje(valor, decimales=2):
    # El contexto trae la cobertura en unidades porcentuales de 0 a 100.
    return f"{valor:.{decimales}f}".replace(".", ",") + " %"


# Conservamos la distinción entre cobertura cero y una máscara muy pequeña.
def texto_cobertura(cobertura):
    # Usamos el mismo rango mínimo visible que emplea el panel de resultados.
    if 0 < cobertura < 0.01:
        # Mantenemos visible que hubo una marca aunque su porcentaje sea muy pequeño.
        return "menos del 0,01 %"
    # Presentamos los demás valores como un porcentaje con dos decimales.
    return f"el {porcentaje(cobertura)}"


# Ajustamos el singular y el plural al hablar de cajas de baches.
def nombrar_baches(cantidad):
    # Devolvemos la misma unidad que usamos en la interfaz y el resumen.
    return f"{cantidad} {'bache' if cantidad == 1 else 'baches'}"


# Presentamos en una sola frase los dos indicadores que calcula la inspección.
def resumir(cantidad, cobertura):
    # Expresamos la cobertura por píxel y el conteo de cajas con sus unidades.
    return (f"El análisis registró {nombrar_baches(cantidad)}. "
            f"La máscara de grietas cubre {texto_cobertura(cobertura)} de la imagen.")


# Aplicamos plantillas según la intención decidida por el Transformer original.
def redactar(intencion, contexto):
    # Atendemos las consultas que el clasificador rechaza por dominio o puntuación.
    if intencion == "fuera_de_dominio":
        # Orientamos al usuario hacia preguntas que el modelo fue entrenado para reconocer.
        return "No comprendí la consulta. Puedes preguntar por los baches, las grietas o el resumen de RoadVision."
    # Explicamos las capacidades del asistente incluso antes de analizar una imagen.
    if intencion == "ayuda":
        # Enumeramos los indicadores que nuestras plantillas pueden interpretar.
        return ("Puedes consultar el conteo, la ubicación y la confianza de los baches, la presencia y cobertura de "
                "grietas, el resumen de detecciones y la información visual del tramo.")
    # Explicamos el alcance temporal sin inventar análisis persistidos.
    if intencion == "historial":
        # Presentamos la visita actual y la opción existente para conservar la imagen.
        return "Consulto el último análisis de esta página. Puedes conservarlo al descargar la imagen anotada."
    # Pedimos una inspección cuando la intención depende de resultados ausentes.
    if contexto is None:
        # Mencionamos las dos fuentes válidas con las que puede obtener un contexto.
        return "Analiza una foto o un fotograma para que pueda responder sobre sus detecciones."

    # Extraemos los indicadores comunes del contexto autenticado.
    cantidad = contexto["cantidad_baches"]
    # Recuperamos el booleano que indica si hubo marcas de segmentación.
    hay_grietas = contexto["hay_grietas"]
    # Recuperamos el porcentaje calculado antes de dibujar la anotación.
    cobertura = contexto["cobertura_grietas_pct"]
    # Respondemos con el número de cajas que quedaron tras la detección.
    if intencion == "cantidad_baches":
        # Formateamos la cantidad con el sustantivo en singular o plural.
        return f"La detección encontró {nombrar_baches(cantidad)} en la imagen."
    # Contestamos sobre presencia con el mismo criterio que emplea el visor.
    if intencion == "presencia_grietas":
        # Elegimos el mensaje correspondiente al indicador booleano.
        return "Se detectaron grietas en la imagen." if hay_grietas else "No se detectaron grietas en la imagen."
    # Mostramos el porcentaje de píxeles que marcó el segmentador.
    if intencion == "cobertura_grietas":
        # Indicamos que la unidad se refiere a la imagen analizada completa.
        return f"La máscara de grietas cubre {texto_cobertura(cobertura)} de la imagen analizada."
    # Distinguimos la ausencia de cajas de una puntuación promedio calculable.
    if intencion == "confianza":
        # Leemos la media de las cajas seleccionadas por el detector.
        promedio = contexto["confianza_baches_promedio"]
        # Tratamos de forma explícita el caso en que el detector devolvió cero cajas.
        if promedio is None:
            # Explicamos por qué el resultado no tiene un promedio calculado.
            return "No hay puntuaciones de confianza porque el análisis no devolvió cajas de baches."
        # Pasamos la puntuación de 0 a 1 a un porcentaje con un decimal.
        return f"La confianza promedio de las cajas de baches es del {porcentaje(100 * promedio, 1)}."
    # Situamos las cajas con localizaciones relativas al encuadre.
    if intencion == "ubicacion_baches":
        # Explicamos un resultado vacío sin inventar una ubicación.
        if not cantidad:
            return "No se detectaron baches que podamos ubicar en la imagen."
        # Unimos el número de cajas de cada zona con su posición relativa en el encuadre.
        zonas = [f"{nombrar_baches(total)} en {zona}" for zona, total in contexto["ubicaciones_baches"].items()]
        # Concordamos el verbo con el número total de detecciones.
        verbo = "Se detectó" if cantidad == 1 else "Se detectaron"
        # Presentamos todas las zonas ocupadas en una sola intervención.
        return f"{verbo} " + " · ".join(zonas) + "."
    # Identificamos un tipo único o explicamos los indicadores cuando coexisten las dos clases.
    if intencion == "dano_predominante":
        # Reservamos el resumen de unidades distintas para inspecciones con ambos tipos de daño.
        if cantidad and hay_grietas:
            # Mostramos medidas separadas para conservar las unidades de cada daño.
            return resumir(cantidad, cobertura) + " Informo ambos indicadores por separado porque tienen unidades distintas."
        # Con una sola clase podemos identificar el tipo presente.
        if cantidad or hay_grietas:
            # Elegimos la clase que devolvió una detección positiva.
            return "El análisis detectó únicamente baches." if cantidad else "El análisis detectó únicamente grietas."
        # Presentamos el resultado vacío de los dos predictores.
        return "El análisis no marcó baches ni grietas en esta imagen."
    # Describimos la afectación visible usando exclusivamente las medidas disponibles.
    if intencion == "nivel_afectacion":
        # Acompañamos las cifras visuales con lo que hace falta medir en el tramo.
        return resumir(cantidad, cobertura) + " Para estimar la gravedad del tramo se necesitan mediciones en sitio."
    # Sugerimos una comprobación de campo cuando el usuario pide una recomendación.
    if intencion == "recomendacion":
        # Tratamos por separado una escena con hallazgos y una con resultado vacío.
        if cantidad or hay_grietas:
            # Proponemos verificar el hallazgo antes de decidir una intervención.
            return "Conviene verificar los daños con una inspección técnica del tramo antes de decidir una reparación."
        # Sugerimos observar otro ángulo para ampliar la información de la escena.
        return "El análisis no marcó daños. Una revisión del tramo desde otros ángulos puede aportar más información."
    # Reunimos el conteo de baches y la cobertura de grietas en un informe breve.
    if intencion == "reporte_general":
        # Reutilizamos el formato de resumen que aplica ambos indicadores.
        return resumir(cantidad, cobertura)
    # Respondemos de forma controlada si falta una plantilla de la intención predicha.
    return "No hay datos suficientes para responder esta consulta en el análisis seleccionado."
