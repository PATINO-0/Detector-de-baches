"""Punto de entrada para los comandos de Django."""

# Importamos el acceso a las variables de entorno del proceso.
import os
# Importamos la lista de argumentos que recibió Python en la terminal.
import sys

# Usamos el despachador de Django para ejecutar el subcomando solicitado.
from django.core.management import execute_from_command_line


# Ejecutamos el punto de entrada cuando se invoca el archivo como script.
if __name__ == "__main__":
    # Seleccionamos la configuración de RoadVision si aún no se indicó otra.
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "roadvision.settings")
    # Entregamos a Django el nombre del comando y todos sus argumentos.
    execute_from_command_line(sys.argv)
