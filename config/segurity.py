from datetime import timedelta, datetime
import os
from typing import Optional
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
import jwt

load_dotenv()

SECRET_KEY_TOKEN = os.getenv("SECRET_KEY_TOKEN", "123456789")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    token = jwt.encode(payload=to_encode,
                       key=SECRET_KEY_TOKEN, algorithm=ALGORITHM)
    return token


def decode_access_token(token: str):
    payload = jwt.decode(token, key=SECRET_KEY_TOKEN, algorithms=[ALGORITHM])
    return payload


def get_current_user(token: str = Depends(oauth2_scheme)):
    credencial_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No autenticado",
        headers={"WWW-Authenticate": "Bearer"}
    )
    try:
        payload = decode_access_token(token)
        id: Optional[int] = payload.get("id")
        username: Optional[str] = payload.get("username")
        id_rol: Optional[int] = payload.get("id_rol")

        if username is None:
            raise credencial_exception

        return {"id": id, "username": username, "id_rol": id_rol}
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expirado",
            headers={"WWW-Authenticate": "Bearer"}
        )
    except jwt.InvalidTokenError:
        raise credencial_exception
