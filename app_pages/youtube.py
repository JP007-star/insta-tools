import streamlit as st
import os
import re
import subprocess
import tempfile
from pathlib import Path

try:
    from pytubefix import YouTube
    import imageio_ffmpeg
    PYTUBEFIX_OK = True
except ImportError:
    PYTUBEFIX_OK = False

# ── Helpers ────────────────────────────────────────────────────────────────────

def get_ffmpeg() -> str:
    """Return the ffmpeg binary path (bundled via imageio-ffmpeg)."""
    return imageio_ffmpeg.get_ffmpeg_exe()


def is_valid_youtube_url(url: str) -> bool:
    pattern = (
        r"(https?://)?(www\.)?"
        r"(youtube\.com/(watch\?v=|shorts/|embed/)|youtu\.be/)[\w\-]+"
    )
    return bool(re.match(pattern, url.strip()))


CLIENT_LIST = ["ANDROID_VR", "ANDROID", "IOS", "WEB"]

def get_youtube_instance(url: str, client: str = "ANDROID_VR") -> YouTube:
    """Create a YouTube instance with the specified client."""
    return YouTube(url, client=client)

@st.cache_data(ttl=300, show_spinner=False)
def fetch_video_info(url: str) -> dict | None:
    """Fetch title, thumbnail, duration, channel — no download."""
    for client in CLIENT_LIST:
        try:
            yt = get_youtube_instance(url, client=client)
            return {
                "title":     yt.title,
                "thumbnail": yt.thumbnail_url,
                "duration":  yt.length,        # seconds
                "channel":   yt.author,
                "views":     yt.views,
            }
        except Exception:
            continue
    return None


QUALITY_OPTIONS = {
    "🎬  Best quality (1080p)": 1080,
    "🎬  720p":                  720,
    "🎬  480p":                  480,
    "🎬  360p":                  360,
}


def download_mp4(url: str, output_dir: str, max_height: int) -> tuple[bool, str, str | None]:
    """Download video + audio separately across fallback clients, merge with ffmpeg."""
    last_err = ""
    for client in CLIENT_LIST:
        try:
            yt = get_youtube_instance(url, client=client)

            # Pick best mp4 video stream at or below requested height
            video_streams = (
                yt.streams
                .filter(adaptive=True, file_extension="mp4", only_video=True)
                .order_by("resolution")
                .desc()
            )
            video = next(
                (s for s in video_streams if s.resolution and int(s.resolution[:-1]) <= max_height),
                video_streams.first(),
            )

            # Pick best audio (prefer m4a/mp4, fallback to webm)
            audio = (
                yt.streams
                .filter(adaptive=True, only_audio=True, file_extension="mp4")
                .order_by("abr").desc().first()
            ) or (
                yt.streams
                .filter(adaptive=True, only_audio=True)
                .order_by("abr").desc().first()
            )

            if not video or not audio:
                continue

            vpath = video.download(output_path=output_dir, filename=f"video_raw_{client}.mp4")
            apath = audio.download(output_path=output_dir, filename=f"audio_raw_{client}")

            # Safe filename from title
            safe_title = re.sub(r'[\\/*?:"<>|]', "", yt.title)[:80]
            out_path = os.path.join(output_dir, f"{safe_title}.mp4")

            ffmpeg = get_ffmpeg()
            result = subprocess.run(
                [ffmpeg, "-i", vpath, "-i", apath,
                 "-c:v", "copy", "-c:a", "aac", "-y", out_path],
                capture_output=True,
            )

            if result.returncode != 0:
                last_err = result.stderr.decode()[-300:]
                continue

            return True, "Download complete!", out_path

        except Exception as exc:
            last_err = str(exc)
            continue

    return False, f"Download failed: {last_err or 'No stream could be downloaded.'}", None


def download_mp3(url: str, output_dir: str, kbps: str) -> tuple[bool, str, str | None]:
    """Download best audio across fallback clients and convert to MP3."""
    last_err = ""
    for client in CLIENT_LIST:
        try:
            yt = get_youtube_instance(url, client=client)

            audio = (
                yt.streams
                .filter(adaptive=True, only_audio=True)
                .order_by("abr").desc().first()
            )
            if not audio:
                continue

            apath = audio.download(output_path=output_dir, filename=f"audio_raw_{client}")

            safe_title = re.sub(r'[\\/*?:"<>|]', "", yt.title)[:80]
            out_path = os.path.join(output_dir, f"{safe_title}.mp3")

            ffmpeg = get_ffmpeg()
            result = subprocess.run(
                [ffmpeg, "-i", apath, "-vn",
                 "-ab", f"{kbps}k", "-ar", "44100", "-y", out_path],
                capture_output=True,
            )

            if result.returncode != 0:
                last_err = result.stderr.decode()[-300:]
                continue

            return True, "Download complete!", out_path

        except Exception as exc:
            last_err = str(exc)
            continue

    return False, f"Download failed: {last_err or 'Audio stream could not be converted.'}", None


