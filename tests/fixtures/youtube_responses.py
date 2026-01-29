"""
Mock YouTube API responses for testing.

These fixtures provide realistic sample data matching the YouTube Data API v3 format.
"""

from typing import Dict, Any, List


def mock_channel_info_response(
    channel_id: str = "UC_test_channel_id",
    title: str = "Test Channel",
    handle: str = "testchannel",
    description: str = "This is a test channel",
    uploads_playlist_id: str = "UU_test_playlist_id",
) -> Dict[str, Any]:
    """
    Returns a mock response for the channels.list API call.

    This matches the structure returned by YouTubeAPI.get_channel_info()
    """
    return {
        "kind": "youtube#channelListResponse",
        "etag": "test_etag",
        "pageInfo": {
            "totalResults": 1,
            "resultsPerPage": 1
        },
        "items": [
            {
                "kind": "youtube#channel",
                "etag": "test_channel_etag",
                "id": channel_id,
                "snippet": {
                    "title": title,
                    "description": description,
                    "customUrl": f"@{handle}",
                    "publishedAt": "2020-01-01T00:00:00Z",
                    "thumbnails": {
                        "default": {
                            "url": f"https://yt3.ggpht.com/default_{channel_id}",
                            "width": 88,
                            "height": 88
                        },
                        "medium": {
                            "url": f"https://yt3.ggpht.com/medium_{channel_id}",
                            "width": 240,
                            "height": 240
                        },
                        "high": {
                            "url": f"https://yt3.ggpht.com/high_{channel_id}",
                            "width": 800,
                            "height": 800
                        }
                    },
                    "localized": {
                        "title": title,
                        "description": description
                    }
                },
                "contentDetails": {
                    "relatedPlaylists": {
                        "likes": "",
                        "uploads": uploads_playlist_id
                    }
                },
                "statistics": {
                    "viewCount": "1000000",
                    "subscriberCount": "50000",
                    "hiddenSubscriberCount": False,
                    "videoCount": "100"
                }
            }
        ]
    }


def mock_channel_not_found_response() -> Dict[str, Any]:
    """Returns a mock response when a channel is not found."""
    return {
        "kind": "youtube#channelListResponse",
        "etag": "test_etag",
        "pageInfo": {
            "totalResults": 0,
            "resultsPerPage": 0
        },
        "items": []
    }


def mock_playlist_items_response(
    playlist_id: str = "UU_test_playlist_id",
    video_ids: List[str] = None,
    page_token: str = None,
    next_page_token: str = None,
) -> Dict[str, Any]:
    """
    Returns a mock response for the playlistItems.list API call.

    Used when fetching videos from a channel's uploads playlist.
    """
    if video_ids is None:
        video_ids = ["video_id_1", "video_id_2", "video_id_3"]

    items = []
    for i, video_id in enumerate(video_ids):
        items.append({
            "kind": "youtube#playlistItem",
            "etag": f"test_etag_{i}",
            "id": f"playlist_item_{i}",
            "snippet": {
                "publishedAt": f"2024-01-{str(i+1).zfill(2)}T12:00:00Z",
                "channelId": "UC_test_channel_id",
                "title": f"Test Video {i+1}",
                "description": f"Description for test video {i+1}",
                "thumbnails": {
                    "default": {
                        "url": f"https://i.ytimg.com/vi/{video_id}/default.jpg",
                        "width": 120,
                        "height": 90
                    },
                    "medium": {
                        "url": f"https://i.ytimg.com/vi/{video_id}/mqdefault.jpg",
                        "width": 320,
                        "height": 180
                    },
                    "high": {
                        "url": f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
                        "width": 480,
                        "height": 360
                    }
                },
                "channelTitle": "Test Channel",
                "playlistId": playlist_id,
                "position": i,
                "resourceId": {
                    "kind": "youtube#video",
                    "videoId": video_id
                }
            }
        })

    response = {
        "kind": "youtube#playlistItemListResponse",
        "etag": "test_playlist_etag",
        "pageInfo": {
            "totalResults": len(video_ids),
            "resultsPerPage": len(video_ids)
        },
        "items": items
    }

    if next_page_token:
        response["nextPageToken"] = next_page_token

    return response


