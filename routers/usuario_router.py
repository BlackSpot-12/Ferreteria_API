import hashlib
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from sqlmodel import select

from config.segurity_Dependencia import Token_Dependencia
from config.session_Dependencia import SessionDeDependencia
from lib.email_tasks import enviar_token_verificacion
from lib.pwd import get_password_hash
from models.email import EmailToken, EmailVerificationApply, UserEmailVerification
from models.rol import Rol
from models.security import UserAccess
from models.usuario import (
    Usuario,
    UsuarioAdminResponse,
    UsuarioCreate,
    UsuarioEstadoUpdate,
    UsuarioRegistroCliente,
    UsuarioResponse,
)

router = APIRouter()


@router.post("/usuarios/registro", response_model=UsuarioResponse, status_code=status.HTTP_201_CREATED)
async def registrar_cliente(
    datos_cliente: UsuarioRegistroCliente,
    session: SessionDeDependencia,
    background_tasks: BackgroundTasks,
):
    if session.exec(select(Usuario).where(Usuario.correo == datos_cliente.correo)).first():
        raise HTTPException(status_code=400, detail="El correo ya está registrado")

    nuevo_cliente = Usuario(
        Nombres=datos_cliente.Nombres,
        apellidos=datos_cliente.apellidos,
        correo=datos_cliente.correo,
        password_hash=get_password_hash(datos_cliente.password),
        rol_id=3,
    )
    session.add(nuevo_cliente)
    session.flush()
    session.add(
        UserEmailVerification(
            usuario_id=nuevo_cliente.id_usuario,
            verificado=False,
            last_sent_at=datetime.now(timezone.utc),
        )
    )
    session.commit()
    session.refresh(nuevo_cliente)
    background_tasks.add_task(enviar_token_verificacion, nuevo_cliente.id_usuario)
    return nuevo_cliente


@router.post("/usuarios", response_model=UsuarioResponse, status_code=status.HTTP_201_CREATED)
async def crear_empleado_admin(datos_usuario: UsuarioCreate, session: SessionDeDependencia, token: Token_Dependencia):
    if token["id_rol"] != 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo los propietarios pueden crear empleados",
        )
    if datos_usuario.rol_id != 2 or session.get(Rol, datos_usuario.rol_id) is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Este endpoint solo permite crear usuarios con rol de empleado",
        )

    if session.exec(select(Usuario).where(Usuario.correo == datos_usuario.correo)).first():
        raise HTTPException(status_code=400, detail="El correo ya está registrado")

    nuevo_usuario = Usuario(
        Nombres=datos_usuario.Nombres,
        apellidos=datos_usuario.apellidos,
        correo=datos_usuario.correo,
        password_hash=get_password_hash(datos_usuario.password),
        rol_id=datos_usuario.rol_id,
    )
    session.add(nuevo_usuario)
    session.flush()
    session.add(
        UserEmailVerification(
            usuario_id=nuevo_usuario.id_usuario,
            verificado=True,
            verified_at=datetime.now(timezone.utc),
        )
    )
    session.commit()
    session.refresh(nuevo_usuario)
    return nuevo_usuario


@router.get("/usuarios/me", response_model=UsuarioResponse, status_code=status.HTTP_200_OK)
async def obtener_perfil_actual(session: SessionDeDependencia, token: Token_Dependencia):
    usuario = session.exec(select(Usuario).where(Usuario.id_usuario == token["id"])).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return usuario


@router.post("/usuarios/verificar-correo", status_code=status.HTTP_200_OK)
async def verificar_correo(
    payload: EmailVerificationApply,
    session: SessionDeDependencia,
):
    digest = hashlib.sha256(payload.token.encode("utf-8")).hexdigest()
    token = session.exec(
        select(EmailToken).where(
            EmailToken.token_hash == digest,
            EmailToken.purpose == "email_verification",
            EmailToken.used_at.is_(None),
        ).with_for_update()
    ).first()
    now = datetime.now(timezone.utc)
    if token is None or _utc(token.expires_at) <= now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token inválido o expirado",
        )
    verification = session.get(UserEmailVerification, token.usuario_id)
    if verification is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token inválido o expirado",
        )
    verification.verificado = True
    verification.verified_at = now
    token.used_at = now
    session.add(verification)
    session.add(token)
    session.commit()
    return {"detail": "Correo verificado"}


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


