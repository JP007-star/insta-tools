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


def base_ydl_opts(cookie_path: str | None = None) -> dict:
    """Common yt-dlp options with EJS remote components for signature solving."""
    opts = {
        "quiet": True,
        "no_warnings": True,
        # Download EJS challenge solver from GitHub (fixes signature errors)
        "allow_unplayable_formats": False,
        "extractor_args": {
            "youtube": {
                "player_client": ["ios", "android", "tv_embedded", "web"],
            }
        },
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Linux; Android 12; Pixel 6) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/112.0.0.0 Mobile Safari/537.36"
            ),
        },
        # Enable remote EJS components so yt-dlp can solve YouTube's
        # signature/n-challenge without a local JS runtime
        "remote_components": "ejs:github",
    }
    if cookie_path:
        opts["cookiefile"] = cookie_path
    return opts


def fetch_video_info(url: str, cookie_path: str | None = None) -> dict | None:
    ydl_opts = {**base_ydl_opts(cookie_path), "skip_download": True}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(url, download=False)
    except Exception:
        return None


FORMAT_OPTIONS = {
    "🎬  MP4 — Best quality": {
        "format": "best[ext=mp4]/best",
        "ext": "mp4", "mime": "video/mp4",
    },
    "🎬  MP4 — 1080p": {
        "format": "best[height<=1080][ext=mp4]/best[height<=1080]/best[ext=mp4]/best",
        "ext": "mp4", "mime": "video/mp4",
    },
    "🎬  MP4 — 720p": {
        "format": "best[height<=720][ext=mp4]/best[height<=720]/best[ext=mp4]/best",
        "ext": "mp4", "mime": "video/mp4",
    },
    "🎬  MP4 — 480p": {
        "format": "best[height<=480][ext=mp4]/best[height<=480]/best[ext=mp4]/best",
        "ext": "mp4", "mime": "video/mp4",
    },
    "🎵  MP3 — High quality (320 kbps)": {
        "format": "bestaudio[ext=m4a]/bestaudio/best",
        "ext": "mp3", "mime": "audio/mpeg",
        "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "320"}],
    },
    "🎵  MP3 — Standard (192 kbps)": {
        "format": "bestaudio[ext=m4a]/bestaudio/best",
        "ext": "mp3", "mime": "audio/mpeg",
        "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}],
    },
    "🎵  MP3 — Small (128 kbps)": {
        "format": "bestaudio[ext=m4a]/bestaudio/best",
        "ext": "mp3", "mime": "audio/mpeg",
        "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "128"}],
    },
}


def download_video(
    url: str, output_dir: str, fmt_key: str, cookie_path: str | None = None
) -> tuple[bool, str, str | None]:
    cfg = FORMAT_OPTIONS[fmt_key]
    ext = cfg["ext"]

    ydl_opts = {
        **base_ydl_opts(cookie_path),
        "outtmpl": os.path.join(output_dir, "%(title)s.%(ext)s"),
        "format": cfg["format"],
        # Always merge to mp4 when streams are separate (no-op for single-file formats)
        "merge_output_format": "mp4",
    }
    if "postprocessors" in cfg:
        ydl_opts["postprocessors"] = cfg["postprocessors"]
    else:
        # Fix MPEG-TS timestamp issues common in Shorts/HLS streams
        ydl_opts["postprocessors"] = [{"key": "FFmpegFixupM3u8"}]

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            base = os.path.splitext(filename)[0]
            final = f"{base}.{ext}"
            if os.path.exists(final):
                return True, "Download complete!", final
            candidates = sorted(Path(output_dir).glob(f"*.{ext}"),
                                key=os.path.getmtime, reverse=True)
            if candidates:
                return True, "Download complete!", str(candidates[0])
            all_files = sorted(Path(output_dir).iterdir(),
                               key=os.path.getmtime, reverse=True)
            if all_files:
                return True, "Download complete!", str(all_files[0])
            return False, "File not found after download.", None
    except yt_dlp.utils.DownloadError as exc:
        return False, f"Download failed: {exc}", None
    except Exception as exc:
        return False, f"Unexpected error: {exc}", None


# ── Session state ──────────────────────────────────────────────────────────────
for key, val in {
    "yt_result_path": None,
    "yt_result_ext": "mp4",
    "yt_result_mime": "video/mp4",
    "yt_downloading": False,
    "yt_info": None,
    "yt_last_url": "",
    "yt_cookie_path": None,
}.items():
    if key not in st.session_state:
        st.session_state[key] = val


# ── UI ─────────────────────────────────────────────────────────────────────────
st.title(":material/play_circle: YouTube Downloader")
st.caption("Download videos as MP4 or extract audio as MP3.")
st.divider()

