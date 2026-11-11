import hashlib
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from sqlalchemy import func
from sqlmodel import select

from config.segurity import create_access_token
from config.segurity_Dependencia import Token_Dependencia
from config.segurity_Dependencia import OAuth2FormDeDependencia
from config.session_Dependencia import SessionDeDependencia
from lib.email_tasks import PASSWORD_RESET, enviar_token_restablecimiento
from lib.pwd import verify_password
from lib.pwd import get_password_hash
from models.email import EmailToken, PasswordResetApply, PasswordResetRequest
from models.security import UserAccess
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

    access = session.get(UserAccess, usuario.id_usuario)
    if access is not None and not access.activo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="La cuenta está inactiva",
        )

    token = create_access_token(
        data={
            "id": usuario.id_usuario,
            "username": usuario.correo,
            "correo": usuario.correo,
            "id_rol": usuario.rol_id,
            "rol_id": usuario.rol_id,
            "token_version": access.token_version if access is not None else 0,
        }
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "id_rol": usuario.rol_id,
        "nombre": usuario.Nombres,
        "correo": usuario.correo,
    }


@router.post("/auth/logout-all", status_code=status.HTTP_200_OK)
async def cerrar_todas_las_sesiones(
    session: SessionDeDependencia,
    token: Token_Dependencia,
):
    access = session.get(UserAccess, token["id"])
    if access is None:
        access = UserAccess(usuario_id=token["id"], token_version=1)
    else:
        access.token_version += 1
    session.add(access)
    session.commit()
    return {"detail": "Se revocaron todas las sesiones del usuario"}


@router.post("/auth/olvide-password", status_code=status.HTTP_200_OK)
async def solicitar_restauracion_password(
    payload: PasswordResetRequest,
    session: SessionDeDependencia,
    background_tasks: BackgroundTasks,
):
    user = session.exec(
        select(Usuario).where(func.lower(Usuario.correo) == str(payload.correo).lower())
    ).first()
    if user is not None:
        background_tasks.add_task(enviar_token_restablecimiento, user.id_usuario)
    return {
        "detail": (
            "Si el correo está registrado, recibirás instrucciones para "
            "restablecer la contraseña"
        )
    }


@router.post("/auth/restablecer-password", status_code=status.HTTP_200_OK)
async def restablecer_password(
    payload: PasswordResetApply,
    session: SessionDeDependencia,
):
    digest = hashlib.sha256(payload.token.encode("utf-8")).hexdigest()
    reset_token = session.exec(
        select(EmailToken).where(
            EmailToken.token_hash == digest,
            EmailToken.purpose == PASSWORD_RESET,
            EmailToken.used_at.is_(None),
        ).with_for_update()
    ).first()
    now = datetime.now(timezone.utc)
    expires_at = reset_token.expires_at if reset_token is not None else None
    if (
        reset_token is None
        or (
            expires_at.replace(tzinfo=timezone.utc)
            if expires_at.tzinfo is None
            else expires_at
        )
        <= now
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token inválido o expirado",
        )

    user = session.get(Usuario, reset_token.usuario_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token inválido o expirado",
        )
    user.password_hash = get_password_hash(payload.password)
    reset_token.used_at = now
    session.add(user)
    session.add(reset_token)

    access = session.get(UserAccess, user.id_usuario)
    if access is None:
        access = UserAccess(usuario_id=user.id_usuario, token_version=1)
    else:
        access.token_version += 1
    session.add(access)

    older_tokens = session.exec(
        select(EmailToken).where(
            EmailToken.usuario_id == user.id_usuario,
            EmailToken.purpose == PASSWORD_RESET,
            EmailToken.used_at.is_(None),
        )
    ).all()
    for token in older_tokens:
        token.used_at = now
        session.add(token)
    session.commit()
    return {"detail": "La contraseña se restableció correctamente"}
