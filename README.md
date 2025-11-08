
## Endpoints Disponibles

### 1. Health Check
- **GET** `/` - Verificación básica
- **GET** `/health` - Estado del servicio

### 2. Extracción de Drive
- **POST** `/extraer-drive`
- **Body:**
  ```json
  {
    "ciclo_num": 1,
    "semana_num": 6
  }
  ```
- **Respuesta:**
  ```json
  [
    {
      "asignatura": "Nombre de la Asignatura",
      "ciclo": 1,
      "semana": 6,
      "id_silabo": "1A2B3C4D5E",
      "id_teoria": "6F7G8H9I0J",
      "id_practica": "1K2L3M4N5O",
      "id_laboratorio": "6P7Q8R9S0T"
    }
  ]
  ```

### 3. Conversión de Documentos
- **POST** `/convertir-documento`
- **Body:** Archivo DOCX o PPTX (multipart/form-data)
- **Respuesta:**
  ```json
  {
    "text": "Contenido extraído del documento..."
  }
  ```

## Notas
- Los IDs de carpetas serán `null` si no se encuentra la carpeta correspondiente
- La aplicación busca carpetas de forma insensible a mayúsculas/minúsculas
- Las credenciales de Google deben estar en el archivo `credentials-python.json` en el directorio raíz
