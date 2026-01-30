import logging
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.config import settings
from .routers import channels, videos, folders, tags

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


@app.get("/")
async def root():
    return {"message": "Hello World"}
