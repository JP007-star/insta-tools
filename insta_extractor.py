import os
import re
import tempfile
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, List
import yt_dlp


def is_valid_instagram_url(url: str) -> bool:
    """Validates Instagram Reel, Post, or Video URL."""
    pattern = r"(https?://)?(www\.)?instagram\.com/(reel|reels|p|tv)/[\w-]+/?"
    return bool(re.match(pattern, url.strip()))


def extract_instagram_urls(text: str) -> List[str]:
    """Finds all Instagram reel/post URLs in a text blob or newline-separated list."""
    pattern = r"https?://(?:www\.)?instagram\.com/(?:reel|reels|p|tv)/[\w-]+/?"
    matches = re.findall(pattern, text)
    return list(dict.fromkeys([m.rstrip("/") + "/" for m in matches]))


def parse_hashtags(text: str) -> List[str]:
    """Extracts unique hashtag keywords from text."""
    if not text:
        return []
    tags = re.findall(r"#([\w]+)", text)
    return list(dict.fromkeys(tags))


def clean_title_from_caption(caption: str, fallback_id: str = "Reel", max_length: int = 70) -> str:
    """
    Creates a clean, attractive YouTube title from an Instagram caption:
    - Takes the first clean line/sentence
    - Strips excessive hashtags from the title
    - Truncates safely
    """
    if not caption:
        return f"Instagram Reel {fallback_id} #Shorts"

    lines = [line.strip() for line in caption.split("\n") if line.strip()]
    first_line = lines[0] if lines else caption.strip()

    # Strip hashtags from title
    title_clean = re.sub(r"#\w+", "", first_line).strip()
    title_clean = re.sub(r"\s+", " ", title_clean)

    if not title_clean:
        # If the line was only hashtags, use fallback
        title_clean = f"Instagram Reel {fallback_id}"

    if len(title_clean) > max_length:
        title_clean = title_clean[:max_length].rstrip(" ,-–.") + "…"

    return f"{title_clean} #Shorts"


def fetch_instagram_reel(url: str, output_dir: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Fetches Instagram video, caption, hashtags, and metadata.
    Returns:
        (success: bool, message: str, data: dict or None)
        where data contains:
        {
            "video_path": str,
            "title": str,
            "description": str,
            "caption": str,
            "hashtags": list[str],
            "thumbnail": str,
            "uploader": str,
            "url": str,
        }
    """
    ydl_opts = {
        "outtmpl": os.path.join(output_dir, "%(id)s.%(ext)s"),
        "format": "best[ext=mp4]/best",
        "quiet": True,
        "no_warnings": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            video_id = info.get("id", "video")
            caption = info.get("description") or info.get("title") or ""
            uploader = info.get("uploader") or info.get("channel") or "Instagram Creator"
            thumbnail = info.get("thumbnail")

            # Check downloaded file
            filename = ydl.prepare_filename(info)
            if not filename.endswith(".mp4"):
                filename = os.path.splitext(filename)[0] + ".mp4"

            if not os.path.exists(filename):
                candidates = list(Path(output_dir).glob(f"{video_id}.*")) or list(Path(output_dir).glob("*.mp4"))
                if candidates:
                    filename = str(candidates[0])
                else:
                    return False, "Downloaded video file not found.", None

            # Process metadata
            hashtags = parse_hashtags(caption)
            youtube_title = clean_title_from_caption(caption, fallback_id=video_id)

            # Build rich description for YouTube
            youtube_description = (
                f"{caption.strip()}\n\n"
                f"───\n"
                f"Original by: @{uploader}\n"
                f"Source: {url}\n"
                f"#Shorts #Instagram"
            )

            result = {
                "video_path": filename,
                "title": youtube_title,
                "caption": caption,
                "description": youtube_description,
                "hashtags": hashtags,
                "thumbnail": thumbnail,
                "uploader": uploader,
                "url": url,
                "video_id": video_id,
            }

            return True, "Successfully fetched Instagram Reel & metadata!", result

    except yt_dlp.utils.DownloadError as exc:
        return False, f"Failed to fetch reel: {exc}", None
    except Exception as exc:
        return False, f"Error processing Instagram reel: {exc}", None
