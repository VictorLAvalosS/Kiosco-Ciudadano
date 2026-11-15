"""Pruebas de los endpoints HTTP de la API (cliente de pruebas transaccional)."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_salud(client: TestClient) -> None:
    respuesta = client.get("/api/salud")
    assert respuesta.status_code == 200
    assert respuesta.json()["estado"] == "ok"


def test_listar_categorias(client: TestClient) -> None:
    respuesta = client.get("/api/categorias")
    assert respuesta.status_code == 200
    categorias = respuesta.json()
    assert len(categorias) == 8
    assert categorias[0]["clave"] == "alumbrado"
    assert all(c["departamento"] for c in categorias)


def test_crear_solicitud_devuelve_ticket(client: TestClient) -> None:
    respuesta = client.post(
        "/api/solicitudes",
        json={"texto": "Hay una fuga de agua potable en la esquina", "otb": "OTB Prueba"},
    )
    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["ticket"].startswith("SC-")
    assert datos["estado"] == "Sin asignar"
    assert datos["origen"] == "kiosco"
    assert datos["etiquetada"] is False
    assert "prediccion_detalle" in datos
    if datos["prediccion_detalle"] is not None:
        assert datos["prediccion_detalle"]["texto"] == "Hay una fuga de agua potable en la esquina"


def test_etiquetar_solicitud_conserva_historial(client: TestClient) -> None:
    creada = client.post(
        "/api/solicitudes",
        json={"texto": "El poste de luz esta apagado en toda la cuadra"},
    ).json()

    respuesta = client.post(
        f"/api/solicitudes/{creada['id']}/etiqueta",
        json={"categoria_clave": "alumbrado", "prioridad": "ALTA", "etiquetado_por": "Ana"},
    )
    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["etiquetada"] is True
    assert datos["etiqueta"]["categoria_clave"] == "alumbrado"
    assert datos["etiqueta"]["prioridad"] == "ALTA"
    assert datos["etiqueta"]["etiquetado_por"] == "Ana"

    # Corregir la etiqueta crea una nueva vigente y desactiva la anterior.
    corregida = client.post(
        f"/api/solicitudes/{creada['id']}/etiqueta",
        json={"categoria_clave": "calles", "prioridad": "MEDIA", "etiquetado_por": "Luis"},
    ).json()
    assert corregida["etiqueta"]["categoria_clave"] == "calles"
    assert corregida["etiqueta"]["etiquetado_por"] == "Luis"


def test_listar_solicitudes_con_filtro_etiquetada(client: TestClient) -> None:
    client.post("/api/solicitudes", json={"texto": "Basura acumulada junto al parque"})
    respuesta = client.get("/api/solicitudes", params={"etiquetada": "false"})
    assert respuesta.status_code == 200
    assert isinstance(respuesta.json(), list)


def test_importar_csv_por_endpoint(client: TestClient) -> None:
    csv = (
        "ID,Solicitud,Categoría,Prioridad\n"
        "1,Canal de desague pluvial tapado,Drenaje y desagüe pluvial,ALTA\n"
        "2,Categoria invalida,Categoria Fantasma,ALTA\n"
    )
    respuesta = client.post(
        "/api/solicitudes/importar",
        content=csv.encode("utf-8"),
        headers={"content-type": "text/csv"},
    )
    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["total_filas"] == 2
    assert datos["importadas"] == 1
    assert len(datos["invalidas"]) == 1


def test_guia_de_etiquetado(client: TestClient) -> None:
    respuesta = client.get("/api/etiquetado/guia")
    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert len(datos["prioridades"]) == 3
    assert any("Drenaje" in d["categoria"] for d in datos["desambiguaciones"])


def test_cola_de_etiquetado(client: TestClient) -> None:
    respuesta = client.get("/api/etiquetado/cola")
    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert "items" in datos
    assert "total_pendientes" in datos


def test_estadisticas(client: TestClient) -> None:
    respuesta = client.get("/api/estadisticas")
    assert respuesta.status_code == 200
    datos = respuesta.json()
    for clave in (
        "total_solicitudes",
        "etiquetadas",
        "sin_etiquetar",
        "por_categoria",
        "por_etiquetador",
        "progreso_por_categoria",
    ):
        assert clave in datos
    assert len(datos["por_categoria"]) == 8


def test_modelo_activo_responde_sin_error(client: TestClient) -> None:
    respuesta = client.get("/api/modelo/activo")
    assert respuesta.status_code == 200


def test_version_inexistente_da_404(client: TestClient) -> None:
    respuesta = client.post("/api/modelo/v999/activar")
    assert respuesta.status_code == 404