# ── Session state ──────────────────────────────────────────────────────────────
for k, v in {
    "yt_result_path": None,
    "yt_result_ext":  "mp4",
    "yt_result_mime": "video/mp4",
    "yt_downloading":  False,
    "yt_last_url":    "",
    "yt_info":        None,
}.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ── UI ─────────────────────────────────────────────────────────────────────────
st.title(":material/play_circle: YouTube Downloader")
st.caption("Paste any YouTube or Shorts link — no login required.")
st.divider()

url_input = st.text_input(
    "YouTube URL",
    placeholder="https://www.youtube.com/watch?v=... or https://youtube.com/shorts/...",
)

# Format selector
col_v, col_a = st.columns(2)
with col_v:
    video_quality = st.selectbox(
        ":material/videocam: Video quality",
        options=list(QUALITY_OPTIONS.keys()),
        index=0,
    )
with col_a:
    audio_quality = st.selectbox(
        ":material/music_note: Audio quality (MP3)",
        options=["320 kbps", "192 kbps", "128 kbps"],
        index=0,
    )

download_type = st.segmented_control(
    "Download as",
    options=["Video (MP4)", "Audio (MP3)"],
    default="Video (MP4)",
)

# ── Video info preview ─────────────────────────────────────────────────────────
if url_input.strip() and is_valid_youtube_url(url_input):
    if st.session_state.yt_last_url != url_input.strip():
        st.session_state.yt_info = None
        st.session_state.yt_last_url = url_input.strip()
        st.session_state.yt_result_path = None

    if st.session_state.yt_info is None:
        with st.spinner("Fetching video info…"):
            st.session_state.yt_info = fetch_video_info(url_input.strip())

    info = st.session_state.yt_info
    if info:
        with st.container(border=True):
            c1, c2 = st.columns([1, 2])
            with c1:
                if info.get("thumbnail"):
                    st.image(info["thumbnail"])
            with c2:
                st.markdown(f"**{info.get('title', '')}**")
                dur = info.get("duration", 0) or 0
                mins, secs = divmod(int(dur), 60)
                channel = info.get("channel", "")
                views   = info.get("views")
                if channel:
                    st.caption(f":material/person: {channel}")
                st.caption(
                    f":material/schedule: {mins}:{secs:02d}"
                    + (f"   :material/visibility: {views:,} views" if views else "")
                )

elif url_input.strip() and not is_valid_youtube_url(url_input):
    st.error("That doesn't look like a valid YouTube URL.")

st.divider()

download_clicked = st.button(
    "Download",
    icon=":material/cloud_download:",
    type="primary",
    disabled=st.session_state.yt_downloading or not url_input.strip(),
)

# ── Download ───────────────────────────────────────────────────────────────────
if download_clicked:
    url = url_input.strip()
    if not is_valid_youtube_url(url):
        st.error("Invalid URL.")
    elif not PYTUBEFIX_OK:
        st.error("pytubefix is not installed. Run: pip install pytubefix imageio-ffmpeg")
    else:
        st.session_state.yt_downloading = True
        st.session_state.yt_result_path = None

        tmp_dir = tempfile.mkdtemp(prefix="yt_dl_")

        if download_type == "Video (MP4)":
            max_h = QUALITY_OPTIONS[video_quality]
            label = video_quality
            with st.spinner(f"Downloading {label} — please wait…"):
                ok, msg, path = download_mp4(url, tmp_dir, max_h)
            ext, mime = "mp4", "video/mp4"
        else:
            kbps = audio_quality.split()[0]
            with st.spinner(f"Downloading audio ({kbps} kbps) — please wait…"):
                ok, msg, path = download_mp3(url, tmp_dir, kbps)
            ext, mime = "mp3", "audio/mpeg"

        st.session_state.yt_downloading = False

        if ok and path:
            st.session_state.yt_result_path = path
            st.session_state.yt_result_ext  = ext
            st.session_state.yt_result_mime = mime
            st.success(msg)
        else:
            st.error(msg)

# ── Result ─────────────────────────────────────────────────────────────────────
if st.session_state.yt_result_path and os.path.exists(st.session_state.yt_result_path):
    path = st.session_state.yt_result_path
    ext  = st.session_state.yt_result_ext
    mime = st.session_state.yt_result_mime

    st.divider()
    st.subheader(":material/check_circle: Ready!")

    if ext == "mp4":
        st.video(path)
    else:
        st.audio(path, format="audio/mp3")

    with open(path, "rb") as f:
        st.download_button(
            label=f"Save {ext.upper()} to your device",
            data=f,
            file_name=os.path.basename(path),
            mime=mime,
            icon=":material/save:",
            type="primary",
        )

st.divider()
st.caption(":material/info: For personal use only. Respect copyright and YouTube's Terms of Service.")
