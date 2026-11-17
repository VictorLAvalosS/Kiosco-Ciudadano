"""Pruebas del versionado del modelo (conjunto de prueba fijo y activación)."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import ConjuntoPruebaFijo, Modelo
from app.servicio_modelo import (
    entrenar_nueva_version,
    etiquetas_entrenamiento,
    modelo_activo,
    reevaluar_versiones,
    version_valida_para_comparacion,
)
from tests.conftest import crear_dataset_etiquetado


def test_entrenamiento_reserva_y_excluye_el_conjunto_prueba_fijo(db: Session) -> None:
    crear_dataset_etiquetado(db, por_categoria=5)  # 40 solicitudes nuevas
    # Total del pool de entrenamiento: incluye los datos ya presentes en la base,
    # pero excluye el conjunto de prueba EXTERNO (que nunca se entrena).
    total = len(etiquetas_entrenamiento(db))

    resultado = entrenar_nueva_version(db, forzar=True)
    modelo = resultado["version_nueva"]

    ids_fijos = set(db.scalars(select(ConjuntoPruebaFijo.solicitud_id)).all())
    assert len(ids_fijos) > 0, "Debe reservarse un conjunto de prueba fijo."

    # El entrenamiento excluye los ids fijos: entrenamiento + prueba == total vigente.
    assert modelo.n_prueba == len(ids_fijos)
    assert modelo.n_entrenamiento + modelo.n_prueba == total


def test_no_activa_una_version_peor(db: Session) -> None:
    crear_dataset_etiquetado(db, por_categoria=5)

    primera = entrenar_nueva_version(db, forzar=True)
    version_uno = primera["version_nueva"]
    assert version_uno.activo is True

    # Forzamos un F1 artificialmente alto en la versión activa para simular que la
    # nueva no la supera: entonces NO debe activarse.
    version_uno.f1_macro = 0.999
    db.commit()

    segunda = entrenar_nueva_version(db, forzar=False)
    assert segunda["activado"] is False
    assert segunda["version_nueva"].activo is False

    activo = modelo_activo(db)
    assert activo is not None
    assert activo.version == version_uno.version


def test_activacion_forzada_permite_versiones_peores(db: Session) -> None:
    crear_dataset_etiquetado(db, por_categoria=5)

    primera = entrenar_nueva_version(db, forzar=True)
    version_uno = primera["version_nueva"]
    version_uno.f1_macro = 0.999
    db.commit()

    segunda = entrenar_nueva_version(db, forzar=True)
    assert segunda["activado"] is True
    assert segunda["version_nueva"].activo is True

    activo = modelo_activo(db)
    assert activo is not None
    assert activo.version == segunda["version_nueva"].version
    # La versión anterior debe quedar desactivada.
    anterior = db.scalars(select(Modelo).where(Modelo.version == version_uno.version)).first()
    assert anterior is not None and anterior.activo is False


def test_segunda_version_evalua_con_el_mismo_conjunto_fijo(db: Session) -> None:
    crear_dataset_etiquetado(db, por_categoria=5)

    entrenar_nueva_version(db, forzar=True)
    ids_primera = set(db.scalars(select(ConjuntoPruebaFijo.solicitud_id)).all())

    entrenar_nueva_version(db, forzar=True)
    ids_segunda = set(db.scalars(select(ConjuntoPruebaFijo.solicitud_id)).all())

    # El conjunto de prueba fijo no cambia entre versiones (comparabilidad).
    assert ids_primera == ids_segunda


def test_entrenamiento_y_prueba_son_disjuntos(db: Session) -> None:
    """Garantiza que ninguna versión comparable usó ejemplos del conjunto de prueba."""
    crear_dataset_etiquetado(db, por_categoria=5)

    entrenar_nueva_version(db, forzar=True)
    for modelo in db.scalars(select(Modelo)).all():
        if not modelo.valida_para_comparacion:
            continue
        ids_fijos = set(db.scalars(select(ConjuntoPruebaFijo.solicitud_id)).all())
        ids_entrenamiento = set(int(x) for x in (modelo.ids_entrenamiento or []))
        assert ids_entrenamiento, "Toda versión comparable debe registrar sus ids de entrenamiento."
        assert ids_entrenamiento.isdisjoint(ids_fijos), (
            f"La versión {modelo.version} comparte ejemplos entre entrenamiento y prueba."
        )


def test_reevaluar_marca_invalida_la_version_contaminada(db: Session) -> None:
    crear_dataset_etiquetado(db, por_categoria=5)

    resultado = entrenar_nueva_version(db, forzar=True)
    modelo = resultado["version_nueva"]
    ids_fijos = set(db.scalars(select(ConjuntoPruebaFijo.solicitud_id)).all())

    # Simula una versión antigua entrenada incluyendo datos del conjunto de prueba.
    modelo.ids_entrenamiento = sorted(ids_fijos | set(int(x) for x in (modelo.ids_entrenamiento or [])))
    db.commit()

    reevaluar_versiones(db, regenerar_prueba=False)
    db.refresh(modelo)

    assert modelo.valida_para_comparacion is False
    assert "conjunto de prueba" in modelo.motivo_invalidez


def test_valida_para_comparacion_detecta_interseccion() -> None:
    modelo = Modelo(
        version="vtest",
        algoritmo="LinearSVC",
        hiperparametros={},
        n_entrenamiento=3,
        ids_entrenamiento=[1, 2, 3],
        modelo_binario=b"",
    )
    valida, motivo = version_valida_para_comparacion(modelo, {2, 5, 6}, tamano_pool=100)
    assert valida is False
    assert motivo == "entrenada con datos del conjunto de prueba"

    # Sin intersección y con ids registrados → comparable.
    valida2, motivo2 = version_valida_para_comparacion(modelo, {7, 8}, tamano_pool=100)
    assert valida2 is True and motivo2 == ""


def test_la_api_no_activa_sin_forzar_una_version_no_comparable(
    db: Session, client: TestClient
) -> None:
    crear_dataset_etiquetado(db, por_categoria=5)

    resultado = entrenar_nueva_version(db, forzar=True)
    modelo = resultado["version_nueva"]
    modelo.valida_para_comparacion = False
    modelo.motivo_invalidez = "entrenada con datos del conjunto de prueba"
    db.commit()

    # Si la API exige clave, se envía la cabecera configurada.
    cabeceras = {"X-API-Key": settings.api_key} if settings.api_key else {}

    rechazo = client.post(f"/api/modelo/{modelo.version}/activar", headers=cabeceras)
    assert rechazo.status_code == 409

    forzado = client.post(
        f"/api/modelo/{modelo.version}/activar?forzar=true", headers=cabeceras
    )
    assert forzado.status_code == 200
