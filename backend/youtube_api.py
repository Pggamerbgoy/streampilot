import os
import pickle
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, Optional

from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# If modifying upload scopes, delete the file token.pickle.
READONLY_SCOPES = [
    'https://www.googleapis.com/auth/yt-analytics.readonly',
    'https://www.googleapis.com/auth/youtube.readonly',
]
SCOPES = [
    *READONLY_SCOPES,
    'https://www.googleapis.com/auth/youtube.upload'
]

class YouTubeConnection:
    def __init__(self, client_secrets_file=None, api_key: Optional[str] = None):
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.client_secrets_file = client_secrets_file or os.path.join(self.script_dir, 'client_secret.json')
        self.token_file = os.path.join(self.script_dir, 'token.pickle')
        self.api_key = api_key if api_key is not None else (os.getenv("YOUTUBE_API_KEY") or os.getenv("GOOGLE_API_KEY"))
        self.credentials = None
        self.youtube = None
        self.public_youtube = None
        self.youtube_analytics = None

    def authenticate(self, required_scopes=None):
        """Handles the OAuth 2.0 flow to authenticate the user."""
        required_scopes = required_scopes or SCOPES
        print("🔐 Authenticating with YouTube...")
        creds = None

        # The file token.pickle stores the user's access and refresh tokens
        if os.path.exists(self.token_file):
            with open(self.token_file, 'rb') as token:
                creds = pickle.load(token)

        # If there are no (valid) credentials available, let the user log in.
        if creds and hasattr(creds, "has_scopes") and not creds.has_scopes(required_scopes):
            print("⚠️ Existing token is missing required YouTube permissions. Re-authentication required.")
            creds = None

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(self.client_secrets_file):
                    raise FileNotFoundError(
                        f"Missing {self.client_secrets_file}! You need to download "
                        "your OAuth 2.0 Client ID JSON from Google Cloud Console."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.client_secrets_file, required_scopes)
                creds = flow.run_local_server(port=0)
            # Save the credentials for the next run
            with open(self.token_file, 'wb') as token:
                pickle.dump(creds, token)

        self.credentials = creds

        # Build the API clients
        self.youtube = build('youtube', 'v3', credentials=creds)
        self.youtube_analytics = build('youtubeAnalytics', 'v2', credentials=creds)
        print("✅ Successfully connected to YouTube!")

    def _public_youtube_client(self):
        """Builds a public YouTube Data API client when an API key is configured."""
        if not self.api_key:
            return None
        if not self.public_youtube:
            self.public_youtube = build('youtube', 'v3', developerKey=self.api_key)
        return self.public_youtube

    def _public_or_authenticated_youtube(self):
        """Returns an API-key client for public data, falling back to OAuth."""
        public_client = self._public_youtube_client()
        if public_client:
            return public_client
        if not self.youtube:
            self.authenticate(READONLY_SCOPES)
        return self.youtube

    def get_channel_stats(self):
        """Fetches real channel statistics."""
        if not self.youtube:
            self.authenticate(READONLY_SCOPES)

        request = self.youtube.channels().list(
            part="statistics,snippet",
            mine=True
        )
        response = request.execute()

        if response['items']:
            channel = response['items'][0]
            print(f"📺 Channel: {channel['snippet']['title']}")
            print(f"👥 Subscribers: {channel['statistics']['subscriberCount']}")
            print(f"👁️ Total Views: {channel['statistics']['viewCount']}")
            print(f"🎥 Total Videos: {channel['statistics']['videoCount']}")
            return channel
        return None

    def get_analytics_data(self):
        """Fetches the last 30 days of daily views using the YouTube Analytics API."""
        if not self.youtube_analytics:
            self.authenticate(READONLY_SCOPES)

        from datetime import datetime, timedelta

        # Calculate dates for the last 30 days
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')

        print(f"📊 Fetching analytics from {start_date} to {end_date}...")

        try:
            request = self.youtube_analytics.reports().query(
                ids="channel==MINE",
                startDate=start_date,
                endDate=end_date,
                metrics="views,estimatedMinutesWatched,averageViewDuration",
                dimensions="day",
                sort="day"
            )
            response = request.execute()
            return response.get('rows', [])
        except Exception as e:
            print(f"❌ Analytics Error: {e}")
            return []

    def get_channel_analytics_window(self, days: int = 28, strict: bool = False) -> Dict[str, Any]:
        """Fetches channel analytics for recent training baselines."""
        if not self.youtube_analytics:
            self.authenticate(READONLY_SCOPES)

        end_date = datetime.now(timezone.utc).date()
        start_date = end_date - timedelta(days=max(1, int(days)))
        metrics = "views,estimatedMinutesWatched,averageViewDuration,comments,likes,shares"
        try:
            request = self.youtube_analytics.reports().query(
                ids="channel==MINE",
                startDate=start_date.isoformat(),
                endDate=end_date.isoformat(),
                metrics=metrics,
                dimensions="day",
                sort="day",
            )
            response = request.execute()
            rows = self._analytics_rows(response)
            totals = self._analytics_totals(rows)
            return {
                "rows": rows,
                "timeline": rows,
                "totals": totals,
                "analytics_available": bool(rows),
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            }
        except Exception as e:
            if strict:
                raise
            print(f"❌ Channel Analytics Error: {e}")
            return {"rows": [], "timeline": [], "totals": {}, "analytics_available": False, "error": str(e)}

    def get_video_analytics_window(self, video_id: str, days: int = 7, strict: bool = False) -> Dict[str, Any]:
        """Fetches video analytics for a recent window."""
        if not self.youtube_analytics:
            self.authenticate(READONLY_SCOPES)

        end_date = datetime.now(timezone.utc).date()
        start_date = end_date - timedelta(days=max(1, int(days)))
        metrics = "views,estimatedMinutesWatched,averageViewDuration,comments,likes,shares"
        try:
            request = self.youtube_analytics.reports().query(
                ids="channel==MINE",
                startDate=start_date.isoformat(),
                endDate=end_date.isoformat(),
                metrics=metrics,
                dimensions="day",
                filters=f"video=={video_id}",
                sort="day",
            )
            response = request.execute()
            rows = self._analytics_rows(response)
            totals = self._analytics_totals(rows)
            return {
                "rows": rows,
                "timeline": rows,
                "totals": totals,
                "analytics_available": bool(rows),
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            }
        except Exception as e:
            if strict:
                raise
            print(f"❌ Video Analytics Error: {e}")
            return {"rows": [], "timeline": [], "totals": {}, "analytics_available": False, "error": str(e)}

    def get_video_analytics_24h(self, video_id: str, strict: bool = False) -> Dict[str, Any]:
        """Fetches early video analytics where YouTube has made them available."""
        return self.get_video_analytics_window(video_id, days=1, strict=strict)

    def get_video_stats(self, video_id: str) -> Dict[str, Any]:
        """Fetches public snippet/statistics for one video."""
        videos = self.get_video_stats_batch([video_id])
        return videos[0] if videos else {}

    def get_video_stats_batch(self, video_ids: list[str]) -> list[Dict[str, Any]]:
        """Fetches public snippet/statistics for a batch of videos."""
        youtube = self._public_or_authenticated_youtube()
        clean_ids = [video_id for video_id in video_ids if video_id]
        if not clean_ids:
            return []
        request = youtube.videos().list(
            part="snippet,statistics,contentDetails,status",
            id=",".join(clean_ids[:50]),
        )
        response = request.execute()
        return [self._video_item_to_payload(item) for item in response.get("items", [])]

    def get_recent_channel_videos(self, max_results: int = 25) -> list[Dict[str, Any]]:
        """Fetches recent uploads for the authenticated channel."""
        if not self.youtube:
            self.authenticate(READONLY_SCOPES)
        channel_response = self.youtube.channels().list(part="contentDetails", mine=True).execute()
        items = channel_response.get("items", [])
        if not items:
            return []
        uploads_playlist = (
            items[0]
            .get("contentDetails", {})
            .get("relatedPlaylists", {})
            .get("uploads")
        )
        if not uploads_playlist:
            return []
        playlist_response = self.youtube.playlistItems().list(
            part="contentDetails",
            playlistId=uploads_playlist,
            maxResults=max(1, min(int(max_results), 50)),
        ).execute()
        ids = [
            item.get("contentDetails", {}).get("videoId")
            for item in playlist_response.get("items", [])
            if item.get("contentDetails", {}).get("videoId")
        ]
        videos = self.get_video_stats_batch(ids)
        now = datetime.now(timezone.utc)
        for video in videos:
            try:
                published = datetime.fromisoformat(video.get("published_at", "").replace("Z", "+00:00"))
                if published.tzinfo is None:
                    published = published.replace(tzinfo=timezone.utc)
                age_hours = max((now - published).total_seconds() / 3600.0, 0.5)
            except Exception:
                age_hours = 24.0
            video["age_hours"] = round(age_hours, 2)
            video["views_per_hour"] = round(int(video.get("view_count") or 0) / age_hours, 2)
        return videos

    def get_recent_comments(self, video_id: str, max_results: int = 20, strict: bool = False) -> list[Dict[str, Any]]:
        """Fetches recent top-level comments for reply drafting."""
        if not self.youtube:
            self.authenticate(READONLY_SCOPES)
        try:
            request = self.youtube.commentThreads().list(
                part="snippet",
                videoId=video_id,
                order="time",
                textFormat="plainText",
                maxResults=max(1, min(int(max_results), 100)),
            )
            response = request.execute()
            comments = []
            for item in response.get("items", []):
                snippet = item.get("snippet", {}).get("topLevelComment", {}).get("snippet", {})
                comments.append(
                    {
                        "id": item.get("id"),
                        "author": snippet.get("authorDisplayName", "Viewer"),
                        "text": snippet.get("textDisplay", ""),
                        "published_at": snippet.get("publishedAt"),
                        "like_count": snippet.get("likeCount", 0),
                    }
            )
            return comments
        except Exception as e:
            if strict:
                raise
            print(f"❌ Comments Error: {e}")
            return []

    def get_trending_videos(
        self,
        region_code: str = "US",
        category_id: Optional[str] = None,
        max_results: int = 12,
    ) -> list[Dict[str, Any]]:
        """Fetches currently popular videos for a region/category."""
        youtube = self._public_or_authenticated_youtube()
        request_params = {
            "part": "snippet,statistics,contentDetails",
            "chart": "mostPopular",
            "regionCode": (region_code or "US").upper(),
            "maxResults": max(1, min(int(max_results), 50)),
        }
        if category_id:
            request_params["videoCategoryId"] = str(category_id)
        response = youtube.videos().list(**request_params).execute()
        return [
            {**self._video_item_to_payload(item), "region_code": request_params["regionCode"]}
            for item in response.get("items", [])
        ]

    def _video_item_to_payload(self, item: Dict[str, Any]) -> Dict[str, Any]:
        snippet = item.get("snippet", {})
        stats = item.get("statistics", {})
        thumbnails = snippet.get("thumbnails", {})
        thumb = thumbnails.get("high") or thumbnails.get("medium") or thumbnails.get("default") or {}
        video_id = item.get("id")
        return {
            "id": video_id,
            "title": snippet.get("title", ""),
            "channel_title": snippet.get("channelTitle", ""),
            "description": snippet.get("description", ""),
            "view_count": int(stats.get("viewCount", 0)),
            "like_count": int(stats.get("likeCount", 0)),
            "comment_count": int(stats.get("commentCount", 0)),
            "published_at": snippet.get("publishedAt"),
            "category_id": snippet.get("categoryId"),
            "privacy_status": item.get("status", {}).get("privacyStatus"),
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "thumbnail_url": thumb.get("url", ""),
        }

    def _analytics_rows(self, response: Dict[str, Any]) -> list[Dict[str, Any]]:
        headers = [header["name"] for header in response.get("columnHeaders", [])]
        rows = []
        for raw_row in response.get("rows", []):
            row = dict(zip(headers, raw_row))
            rows.append(
                {
                    "day": row.get("day"),
                    "views": row.get("views", 0),
                    "watch_time_minutes": row.get("estimatedMinutesWatched", 0),
                    "average_view_duration_seconds": row.get("averageViewDuration", 0),
                    "comments": row.get("comments", 0),
                    "likes": row.get("likes", 0),
                    "shares": row.get("shares", 0),
                }
            )
        return rows

    def _analytics_totals(self, rows: list[Dict[str, Any]]) -> Dict[str, Any]:
        if not rows:
            return {}
        views = sum(int(row.get("views") or 0) for row in rows)
        watch_time = sum(float(row.get("watch_time_minutes") or 0) for row in rows)
        comments = sum(int(row.get("comments") or 0) for row in rows)
        likes = sum(int(row.get("likes") or 0) for row in rows)
        shares = sum(int(row.get("shares") or 0) for row in rows)
        avd = (watch_time * 60.0 / max(views, 1)) if views else 0
        return {
            "elapsed_hours": None,
            "views": views,
            "impressions": None,
            "ctr": None,
            "average_view_duration_seconds": round(avd, 2),
            "watch_time_minutes": round(watch_time, 2),
            "comments": comments,
            "likes": likes,
            "shares": shares,
        }

    def upload_video(
        self,
        file_path,
        title,
        description="",
        tags=None,
        category_id="28",
        privacy_status="public",
        publish_at=None,
        made_for_kids=False,
        contains_synthetic_media=False,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        chunk_size: int = 8 * 1024 * 1024,
    ):
        """Uploads a video with AI-generated metadata."""
        if not self.youtube:
            self.authenticate(SCOPES)

        clean_tags = [tag for tag in (tags or []) if tag]
        status = {
            "privacyStatus": privacy_status,
            "selfDeclaredMadeForKids": bool(made_for_kids),
            "containsSyntheticMedia": bool(contains_synthetic_media),
        }
        if publish_at:
            status["publishAt"] = publish_at
            status["privacyStatus"] = "private"

        body = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": clean_tags,
                "categoryId": str(category_id or "28"),
            },
            "status": status,
        }

        total_bytes = os.path.getsize(file_path)
        media = MediaFileUpload(file_path, mimetype="video/*", chunksize=chunk_size, resumable=True)
        request = self.youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media,
        )

        response = None
        while response is None:
            if self.credentials and self.credentials.expired and self.credentials.refresh_token:
                self.credentials.refresh(Request())
            status, response = request.next_chunk()
            if status and progress_callback:
                progress_callback(
                    {
                        "progress": round(float(status.progress()) * 100.0, 1),
                        "bytes_uploaded": getattr(status, "resumable_progress", None),
                        "total_bytes": total_bytes,
                    }
                )
        if progress_callback:
            progress_callback({"progress": 100.0, "bytes_uploaded": total_bytes, "total_bytes": total_bytes})
        return response

    def set_thumbnail(self, video_id, image_path):
        """Sets a custom thumbnail for an uploaded video."""
        if not self.youtube:
            self.authenticate(SCOPES)
        media = MediaFileUpload(image_path, resumable=True)
        return self.youtube.thumbnails().set(videoId=video_id, media_body=media).execute()

if __name__ == "__main__":
    # To test this, you must have a client_secret.json file in the same directory.
    yt = YouTubeConnection()
    try:
        yt.get_channel_stats()
        rows = yt.get_analytics_data()
        if rows:
            print(f"✅ Found {len(rows)} days of analytics data.")
            print(f"Most recent day: {rows[-1]}")
    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
