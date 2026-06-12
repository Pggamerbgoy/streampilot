import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import youtube_api as youtube_api_module  # noqa: E402
from youtube_api import YouTubeConnection  # noqa: E402


class _FakeRequest:
    def __init__(self, response):
        self._response = response

    def execute(self):
        return self._response


class _FakeVideosResource:
    def __init__(self, record, response):
        self._record = record
        self._response = response

    def list(self, **params):
        self._record["list_params"] = params
        return _FakeRequest(self._response)


class _FakeYouTubeClient:
    def __init__(self, record, response):
        self._record = record
        self._response = response

    def videos(self):
        return _FakeVideosResource(self._record, self._response)


def test_get_trending_videos_uses_api_key_without_oauth(monkeypatch):
    record = {}
    response = {
        "items": [
            {
                "id": "realTrend123",
                "snippet": {
                    "title": "Actual Trending Video",
                    "channelTitle": "Live Creator",
                    "description": "Public trend row",
                    "publishedAt": "2026-06-11T10:00:00Z",
                    "categoryId": "28",
                    "thumbnails": {"high": {"url": "https://i.ytimg.com/vi/realTrend123/hqdefault.jpg"}},
                },
                "statistics": {"viewCount": "123456", "likeCount": "7890", "commentCount": "321"},
                "contentDetails": {},
            }
        ]
    }

    def fake_build(service_name, version, **kwargs):
        record["build"] = {"service_name": service_name, "version": version, "kwargs": kwargs}
        return _FakeYouTubeClient(record, response)

    monkeypatch.setattr(youtube_api_module, "build", fake_build)

    connection = YouTubeConnection(api_key="test-youtube-key")
    monkeypatch.setattr(
        connection,
        "authenticate",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("OAuth should not run for API-key public data")),
    )

    videos = connection.get_trending_videos(region_code="in", category_id="28", max_results=99)

    assert record["build"] == {
        "service_name": "youtube",
        "version": "v3",
        "kwargs": {"developerKey": "test-youtube-key"},
    }
    assert record["list_params"]["chart"] == "mostPopular"
    assert record["list_params"]["regionCode"] == "IN"
    assert record["list_params"]["videoCategoryId"] == "28"
    assert record["list_params"]["maxResults"] == 50
    assert videos == [
        {
            "id": "realTrend123",
            "title": "Actual Trending Video",
            "channel_title": "Live Creator",
            "description": "Public trend row",
            "view_count": 123456,
            "like_count": 7890,
            "comment_count": 321,
            "published_at": "2026-06-11T10:00:00Z",
            "category_id": "28",
            "privacy_status": None,
            "url": "https://www.youtube.com/watch?v=realTrend123",
            "thumbnail_url": "https://i.ytimg.com/vi/realTrend123/hqdefault.jpg",
            "region_code": "IN",
        }
    ]