def mock_videos_list_response(
    video_data: List[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Returns a mock response for the videos.list API call.

    Used when fetching detailed information about specific videos.

    Each video_data dict can have:
    - video_id: str
    - title: str
    - description: str
    - duration: str (ISO 8601 format, e.g., "PT5M30S")
    - published_at: str
    - channel_id: str
    - is_short: bool (affects duration and title)
    """
    if video_data is None:
        video_data = [
            {
                "video_id": "video_id_1",
                "title": "Normal Video",
                "description": "A normal length video",
                "duration": "PT10M30S",
                "published_at": "2024-01-01T12:00:00Z",
                "channel_id": "UC_test_channel_id",
            },
            {
                "video_id": "video_id_2",
                "title": "Short Video #shorts",
                "description": "A YouTube Short",
                "duration": "PT45S",
                "published_at": "2024-01-02T12:00:00Z",
                "channel_id": "UC_test_channel_id",
            }
        ]

    items = []
    for data in video_data:
        video_id = data.get("video_id", "test_video_id")
        title = data.get("title", "Test Video")
        description = data.get("description", "Test description")
        duration = data.get("duration", "PT5M0S")
        published_at = data.get("published_at", "2024-01-01T12:00:00Z")
        channel_id = data.get("channel_id", "UC_test_channel_id")
        tags = data.get("tags", [])

        items.append({
            "kind": "youtube#video",
            "etag": f"test_etag_{video_id}",
            "id": video_id,
            "snippet": {
                "publishedAt": published_at,
                "channelId": channel_id,
                "title": title,
                "description": description,
                "thumbnails": {
                    "default": {
                        "url": f"https://i.ytimg.com/vi/{video_id}/default.jpg",
                        "width": 120,
                        "height": 90
                    },
                    "medium": {
                        "url": f"https://i.ytimg.com/vi/{video_id}/mqdefault.jpg",
                        "width": 320,
                        "height": 180
                    },
                    "high": {
                        "url": f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
                        "width": 480,
                        "height": 360
                    }
                },
                "channelTitle": "Test Channel",
                "tags": tags,
                "categoryId": "22",
                "liveBroadcastContent": "none",
                "localized": {
                    "title": title,
                    "description": description
                }
            },
            "contentDetails": {
                "duration": duration,
                "dimension": "2d",
                "definition": "hd",
                "caption": "false",
                "licensedContent": True,
                "projection": "rectangular"
            },
            "statistics": {
                "viewCount": "10000",
                "likeCount": "500",
                "favoriteCount": "0",
                "commentCount": "50"
            }
        })

    return {
        "kind": "youtube#videoListResponse",
        "etag": "test_videos_etag",
        "pageInfo": {
            "totalResults": len(items),
            "resultsPerPage": len(items)
        },
        "items": items
    }


def mock_empty_playlist_response(playlist_id: str = "UU_test_playlist_id") -> Dict[str, Any]:
    """Returns a mock response for an empty playlist."""
    return {
        "kind": "youtube#playlistItemListResponse",
        "etag": "test_etag",
        "pageInfo": {
            "totalResults": 0,
            "resultsPerPage": 0
        },
        "items": []
    }


def mock_videos_short_response() -> Dict[str, Any]:
    """Returns a mock response for YouTube Shorts videos."""
    return mock_videos_list_response([
        {
            "video_id": "short_video_1",
            "title": "Cool Short #shorts",
            "description": "A YouTube Short with hashtag",
            "duration": "PT30S",
            "published_at": "2024-01-01T12:00:00Z",
            "channel_id": "UC_test_channel_id",
            "tags": ["shorts", "test"]
        },
        {
            "video_id": "short_video_2",
            "title": "Another Short",
            "description": "Check out this #short video!",
            "duration": "PT55S",
            "published_at": "2024-01-02T12:00:00Z",
            "channel_id": "UC_test_channel_id",
            "tags": ["short"]
        }
    ])


def mock_paginated_playlist_response(
    page_num: int = 1,
    videos_per_page: int = 50,
    total_videos: int = 150,
) -> Dict[str, Any]:
    """
    Returns a mock paginated response for playlist items.

    Useful for testing pagination logic when fetching many videos.
    """
    start_idx = (page_num - 1) * videos_per_page
    end_idx = min(start_idx + videos_per_page, total_videos)

    video_ids = [f"video_{i}" for i in range(start_idx, end_idx)]

    has_next = end_idx < total_videos
    next_token = f"page_{page_num + 1}_token" if has_next else None

    return mock_playlist_items_response(
        video_ids=video_ids,
        next_page_token=next_token
    )


# Convenience fixtures for common scenarios
SAMPLE_CHANNEL_RESPONSE = mock_channel_info_response()
SAMPLE_CHANNEL_NOT_FOUND = mock_channel_not_found_response()
SAMPLE_PLAYLIST_ITEMS = mock_playlist_items_response()
SAMPLE_VIDEOS_LIST = mock_videos_list_response()
SAMPLE_SHORTS_VIDEOS = mock_videos_short_response()
SAMPLE_EMPTY_PLAYLIST = mock_empty_playlist_response()
