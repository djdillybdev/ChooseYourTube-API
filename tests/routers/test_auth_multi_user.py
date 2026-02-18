import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.db.models.channel import Channel
from app.db.models.playlist import Playlist
from app.db.models.video import Video
from app.db.session import get_db_session
from app.main import app
from app.clients.youtube import get_youtube_api
from app.queue import get_arq_redis


@pytest.fixture
def auth_client(db_session, mock_youtube_api, mock_arq_redis):
    async def override_get_db_session():
        yield db_session

    app.dependency_overrides[get_db_session] = override_get_db_session
    app.dependency_overrides[get_youtube_api] = lambda: mock_youtube_api
    app.dependency_overrides[get_arq_redis] = lambda: mock_arq_redis

    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


def _register(client: TestClient, email: str, password: str = "testpassword123"):
    response = client.post(
        "/auth/register",
        json={"email": email, "password": password},
    )
    assert response.status_code in (201, 400)
    return response


def _login_token(client: TestClient, email: str, password: str = "testpassword123") -> str:
    response = client.post(
        "/auth/jwt/login",
        data={"username": email, "password": password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
class TestMultiUserAuth:
    async def test_protected_routes_require_auth(self, auth_client):
        response = auth_client.get("/channels/")
        assert response.status_code == 401

    async def test_users_only_see_their_own_data(self, auth_client, db_session):
        user_1_email = "user1@example.com"
        user_2_email = "user2@example.com"

        user_1 = _register(auth_client, user_1_email).json()
        user_2 = _register(auth_client, user_2_email).json()

        token_1 = _login_token(auth_client, user_1_email)
        token_2 = _login_token(auth_client, user_2_email)

        owner_1 = str(uuid.UUID(user_1["id"]))
        owner_2 = str(uuid.UUID(user_2["id"]))

        channel_1 = Channel(
            owner_id=owner_1,
            id="UC_owner_1",
            handle="owner1",
            title="Owner 1 Channel",
            uploads_playlist_id="UU_owner_1",
        )
        channel_2 = Channel(
            owner_id=owner_2,
            id="UC_owner_2",
            handle="owner2",
            title="Owner 2 Channel",
            uploads_playlist_id="UU_owner_2",
        )
        db_session.add(channel_1)
        db_session.add(channel_2)
        await db_session.commit()

        db_session.add(
            Video(
                owner_id=owner_1,
                id="video_owner_1",
                channel_id=channel_1.id,
                title="Owner 1 Video",
                description="v1",
                published_at=datetime.now(timezone.utc),
                duration_seconds=100,
                is_short=False,
            )
        )
        db_session.add(
            Video(
                owner_id=owner_2,
                id="video_owner_2",
                channel_id=channel_2.id,
                title="Owner 2 Video",
                description="v2",
                published_at=datetime.now(timezone.utc),
                duration_seconds=120,
                is_short=False,
            )
        )
        db_session.add(Playlist(id="playlist_owner_1", owner_id=owner_1, name="P1"))
        db_session.add(Playlist(id="playlist_owner_2", owner_id=owner_2, name="P2"))
        await db_session.commit()

        resp_tag_1 = auth_client.post(
            "/tags/",
            json={"name": "tag-user-1"},
            headers=_auth_headers(token_1),
        )
        assert resp_tag_1.status_code == 201

        resp_tag_2 = auth_client.post(
            "/tags/",
            json={"name": "tag-user-2"},
            headers=_auth_headers(token_2),
        )
        assert resp_tag_2.status_code == 201

        resp_folder_1 = auth_client.post(
            "/folders/",
            json={"name": "folder-user-1"},
            headers=_auth_headers(token_1),
        )
        assert resp_folder_1.status_code == 201

        resp_folder_2 = auth_client.post(
            "/folders/",
            json={"name": "folder-user-2"},
            headers=_auth_headers(token_2),
        )
        assert resp_folder_2.status_code == 201

        ch_1 = auth_client.get("/channels/", headers=_auth_headers(token_1)).json()
        ch_2 = auth_client.get("/channels/", headers=_auth_headers(token_2)).json()
        assert [c["id"] for c in ch_1["items"]] == ["UC_owner_1"]
        assert [c["id"] for c in ch_2["items"]] == ["UC_owner_2"]

        v_1 = auth_client.get("/videos/", headers=_auth_headers(token_1)).json()
        v_2 = auth_client.get("/videos/", headers=_auth_headers(token_2)).json()
        assert [v["id"] for v in v_1["items"]] == ["video_owner_1"]
        assert [v["id"] for v in v_2["items"]] == ["video_owner_2"]

        p_1 = auth_client.get("/playlists/", headers=_auth_headers(token_1)).json()
        p_2 = auth_client.get("/playlists/", headers=_auth_headers(token_2)).json()
        assert [p["id"] for p in p_1["items"]] == ["playlist_owner_1"]
        assert [p["id"] for p in p_2["items"]] == ["playlist_owner_2"]

        t_1 = auth_client.get("/tags/", headers=_auth_headers(token_1)).json()
        t_2 = auth_client.get("/tags/", headers=_auth_headers(token_2)).json()
        assert [t["name"] for t in t_1["items"]] == ["tag-user-1"]
        assert [t["name"] for t in t_2["items"]] == ["tag-user-2"]

        f_1 = auth_client.get("/folders/tree", headers=_auth_headers(token_1)).json()
        f_2 = auth_client.get("/folders/tree", headers=_auth_headers(token_2)).json()
        assert [f["name"] for f in f_1] == ["folder-user-1"]
        assert [f["name"] for f in f_2] == ["folder-user-2"]
