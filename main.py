from contextlib import asynccontextmanager
import json
from googleapiclient.discovery import build
from google.oauth2 import service_account
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os

# tu JSON de service account
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"] # carpeta raíz con asignaturas


service = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global service
    try:
        # Leer las credenciales desde la variable de entorno
        google_api_secret = os.getenv("GOOGLE_API_SECRET")
        folder_id_env = os.getenv("ID_CARPETA")

        if not google_api_secret or not folder_id_env:
            raise Exception("Variables de entorno GOOGLE_API_SECRET o ID_CARPETA no encontradas")

        # Parsear el JSON de las credenciales
        credentials_info = json.loads(google_api_secret)
        creds = service_account.Credentials.from_service_account_info(
             credentials_info, scopes=SCOPES )
        service = build("drive", "v3", credentials=creds)
        print("Servicio de Google Drive autenticado exitosamente.")

    except Exception as e:
        service = None
        print(f"Error fatal durante la autenticación: {e}")

    yield

# Shutdown (si necesitas limpiar algo)
    pass

app = FastAPI(lifespan=lifespan)
# Obtener folder_id desde variable de entorno
folder_id = os.getenv("ID_CARPETA", "1JVV3OVjabbHIVvJZSb338w6ZrieDJ3IS")

# --- Modelo de Pydantic para los datos de entrada ---
class DriveQuery(BaseModel):
    ciclo_num: int
    semana_num: int

# --- Endpoint POST principal ---
@app.post("/extraer-drive")
async def ejecutar_extraccion(query: DriveQuery):
    if not service:
        raise HTTPException(status_code=500, detail="El servicio de Google Drive no está autenticado. Revisa los logs del contenedor.")

    try:
        # Llama a tu función principal con los datos del POST
        datos_completos = get_datos_ciclo(
            ciclo_num=query.ciclo_num,
            semana_num=query.semana_num
        )
        return datos_completos
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ocurrió un error durante la extracción: {str(e)}")




# --- Funciones Auxiliares (con mejoras) ---

def find_item_in_folder(parent_id, name_to_find, is_prefix=False, mime_type=None):
    """
    Busca un ítem de forma insensible a mayúsculas/minúsculas.
    Obtiene todos los ítems de la carpeta y los compara en Python para mayor precisión.
    """
    if not service: return None
    try:
        query = f"'{parent_id}' in parents and trashed=false"
        if mime_type:
            query += f" and mimeType = '{mime_type}'"

        results = service.files().list(q=query, fields="files(id, name, mimeType)").execute()
        items = results.get("files", [])

        # Normalizamos el nombre a buscar a minúsculas
        name_to_find_lower = name_to_find.lower()

        for item in items:
            # Comparamos todo en minúsculas y sin espacios extra
            item_name_lower = item['name'].lower().strip()

            if is_prefix:
                if item_name_lower.startswith(name_to_find_lower):
                    return item
            else:
                if item_name_lower == name_to_find_lower:
                    return item
        return None # No se encontró el ítem
    except Exception as e:
        print(f"Error buscando '{name_to_find}' en '{parent_id}': {e}")
        return None

def get_all_folders_in_folder(parent_id):
    """Obtiene TODAS las subcarpetas de una carpeta padre."""
    if not service: return []
    try:
        query = f"'{parent_id}' in parents and trashed=false and mimeType = 'application/vnd.google-apps.folder'"
        results = service.files().list(q=query, fields="files(id, name)").execute()
        return results.get("files", [])
    except Exception as e:
        print(f"Error obteniendo carpetas de '{parent_id}': {e}")
        return []

def get_files_in_folder(folder_id):
    """Obtiene todos los archivos (no carpetas) de una carpeta."""
    if not service: return []
    try:
        query = f"'{folder_id}' in parents and trashed=false and mimeType != 'application/vnd.google-apps.folder'"
        results = service.files().list(q=query, fields="files(id, name)").execute()
        return results.get("files", [])
    except Exception as e:
        print(f"Error obteniendo archivos de la carpeta '{folder_id}': {e}")
        return []

# --- Función Principal Actualizada ---

def get_datos_ciclo(ciclo_num, semana_num):
    """
    Obtiene los datos de todas las asignaturas de un ciclo para una semana específica.
    """
    ciclo_folder = find_item_in_folder(folder_id, f"{ciclo_num} ", is_prefix=True, mime_type="application/vnd.google-apps.folder")
    if not ciclo_folder:
        return {"error": f"Ciclo {ciclo_num} no encontrado."}

    asignaturas = get_all_folders_in_folder(ciclo_folder['id'])
    if not asignaturas:
        return {"error": f"No se encontraron asignaturas en el ciclo {ciclo_num}."}

    resultados_ciclo = []
    for asignatura_folder in asignaturas:
        print(f"Procesando asignatura: {asignatura_folder['name']}...")
        datos_asignatura = {
            "asignatura": {"nombre": asignatura_folder['name'], "id": asignatura_folder['id']}
        }

        # Búsqueda de sílabos (ahora insensible a mayúsculas)
        # Buscamos la carpeta "1. silabo..." y extraemos TODOS los archivos de adentro
        silabo_folder = find_item_in_folder(asignatura_folder['id'], "1. silabo del curso", mime_type="application/vnd.google-apps.folder")
        if silabo_folder:
            datos_asignatura["silabos"] = [{"nombre": f['name'], "id": f['id']} for f in get_files_in_folder(silabo_folder['id'])]
        else:
            datos_asignatura["silabos"] = [] # Si no encuentra la carpeta, devuelve una lista vacía

        # Búsqueda de material de enseñanza (ahora insensible a mayúsculas)
        material_folder = find_item_in_folder(asignatura_folder['id'], "2. material de enseñanza", mime_type="application/vnd.google-apps.folder")
        if not material_folder:
            datos_asignatura["material_semana"] = {"error": "Carpeta '2. Material de Enseñanza' no encontrada."}
            resultados_ciclo.append(datos_asignatura)
            continue

        # Búsqueda de la semana específica (ahora insensible a mayúsculas)
        semana_folder = find_item_in_folder(material_folder['id'], f"semana {semana_num}", mime_type="application/vnd.google-apps.folder")

        if not semana_folder:
            for subfolder_name in ["teoría", "práctica"]:
                subfolder = find_item_in_folder(material_folder['id'], subfolder_name, mime_type="application/vnd.google-apps.folder")
                if subfolder:
                    semana_folder = find_item_in_folder(subfolder['id'], f"semana {semana_num}", mime_type="application/vnd.google-apps.folder")
                    if semana_folder:
                        break

        if semana_folder:
            archivos_semana = get_files_in_folder(semana_folder['id'])
            estado = "Completo" if archivos_semana else "Incompleto"
            datos_asignatura["material_semana"] = {
                "semana": semana_folder['name'],
                "id": semana_folder['id'],
                "estado": estado,
                "archivos": [{"nombre": f['name'], "id": f['id']} for f in archivos_semana]
            }
        else:
            datos_asignatura["material_semana"] = {"error": f"No se encontró la carpeta 'Semana {semana_num}'."}

        resultados_ciclo.append(datos_asignatura)

    return resultados_ciclo

if __name__ == "__main__":
    import uvicorn
    print("Iniciando servidor FastAPI en http://127.0.0.1:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