@router.get("/usuarios/me/verificacion", status_code=status.HTTP_200_OK)
async def estado_verificacion_correo(
    session: SessionDeDependencia,
    token: Token_Dependencia,
):
    verification = session.get(UserEmailVerification, token["id"])
    return {
        "verificado": verification.verificado if verification else True,
        "verificado_en": verification.verified_at if verification else None,
    }


@router.post("/usuarios/me/reenviar-verificacion", status_code=status.HTTP_200_OK)
async def reenviar_verificacion_correo(
    session: SessionDeDependencia,
    token: Token_Dependencia,
    background_tasks: BackgroundTasks,
):
    verification = session.exec(
        select(UserEmailVerification)
        .where(UserEmailVerification.usuario_id == token["id"])
        .with_for_update()
    ).first()
    if verification is None or verification.verificado:
        return {"detail": "El correo ya está verificado"}
    now = datetime.now(timezone.utc)
    if (
        verification.last_sent_at is not None
        and now - _utc(verification.last_sent_at)
        < timedelta(minutes=2)
    ):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Espera al menos dos minutos antes de solicitar otro correo",
        )
    verification.last_sent_at = now
    session.add(verification)
    session.commit()
    background_tasks.add_task(enviar_token_verificacion, token["id"])
    return {"detail": "Si el correo está pendiente de verificación, recibirás un mensaje"}


def _require_user_management_read(token: dict) -> None:
    if token.get("id_rol") not in (1, 2):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo empleados y propietarios pueden consultar usuarios",
        )


def _require_owner(token: dict) -> None:
    if token.get("id_rol") != 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo el propietario puede administrar cuentas",
        )


@router.get(
    "/usuarios",
    response_model=list[UsuarioAdminResponse],
    status_code=status.HTTP_200_OK,
)
async def listar_usuarios(
    session: SessionDeDependencia,
    token: Token_Dependencia,
):
    _require_user_management_read(token)
    users = session.exec(select(Usuario).order_by(Usuario.id_usuario)).all()
    accesses = {
        access.usuario_id: access
        for access in session.exec(select(UserAccess)).all()
    }
    return [
        UsuarioAdminResponse.model_validate(
            {
                **user.model_dump(),
                "activo": (
                    accesses[user.id_usuario].activo
                    if user.id_usuario in accesses
                    else True
                ),
            }
        )
        for user in users
    ]


@router.put(
    "/usuarios/{usuario_id}/estado",
    response_model=UsuarioAdminResponse,
    status_code=status.HTTP_200_OK,
)
async def actualizar_estado_usuario(
    usuario_id: int,
    payload: UsuarioEstadoUpdate,
    session: SessionDeDependencia,
    token: Token_Dependencia,
):
    _require_owner(token)
    usuario = session.get(Usuario, usuario_id)
    if usuario is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if usuario.rol_id == 1 and not payload.activo:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No se pueden inactivar cuentas de propietario",
        )
    if usuario_id == token.get("id") and not payload.activo:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No puede inactivar la cuenta con la que inició sesión",
        )

    access = session.get(UserAccess, usuario_id)
    if access is None:
        access = UserAccess(usuario_id=usuario_id)
    if access.activo != payload.activo:
        access.activo = payload.activo
        access.token_version += 1
    session.add(access)
    session.commit()
    session.refresh(usuario)
    session.refresh(access)
    return UsuarioAdminResponse.model_validate(
        {**usuario.model_dump(), "activo": access.activo}
    )


@router.post(
    "/usuarios/{usuario_id}/logout-all",
    status_code=status.HTTP_200_OK,
)
async def revocar_sesiones_usuario(
    usuario_id: int,
    session: SessionDeDependencia,
    token: Token_Dependencia,
):
    _require_owner(token)
    usuario = session.get(Usuario, usuario_id)
    if usuario is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    access = session.get(UserAccess, usuario_id)
    if access is None:
        access = UserAccess(usuario_id=usuario_id, token_version=1)
    else:
        access.token_version += 1
    session.add(access)
    session.commit()
    return {"detail": "Se revocaron todas las sesiones del usuario"}
