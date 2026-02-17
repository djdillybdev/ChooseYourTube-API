from typing import Annotated

from .db.session import get_db_session
from arq.connections import ArqRedis
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from .clients.youtube import get_youtube_api, YouTubeAPI
from .queue import get_arq_redis
from .auth.deps import current_active_user
from .auth.models import User


DBSessionDep = Annotated[AsyncSession, Depends(get_db_session)]

YouTubeAPIDep = Annotated[YouTubeAPI, Depends(get_youtube_api)]

ArqDep = Annotated[ArqRedis, Depends(get_arq_redis)]

CurrentUserDep = Annotated[User, Depends(current_active_user)]
