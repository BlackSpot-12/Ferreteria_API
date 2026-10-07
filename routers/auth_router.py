from fastapi import APIRouter, HTTPException, status
from sqlmodel import select

from config.segurity import create_access_token
from config.segurity_Dependencia import OAuth2FormDeDependencia
from config.session_Dependencia import SessionDeDependencia
from lib.pwd import verify_password
from models.usuario import Usuario

router = APIRouter()


@router.post("/auth/login", status_code=status.HTTP_200_OK)
async def login(form_data: OAuth2FormDeDependencia, session: SessionDeDependencia):
    correo = form_data.username.strip()
    consulta = select(Usuario).where(Usuario.correo == correo)
    usuario = session.exec(consulta).first()

    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas"
        )

    if not verify_password(form_data.password, usuario.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas"
        )

    token = create_access_token(
        data={
            "id": usuario.id_usuario,
            "username": usuario.correo,
            "correo": usuario.correo,
            "id_rol": usuario.rol_id,
            "rol_id": usuario.rol_id,
        }
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "id_rol": usuario.rol_id,
        "nombre": usuario.Nombres,
        "correo": usuario.correo,
    }
