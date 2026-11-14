import streamlit as st
import yt_dlp
import os
import tempfile
import re
from pathlib import Path


# ── Helpers ────────────────────────────────────────────────────────────────────

def is_valid_youtube_url(url: str) -> bool:
    pattern = (
        r"(https?://)?(www\.)?"
        r"(youtube\.com/(watch\?v=|shorts/|embed/)|youtu\.be/)[\w\-]+"
    )
    return bool(re.match(pattern, url.strip()))


def fetch_video_info(url: str) -> dict | None:
    ydl_opts = {"quiet": True, "no_warnings": True, "skip_download": True}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(url, download=False)
    except Exception:
        return None


def download_video(url: str, output_dir: str, fmt: str) -> tuple[bool, str, str | None]:
    format_map = {
        "Best quality (MP4)":    "best[ext=mp4]/best",
        "1080p":                 "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best[height<=1080]",
        "720p":                  "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best[height<=720]",
        "480p":                  "best[height<=480][ext=mp4]/best[height<=480]",
        "Audio only (MP3)":      "bestaudio/best",
    }
    is_audio = fmt == "Audio only (MP3)"
    ydl_opts = {
        "outtmpl": os.path.join(output_dir, "%(title)s.%(ext)s"),
        "format": format_map.get(fmt, "best[ext=mp4]/best"),
        "quiet": True,
        "no_warnings": True,
    }
    if is_audio:
        ydl_opts["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }]

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            ext = "mp3" if is_audio else "mp4"
            base = os.path.splitext(filename)[0]
            final = f"{base}.{ext}"
            if os.path.exists(final):
                return True, "Download complete!", final
            candidates = sorted(Path(output_dir).glob(f"*.{ext}"), key=os.path.getmtime, reverse=True)
            if candidates:
                return True, "Download complete!", str(candidates[0])
            # fallback: any file
            all_files = sorted(Path(output_dir).iterdir(), key=os.path.getmtime, reverse=True)
            if all_files:
                return True, "Download complete!", str(all_files[0])
            return False, "File not found after download.", None
    except yt_dlp.utils.DownloadError as exc:
        msg = str(exc)
        if "ffmpeg" in msg.lower():
            return False, "This quality requires ffmpeg (not available on cloud). Try **Best quality (MP4)** or **480p** instead.", None
        return False, f"Download failed: {exc}", None
    except Exception as exc:
        return False, f"Unexpected error: {exc}", None


# ── Session state ──────────────────────────────────────────────────────────────
for key, val in {
    "yt_result_path": None,
    "yt_result_ext": "mp4",
    "yt_downloading": False,
    "yt_info": None,
}.items():
    if key not in st.session_state:
        st.session_state[key] = val

# ── UI ─────────────────────────────────────────────────────────────────────────
st.title(":material/play_circle: YouTube Downloader")
st.caption("Download YouTube videos or extract audio — no ffmpeg required for most formats.")
st.divider()

url_input = st.text_input(
    "YouTube URL",
    placeholder="https://www.youtube.com/watch?v=XXXXXXX",
)

# Format selector
format_choice = st.segmented_control(
    "Format",
    options=["Best quality (MP4)", "720p", "480p", "Audio only (MP3)"],
    default="Best quality (MP4)",
)

# Preview info on URL entry
if url_input.strip() and is_valid_youtube_url(url_input):
    if st.session_state.yt_info is None or st.session_state.get("yt_last_url") != url_input.strip():
        with st.spinner("Fetching video info…"):
            info = fetch_video_info(url_input.strip())
        st.session_state.yt_info = info
        st.session_state["yt_last_url"] = url_input.strip()

    info = st.session_state.yt_info
    if info:
        with st.container(border=True):
            col1, col2 = st.columns([1, 2])
            with col1:
                if info.get("thumbnail"):
                    st.image(info["thumbnail"])
            with col2:
                st.markdown(f"**{info.get('title', 'Unknown title')}**")
                channel = info.get("uploader") or info.get("channel", "")
                duration = info.get("duration", 0)
                mins, secs = divmod(int(duration), 60)
                views = info.get("view_count")
                if channel:
                    st.caption(f":material/person: {channel}")
                st.caption(f":material/schedule: {mins}:{secs:02d}   " +
                           (f":material/visibility: {views:,} views" if views else ""))

st.divider()

download_clicked = st.button(
    "Download",
    icon=":material/cloud_download:",
    type="primary",
    disabled=st.session_state.yt_downloading,
)

if download_clicked:
    url = url_input.strip()
    if not url:
        st.warning("Please paste a YouTube URL first.")
    elif not is_valid_youtube_url(url):
        st.error("That doesn't look like a valid YouTube URL.")
    else:
        st.session_state.yt_downloading = True
        st.session_state.yt_result_path = None

        with st.spinner(f"Downloading — {format_choice}…"):
            tmp_dir = tempfile.mkdtemp(prefix="yt_dl_")
            success, message, filepath = download_video(url, tmp_dir, format_choice)

        st.session_state.yt_downloading = False

        if success and filepath:
            st.session_state.yt_result_path = filepath
            st.session_state.yt_result_ext = "mp3" if "MP3" in format_choice else "mp4"
            st.success(message)
        else:
            st.error(message)

# ── Result ─────────────────────────────────────────────────────────────────────
if st.session_state.yt_result_path and os.path.exists(st.session_state.yt_result_path):
    filepath = st.session_state.yt_result_path
    ext = st.session_state.yt_result_ext
    st.divider()
    st.subheader(":material/check_circle: Ready!")

    if ext == "mp4":
        st.video(filepath)
        mime = "video/mp4"
    else:
        st.audio(filepath)
        mime = "audio/mpeg"

    with open(filepath, "rb") as f:
        file_bytes = f.read()

    st.download_button(
        label=f"Save {ext.upper()} to your device",
        data=file_bytes,
        file_name=os.path.basename(filepath),
        mime=mime,
        icon=":material/save:",
        type="primary",
    )

st.divider()
st.caption(":material/info: For personal use only. Respect copyright and YouTube's Terms of Service.")
