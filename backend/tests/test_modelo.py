"""Pruebas del versionado del modelo (conjunto de prueba fijo y activación)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ConjuntoPruebaFijo, Modelo
from app.servicio_modelo import entrenar_nueva_version, etiquetas_vigentes, modelo_activo
from tests.conftest import crear_dataset_etiquetado


def test_entrenamiento_reserva_y_excluye_el_conjunto_prueba_fijo(db: Session) -> None:
    crear_dataset_etiquetado(db, por_categoria=5)  # 40 solicitudes nuevas
    # Total de etiquetas vigentes: incluye los datos ya presentes en la base.
    total = len(etiquetas_vigentes(db))

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
