from fastapi import APIRouter, HTTPException, status
from sqlmodel import select
from config.session_Dependencia import SessionDeDependencia
from config.segurity_Dependencia import Token_Dependencia
from models.usuario import Usuario, UsuarioCreate, UsuarioRegistroCliente, UsuarioResponse
from lib.pwd import get_password_hash

router = APIRouter()


@router.post("/usuarios/registro", response_model=UsuarioResponse, status_code=status.HTTP_201_CREATED)
async def registrar_cliente(datos_cliente: UsuarioRegistroCliente, session: SessionDeDependencia):
    if session.exec(select(Usuario).where(Usuario.username == datos_cliente.username)).first():
        raise HTTPException(
            status_code=400, detail="El nombre de usuario ya existe")

    if session.exec(select(Usuario).where(Usuario.correo == datos_cliente.correo)).first():
        raise HTTPException(
            status_code=400, detail="El correo ya está registrado")

    nuevo_cliente = Usuario(
        username=datos_cliente.username,
        password=get_password_hash(datos_cliente.password),
        nombre=datos_cliente.nombre,
        apellido=datos_cliente.apellido,
        telefono=datos_cliente.telefono,
        correo=datos_cliente.correo,
        id_rol=3
    )
    session.add(nuevo_cliente)
    session.commit()
    session.refresh(nuevo_cliente)
    return nuevo_cliente


@router.post("/usuarios", response_model=UsuarioResponse, status_code=status.HTTP_201_CREATED)
async def crear_empleado_admin(datos_usuario: UsuarioCreate, session: SessionDeDependencia, token: Token_Dependencia):
    if token['id_rol'] != 1:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Solo los propietarios pueden crear empleados")

    if session.exec(select(Usuario).where(Usuario.username == datos_usuario.username)).first():
        raise HTTPException(
            status_code=400, detail="El nombre de usuario ya existe")

    nuevo_usuario = Usuario(
        username=datos_usuario.username,
        password=get_password_hash(datos_usuario.password),
        nombre=datos_usuario.nombre,
        apellido=datos_usuario.apellido,
        telefono=datos_usuario.telefono,
        correo=datos_usuario.correo,
        id_rol=datos_usuario.id_rol
    )
    session.add(nuevo_usuario)
    session.commit()
    session.refresh(nuevo_usuario)
    return nuevo_usuario


@router.get("/usuarios/me", response_model=UsuarioResponse, status_code=status.HTTP_200_OK)
async def obtener_perfil_actual(session: SessionDeDependencia, token: Token_Dependencia):
    usuario = session.exec(select(Usuario).where(
        Usuario.id == token['id'])).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return usuario
