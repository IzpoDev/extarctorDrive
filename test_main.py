import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, MagicMock
from main import app
import io

client = TestClient(app)


# Mock del servicio de Google Drive
@pytest.fixture
def mock_drive_service():
    with patch('main.service') as mock_service:
        mock_service.files().list().execute.return_value = {'files': []}
        yield mock_service


# Tests para endpoint raíz
def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "API de extracción de Google Drive funcionando correctamente"}


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "google_drive_extractor"}


# Tests para /convertir-documento
def test_convertir_documento_docx():
    # Crear un archivo DOCX mock
    mock_file = io.BytesIO(b"fake docx content")

    with patch('main.Document') as mock_doc:
        mock_paragraph = MagicMock()
        mock_paragraph.text = "Texto de prueba"
        mock_doc.return_value.paragraphs = [mock_paragraph]

        response = client.post(
            "/convertir-documento",
            files={"file": ("test.docx", mock_file,
                            "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
        )

        assert response.status_code == 200
        assert "text" in response.json()


def test_convertir_documento_pptx():
    mock_file = io.BytesIO(b"fake pptx content")

    with patch('main.Presentation') as mock_prs:
        mock_shape = MagicMock()
        mock_shape.has_text_frame = True
        mock_shape.text_frame.text = "Texto de presentación"

        mock_slide = MagicMock()
        mock_slide.shapes = [mock_shape]

        mock_prs.return_value.slides = [mock_slide]

        response = client.post(
            "/convertir-documento",
            files={"file": ("test.pptx", mock_file,
                            "application/vnd.openxmlformats-officedocument.presentationml.presentation")}
        )

        assert response.status_code == 200
        assert "text" in response.json()


def test_convertir_documento_formato_no_soportado():
    mock_file = io.BytesIO(b"fake content")

    response = client.post(
        "/convertir-documento",
        files={"file": ("test.txt", mock_file, "text/plain")}
    )

    assert response.status_code == 400
    assert "Formato no soportado" in response.json()["detail"]


# Tests para /extraer-drive
def test_extraer_drive_sin_servicio():
    with patch('main.service', None):
        response = client.post(
            "/extraer-drive",
            json={"ciclo_num": 5, "semana_num": 10}
        )

        assert response.status_code == 500
        assert "no está autenticado" in response.json()["detail"]


def test_extraer_drive_exitoso(mock_drive_service):
    with patch('main.get_datos_ciclo') as mock_get_datos:
        mock_get_datos.return_value = [
            {
                "asignatura": "Matemáticas",
                "ciclo": 5,
                "semana": 10,
                "id_silabo": "id123",
                "id_teoria": "id456",
                "id_practica": None,
                "id_laboratorio": None,
                "estado": "pendiente"
            }
        ]

        response = client.post(
            "/extraer-drive",
            json={"ciclo_num": 5, "semana_num": 10}
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) > 0
        assert data[0]["estado"] == "pendiente"


def test_extraer_drive_datos_invalidos():
    response = client.post(
        "/extraer-drive",
        json={"ciclo_num": "invalido", "semana_num": 10}
    )

    assert response.status_code == 422


# Tests para /extraer-contenido-semanal
def test_extraer_contenido_semanal_sin_servicio():
    with patch('main.service', None):
        response = client.post(
            "/extraer-contenido-semanal",
            json={
                "asignatura": "Matemáticas",
                "id_teoria": "id123"
            }
        )

        assert response.status_code == 500
        assert "no está autenticado" in response.json()["detail"]


def test_extraer_contenido_semanal_con_todos_ids(mock_drive_service):
    with patch('main.get_files_in_folder') as mock_get_files:
        mock_get_files.return_value = [
            {"id": "file1", "name": "archivo1.pdf"},
            {"id": "file2", "name": "archivo2.docx"}
        ]

        response = client.post(
            "/extraer-contenido-semanal",
            json={
                "asignatura": "Matemáticas",
                "id_teoria": "teoria123",
                "id_practica": "practica456",
                "id_laboratorio": "lab789"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


def test_extraer_contenido_semanal_con_ids_nulos(mock_drive_service):
    with patch('main.get_files_in_folder') as mock_get_files:
        mock_get_files.return_value = [{"id": "file1", "name": "archivo1.pdf"}]

        response = client.post(
            "/extraer-contenido-semanal",
            json={
                "asignatura": "Física",
                "id_teoria": "teoria123",
                "id_practica": None,
                "id_laboratorio": None
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


def test_extraer_contenido_semanal_con_ids_vacios(mock_drive_service):
    with patch('main.get_files_in_folder') as mock_get_files:
        mock_get_files.return_value = []

        response = client.post(
            "/extraer-contenido-semanal",
            json={
                "asignatura": "Química",
                "id_teoria": "",
                "id_practica": "",
                "id_laboratorio": ""
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data == []


def test_extraer_contenido_semanal_sin_duplicados(mock_drive_service):
    with patch('main.get_files_in_folder') as mock_get_files:
        # Simular que dos carpetas tienen el mismo archivo
        mock_get_files.return_value = [{"id": "file1", "name": "archivo1.pdf"}]

        response = client.post(
            "/extraer-contenido-semanal",
            json={
                "asignatura": "Historia",
                "id_teoria": "teoria123",
                "id_practica": "practica456"
            }
        )

        assert response.status_code == 200
        data = response.json()
        # Verificar que no hay duplicados
        ids = [item["id"] for item in data]
        assert len(ids) == len(set(ids))
