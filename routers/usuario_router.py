from fastapi import APIRouter, HTTPException, status
from sqlmodel import select

from config.segurity_Dependencia import Token_Dependencia
from config.session_Dependencia import SessionDeDependencia
from lib.pwd import get_password_hash
from models.usuario import Usuario, UsuarioCreate, UsuarioRegistroCliente, UsuarioResponse

router = APIRouter()


@router.post("/usuarios/registro", response_model=UsuarioResponse, status_code=status.HTTP_201_CREATED)
async def registrar_cliente(datos_cliente: UsuarioRegistroCliente, session: SessionDeDependencia):
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
    session.commit()
    session.refresh(nuevo_cliente)
    return nuevo_cliente


@router.post("/usuarios", response_model=UsuarioResponse, status_code=status.HTTP_201_CREATED)
async def crear_empleado_admin(datos_usuario: UsuarioCreate, session: SessionDeDependencia, token: Token_Dependencia):
    if token["id_rol"] != 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo los propietarios pueden crear empleados",
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
    session.commit()
    session.refresh(nuevo_usuario)
    return nuevo_usuario


@router.get("/usuarios/me", response_model=UsuarioResponse, status_code=status.HTTP_200_OK)
async def obtener_perfil_actual(session: SessionDeDependencia, token: Token_Dependencia):
    usuario = session.exec(select(Usuario).where(Usuario.id_usuario == token["id"])).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return usuario