# ── Cookies uploader (collapsed by default) ────────────────────────────────────
with st.expander(":material/cookie: Upload cookies.txt (fixes 403 errors)", expanded=False):
    st.markdown(
        """
        YouTube blocks downloads from cloud servers without a real browser session.
        Uploading your browser cookies fixes this instantly.

        **How to export cookies.txt:**
        1. Install the **[Get cookies.txt LOCALLY](https://chrome.google.com/webstore/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc)** Chrome extension
        2. Go to [youtube.com](https://youtube.com) while logged in
        3. Click the extension → **Export** → save as `cookies.txt`
        4. Upload the file below ↓
        """
    )
    cookie_file = st.file_uploader(
        "cookies.txt",
        type=["txt"],
        label_visibility="collapsed",
    )
    if cookie_file:
        # Save to a persistent temp file for this session
        tmp_cookie = tempfile.NamedTemporaryFile(
            delete=False, suffix=".txt", prefix="yt_cookies_"
        )
        tmp_cookie.write(cookie_file.read())
        tmp_cookie.flush()
        tmp_cookie.close()
        st.session_state.yt_cookie_path = tmp_cookie.name
        st.success(":material/check_circle: Cookies loaded — 403 errors should be gone!")

cookie_path = st.session_state.yt_cookie_path

# ── URL input ──────────────────────────────────────────────────────────────────
url_input = st.text_input(
    "YouTube URL",
    placeholder="https://www.youtube.com/watch?v=XXXXXXX",
)

# ── Format selector ────────────────────────────────────────────────────────────
col_v, col_a = st.columns(2)
with col_v:
    video_fmt = st.selectbox(
        ":material/videocam: Video (MP4)",
        options=[k for k in FORMAT_OPTIONS if "MP4" in k],
        index=0,
    )
with col_a:
    audio_fmt = st.selectbox(
        ":material/music_note: Audio (MP3)",
        options=[k for k in FORMAT_OPTIONS if "MP3" in k],
        index=0,
    )

download_type = st.segmented_control(
    "What do you want?",
    options=["Video (MP4)", "Audio (MP3)"],
    default="Video (MP4)",
)
chosen_fmt = video_fmt if download_type == "Video (MP4)" else audio_fmt

# ── Video info preview ─────────────────────────────────────────────────────────
if url_input.strip() and is_valid_youtube_url(url_input):
    if st.session_state.yt_last_url != url_input.strip():
        st.session_state.yt_info = None
        st.session_state.yt_last_url = url_input.strip()

    if st.session_state.yt_info is None:
        with st.spinner("Fetching video info…"):
            st.session_state.yt_info = fetch_video_info(url_input.strip(), cookie_path)

    info = st.session_state.yt_info
    if info:
        with st.container(border=True):
            c1, c2 = st.columns([1, 2])
            with c1:
                if info.get("thumbnail"):
                    st.image(info["thumbnail"])
            with c2:
                st.markdown(f"**{info.get('title', 'Unknown title')}**")
                channel = info.get("uploader") or info.get("channel", "")
                duration = info.get("duration", 0)
                mins, secs = divmod(int(duration), 60)
                views = info.get("view_count")
                if channel:
                    st.caption(f":material/person: {channel}")
                st.caption(
                    f":material/schedule: {mins}:{secs:02d}"
                    + (f"   :material/visibility: {views:,} views" if views else "")
                )

st.divider()

download_clicked = st.button(
    f"Download {chosen_fmt.split('—')[0].strip()}",
    icon=":material/cloud_download:",
    type="primary",
    disabled=st.session_state.yt_downloading,
)

# ── Download ───────────────────────────────────────────────────────────────────
if download_clicked:
    url = url_input.strip()
    if not url:
        st.warning("Please paste a YouTube URL first.")
    elif not is_valid_youtube_url(url):
        st.error("That doesn't look like a valid YouTube URL.")
    else:
        st.session_state.yt_downloading = True
        st.session_state.yt_result_path = None

        with st.spinner(f"Downloading — {chosen_fmt.strip()} …"):
            tmp_dir = tempfile.mkdtemp(prefix="yt_dl_")
            success, message, filepath = download_video(
                url, tmp_dir, chosen_fmt, cookie_path
            )

        st.session_state.yt_downloading = False

        if success and filepath:
            st.session_state.yt_result_path = filepath
            st.session_state.yt_result_ext  = FORMAT_OPTIONS[chosen_fmt]["ext"]
            st.session_state.yt_result_mime = FORMAT_OPTIONS[chosen_fmt]["mime"]
            st.success(message)
        else:
            st.error(message)
            if "403" in message:
                st.info(
                    "**Still getting 403?** Upload your `cookies.txt` using the "
                    "**🍪 Upload cookies.txt** section above — this always fixes it."
                )

# ── Result ─────────────────────────────────────────────────────────────────────
if st.session_state.yt_result_path and os.path.exists(st.session_state.yt_result_path):
    filepath = st.session_state.yt_result_path
    ext  = st.session_state.yt_result_ext
    mime = st.session_state.yt_result_mime

    st.divider()
    st.subheader(":material/check_circle: Ready!")

    if ext == "mp4":
        st.video(filepath)
    else:
        st.audio(filepath, format="audio/mp3")

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
