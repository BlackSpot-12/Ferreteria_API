from datetime import datetime, timedelta, timezone
import os
from typing import Optional

from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
import jwt
from sqlmodel import Session

from config.db import engine
from models.usuario import Usuario

load_dotenv()

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


def _secret_key() -> str:
    secret_key = os.getenv("SECRET_KEY_TOKEN")
    if not secret_key or len(secret_key) < 32:
        raise RuntimeError(
            "SECRET_KEY_TOKEN debe configurarse con al menos 32 caracteres "
            "aleatorios antes de iniciar la API."
        )
    return secret_key


def validate_token_config() -> None:
    _secret_key()


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(
        payload=to_encode,
        key=_secret_key(),
        algorithm=ALGORITHM,
    )


def decode_access_token(token: str):
    return jwt.decode(token, key=_secret_key(), algorithms=[ALGORITHM])


def get_current_user(token: str = Depends(oauth2_scheme)):
    credential_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No autenticado",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        user_id = payload.get("id")
        if (
            not isinstance(user_id, int)
            or isinstance(user_id, bool)
            or user_id <= 0
        ):
            raise credential_exception

        with Session(engine) as session:
            user = session.get(Usuario, user_id)
        if user is None:
            raise credential_exception

        return {
            "id": user.id_usuario,
            "username": user.correo,
            "id_rol": user.rol_id,
            "rol_id": user.rol_id,
        }
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise credential_exception
