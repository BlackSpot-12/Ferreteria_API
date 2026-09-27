from sqlmodel import Session
from fastapi import Depends
from typing import Annotated
from config.db import engine


def get_session():
    with Session(engine) as session:
        yield session


SessionDeDependencia = Annotated[Session, Depends(get_session)]
