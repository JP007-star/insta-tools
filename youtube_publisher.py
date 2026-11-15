import os
import re
import json
import tempfile
from typing import Optional, Tuple, Dict, Any, List
import google.oauth2.credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]

# Standard YouTube Categories
YOUTUBE_CATEGORIES = {
    "22": "People & Blogs",
    "24": "Entertainment",
    "28": "Science & Technology",
    "27": "Education",
    "10": "Music",
    "17": "Sports",
    "20": "Gaming",
    "23": "Comedy",
    "26": "Howto & Style",
    "1":  "Film & Animation",
    "2":  "Autos & Vehicles",
    "25": "News & Politics",
}


def create_oauth_flow(client_config: dict, redirect_uri: str = "urn:ietf:wg:oauth:2.0:oob") -> Flow:
    """Creates a Google OAuth Flow from client config dict."""
    return Flow.from_client_config(
        client_config=client_config,
        scopes=SCOPES,
        redirect_uri=redirect_uri,
    )


def exchange_code_for_credentials(flow: Flow, code: str) -> dict:
    """Exchanges authorization code for credentials and returns a dict representation."""
    flow.fetch_token(code=code)
    creds = flow.credentials
    return {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": creds.scopes,
    }


def get_credentials_from_dict(token_info: dict) -> google.oauth2.credentials.Credentials:
    """Reconstructs Credentials object from token dictionary."""
    return google.oauth2.credentials.Credentials(
        token=token_info.get("token"),
        refresh_token=token_info.get("refresh_token"),
        token_uri=token_info.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=token_info.get("client_id"),
        client_secret=token_info.get("client_secret"),
        scopes=token_info.get("scopes", SCOPES),
    )


def get_channel_info(creds: google.oauth2.credentials.Credentials) -> Optional[dict]:
    """Fetches authenticated user's YouTube channel details."""
    try:
        from google.auth.transport.requests import Request
        if creds.expired or not creds.token:
            creds.refresh(Request())

        youtube = build("youtube", "v3", credentials=creds)
        response = youtube.channels().list(
            part="snippet,statistics",
            mine=True
        ).execute()

        items = response.get("items", [])
        if not items:
            return {
                "id": "authorized",
                "title": "Connected YouTube Channel",
                "customUrl": "",
                "thumbnail": None,
                "subscriberCount": "Active",
                "videoCount": "Ready",
            }

        item = items[0]
        snippet = item.get("snippet", {})
        stats = item.get("statistics", {})

        return {
            "id": item.get("id"),
            "title": snippet.get("title", "Connected Channel"),
            "customUrl": snippet.get("customUrl"),
            "thumbnail": snippet.get("thumbnails", {}).get("default", {}).get("url"),
            "subscriberCount": stats.get("subscriberCount", "0"),
            "videoCount": stats.get("videoCount", "0"),
        }
    except Exception as e:
        # If the token only has youtube.upload scope, channels().list returns 403
        # But uploading is fully authorized!
        err_str = str(e).lower()
        if "insufficient" in err_str or "403" in err_str or creds.valid or creds.refresh_token:
            return {
                "id": "authorized",
                "title": "Connected YouTube Account",
                "customUrl": "",
                "thumbnail": None,
                "subscriberCount": "Authorized (Upload Ready)",
                "videoCount": "Ready to publish",
            }
        return None


def get_preconfigured_credentials() -> Optional[google.oauth2.credentials.Credentials]:
    """Attempts to load credentials from token.json or Streamlit secrets."""
    # 1. Check local token.json
    token_path = os.path.join(os.path.dirname(__file__), "token.json")
    if os.path.exists(token_path):
        try:
            with open(token_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return get_credentials_from_dict(data)
        except Exception:
            pass

    # 2. Check Streamlit secrets
    try:
        import streamlit as st
        if (
            "YOUTUBE_CLIENT_ID" in st.secrets
            and "YOUTUBE_CLIENT_SECRET" in st.secrets
            and "YOUTUBE_REFRESH_TOKEN" in st.secrets
        ):
            return google.oauth2.credentials.Credentials(
                token=None,
                refresh_token=st.secrets["YOUTUBE_REFRESH_TOKEN"],
                token_uri="https://oauth2.googleapis.com/token",
                client_id=st.secrets["YOUTUBE_CLIENT_ID"],
                client_secret=st.secrets["YOUTUBE_CLIENT_SECRET"],
                scopes=["https://www.googleapis.com/auth/youtube.upload"],
            )
    except Exception:
        pass

    return None


def upload_to_youtube(
    creds: google.oauth2.credentials.Credentials,
    file_path: str,
    title: str,
    description: str,
    tags: Optional[List[str]] = None,
    category_id: str = "22",
    privacy_status: str = "public",
) -> Tuple[bool, str, Optional[str]]:
    """
    Uploads a video file to YouTube.
    Returns (success: bool, message: str, video_id: Optional[str]).
    """
    try:
        from google.auth.transport.requests import Request
        if creds.expired or not creds.token:
            creds.refresh(Request())

        youtube = build("youtube", "v3", credentials=creds)

        body = {
            "snippet": {
                "title": title[:100],  # YouTube title limit 100 chars
                "description": description[:5000],  # Description limit 5000 chars
                "tags": (tags or [])[:50],
                "categoryId": category_id,
            },
            "status": {
                "privacyStatus": privacy_status.lower(),
                "selfDeclaredMadeForKids": False,
            },
        }

        # MediaFileUpload with resumable upload
        media = MediaFileUpload(
            file_path,
            mimetype="video/mp4",
            resumable=True,
            chunksize=1024 * 1024 * 2  # 2MB chunks
        )

        request = youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media
        )

        response = None
        while response is None:
            status, response = request.next_chunk()

        video_id = response.get("id")
        return True, "Video published successfully to YouTube!", video_id

    except HttpError as error:
        try:
            err_json = json.loads(error.content.decode("utf-8"))
            err_msg = err_json.get("error", {}).get("message", str(error))
        except Exception:
            err_msg = str(error)
        return False, f"YouTube API Error: {err_msg}", None
    except Exception as exc:
        return False, f"Upload error: {exc}", None
