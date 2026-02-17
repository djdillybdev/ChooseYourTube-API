import logging
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth import auth_backend, fastapi_users
from app.auth.schemas import UserCreate, UserRead, UserUpdate
from .core.config import settings
from .routers import channels, videos, folders, tags, playlists, health

logging.basicConfig(
    stream=sys.stdout, level=logging.DEBUG if settings.debug_logs else logging.INFO
)

origins = [
    "https://localhost:3000",
    "http://localhost:3000",
    "http://localhost:5173",
]


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(channels.router)
app.include_router(videos.router)
app.include_router(folders.router)
app.include_router(tags.router)
app.include_router(playlists.router)
app.include_router(health.router)

app.include_router(
    fastapi_users.get_auth_router(auth_backend),
    prefix="/auth/jwt",
    tags=["auth"],
)
app.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate),
    prefix="/auth",
    tags=["auth"],
)
app.include_router(
    fastapi_users.get_reset_password_router(),
    prefix="/auth",
    tags=["auth"],
)
app.include_router(
    fastapi_users.get_verify_router(UserRead),
    prefix="/auth",
    tags=["auth"],
)
app.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate),
    prefix="/users",
    tags=["users"],
)


@app.get("/")
async def root():
    return {"message": "Hello World"}
