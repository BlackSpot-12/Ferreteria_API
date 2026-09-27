from fastapi import APIRouter, status, HTTPException
from config.session_Dependencia import SessionDeDependencia
from sqlmodel import select
from models.usuario import Usuario
from lib.pwd import verify_password
from config.segurity import create_access_token
from config.segurity_Dependencia import OAuth2FormDeDependencia

router = APIRouter()


@router.post("/auth/login", status_code=status.HTTP_200_OK)
async def login(form_data: OAuth2FormDeDependencia, session: SessionDeDependencia):
    consulta = select(Usuario).where(Usuario.username == form_data.username)
    usuario = session.exec(consulta).first()

    if not usuario or not usuario.estado:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas o usuario inactivo"
        )

    if not verify_password(form_data.password, usuario.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas o usuario inactivo"
        )

    token = create_access_token(
        data={
            "id": usuario.id,
            "username": usuario.username,
            "id_rol": usuario.id_rol
        }
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "id_rol": usuario.id_rol,
        "nombre": usuario.nombre
    }
