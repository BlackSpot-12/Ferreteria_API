from fastapi import APIRouter, HTTPException, status

from config.segurity_Dependencia import Token_Dependencia
from config.session_Dependencia import SessionDeDependencia
from models.configuracion import (
    ConfiguracionMayoristaUpdate,
    ConfiguracionNegocio,
)

router = APIRouter(prefix="/configuracion", tags=["Configuración"])


def _require_owner(token: dict) -> None:
    if token.get("id_rol") != 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo el propietario puede cambiar la configuración del negocio",
        )


@router.get("/mayoristas")
async def obtener_configuracion_mayorista(
    session: SessionDeDependencia,
    token: Token_Dependencia,
):
    _require_owner(token)
    config = session.get(ConfiguracionNegocio, 1)
    return {
        "umbral_mayorista": (
            config.umbral_mayorista if config is not None else None
        ),
        "prioridad_activa": (
            config is not None and config.umbral_mayorista is not None
        ),
    }


@router.put("/mayoristas")
async def actualizar_configuracion_mayorista(
    payload: ConfiguracionMayoristaUpdate,
    session: SessionDeDependencia,
    token: Token_Dependencia,
):
    _require_owner(token)
    config = session.get(ConfiguracionNegocio, 1)
    if config is None:
        config = ConfiguracionNegocio(
            id_configuracion=1,
            umbral_mayorista=payload.umbral_mayorista,
        )
    else:
        config.umbral_mayorista = payload.umbral_mayorista
    session.add(config)
    session.commit()
    session.refresh(config)
    return {
        "umbral_mayorista": config.umbral_mayorista,
        "prioridad_activa": config.umbral_mayorista is not None,
    }
