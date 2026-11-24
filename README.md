# RoadVision AI

Aplicación Django en español para analizar el pavimento. Los dos modelos del repositorio se ejecutan sobre cada imagen. Los baches se muestran con cajas y una puntuación de confianza. Las grietas se resaltan con una máscara y se informa qué porcentaje de la imagen ocupan.

## Ejecutar en Windows

Desde la raíz del proyecto, con Python de 64 bits. La aplicación se verificó con Python 3.13.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py runserver
```

Abre [RoadVision AI en localhost](http://localhost:8000/).

- En **Archivo**, pulsa **Analizar imagen** para probar el ejemplo o selecciona o arrastra una fotografía JPG, PNG o WebP de hasta 10 MB y 24 megapíxeles.
- En **Cámara web**, pulsa **Activar cámara** y concede permiso. Puedes analizar un fotograma o iniciar el análisis en vivo, que envía un fotograma a la vez. **Original** muestra la cámara en directo y **Detecciones** muestra el último fotograma analizado. Usa `localhost` o HTTPS para que el navegador permita el acceso. [Requisitos de acceso a la cámara en el navegador](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia#privacy_and_security)
- Puedes alternar entre la fuente original y el resultado y descargar el JPEG anotado. Las imágenes de archivo se orientan según los metadatos EXIF y se reducen proporcionalmente a 1.600 píxeles en el lado mayor si exceden ese tamaño.

El análisis se realiza en CPU y las solicitudes se procesan sin guardar un historial. La primera ejecución carga ambas sesiones ONNX. Django reutiliza las sesiones durante el resto del proceso.

## Modelos incluidos

| Archivo | Modelo y configuración |
| --- | --- |
| `modelos/baches.onnx` y `modelos/baches.json` | Detector RoadVisionAI V6 basado en YOLOv8n. Usa la exportación de la época 10 de la corrida de continuación iniciada con el checkpoint propio de `v6_rtx4060ti_desde_cero`. La inferencia usa entradas de 768 píxeles, tres vistas TTA e IoU de 0,60 para la supresión de cajas solapadas. El umbral del informe original fue 0,4863. |
| `modelos/grietas.onnx` y `modelos/grietas.json` | CrackUNet entrenado desde cero con Crack-Seg. Usa la exportación de la época 20 con entrada de 384 píxeles. El umbral del informe original fue 0,85. |

Los pesos y metadatos proceden de los paquetes `RoadVisionAI_Baches_V6` y `RoadVisionAI_Grietas`. Se valida el SHA-256 de cada ONNX al cargarlo. La instalación incluye los cuatro archivos necesarios para la inferencia y usa ONNX Runtime para ambos modelos.

La aplicación usa los umbrales definidos en `roadvision/settings.py` para archivos y cámara. `UMBRAL_CONFIANZA_BACHES = 0.15` admite cajas con puntuaciones como 0,18 si pasan la supresión de solapamientos. `UMBRAL_SEGMENTACION_GRIETAS = 0.947` exige una probabilidad de al menos 0,947 por píxel. Las métricas de los JSON corresponden a sus respectivos umbrales originales.

## Estructura

| Ruta | Función |
| --- | --- |
| `roadvision/` | Configuración de Django, límites de entrada y rutas principales. |
| `detector/imagenes.py` | Validación del archivo, orientación y conversión a RGB. |
| `detector/inferencia/` | Carga de sesiones ONNX y preprocesamiento y posprocesamiento de cada modelo. |
| `detector/servicio.py` | Ejecución de ambos modelos y cálculo del resumen de detecciones. |
| `detector/resultados.py` | Dibujo de cajas y máscara sobre la imagen. |
| `detector/templates/` y `detector/static/` | Interfaz adaptable, carga de imágenes y captura desde el navegador. |

`POST /api/analizar/` recibe un formulario `multipart/form-data` con el campo `imagen` y el token CSRF. Devuelve las cajas `box_xyxy` referidas a la resolución analizada, el porcentaje de píxeles de grieta y la imagen JPEG anotada.

Puedes cambiar el directorio de los modelos con `ROADVISION_MODELOS` y los hilos de inferencia por sesión con `ROADVISION_HILOS`.

La fotografía de ejemplo es de Editor5807 y se distribuye en dominio público según Wikimedia Commons. [Ficha de la fotografía](https://commons.wikimedia.org/wiki/File:Emerging_pot_hole.JPG)
