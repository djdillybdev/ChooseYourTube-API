import uuid

from fastapi_users.db import SQLAlchemyBaseUserTableUUID

from app.db.base import Base


class User(SQLAlchemyBaseUserTableUUID, Base):
    __tablename__ = "users"
