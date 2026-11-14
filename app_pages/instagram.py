import streamlit as st
import yt_dlp
import os
import tempfile
import re
from pathlib import Path


def is_valid_instagram_url(url: str) -> bool:
    pattern = r"(https?://)?(www\.)?instagram\.com/(reel|reels|p)/[\w-]+/?"
    return bool(re.match(pattern, url.strip()))


def download_reel(url: str, output_dir: str) -> tuple[bool, str, str | None]:
    ydl_opts = {
        "outtmpl": os.path.join(output_dir, "%(title)s.%(ext)s"),
        "format": "best[ext=mp4]/best",
        "quiet": True,
        "no_warnings": True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            if not filename.endswith(".mp4"):
                filename = os.path.splitext(filename)[0] + ".mp4"
            if os.path.exists(filename):
                return True, "Download complete!", filename
            candidates = list(Path(output_dir).glob("*.mp4"))
            if candidates:
                return True, "Download complete!", str(candidates[0])
            return False, "File not found after download.", None
    except yt_dlp.utils.DownloadError as exc:
        return False, f"Download failed: {exc}", None
    except Exception as exc:
        return False, f"Unexpected error: {exc}", None


# ── Session state ──────────────────────────────────────────────────────────────
if "ig_result_path" not in st.session_state:
    st.session_state.ig_result_path = None
if "ig_downloading" not in st.session_state:
    st.session_state.ig_downloading = False

# ── UI ─────────────────────────────────────────────────────────────────────────
st.title(":material/photo_camera: Instagram Reel Downloader")
st.caption("Paste an Instagram Reel link and download it as an MP4.")
st.divider()

url_input = st.text_input(
    "Instagram Reel URL",
    placeholder="https://www.instagram.com/reel/XXXXXXX/",
)

download_clicked = st.button(
    "Download reel",
    icon=":material/cloud_download:",
    type="primary",
    disabled=st.session_state.ig_downloading,
)

if download_clicked:
    url = url_input.strip()
    if not url:
        st.warning("Please paste an Instagram Reel URL first.")
    elif not is_valid_instagram_url(url):
        st.error("That doesn't look like a valid Instagram Reel URL. It should contain `/reel/` or `/p/`.")
    else:
        st.session_state.ig_downloading = True
        st.session_state.ig_result_path = None
        with st.spinner("Downloading reel — this may take a moment…"):
            tmp_dir = tempfile.mkdtemp(prefix="ig_reel_")
            success, message, filepath = download_reel(url, tmp_dir)
        st.session_state.ig_downloading = False
        if success and filepath:
            st.session_state.ig_result_path = filepath
            st.success(message)
        else:
            st.error(message)
            st.info("**Tip:** Make sure the reel is public. Private reels cannot be downloaded.")

if st.session_state.ig_result_path and os.path.exists(st.session_state.ig_result_path):
    filepath = st.session_state.ig_result_path
    st.divider()
    st.subheader(":material/check_circle: Reel ready!")
    st.video(filepath)
    with open(filepath, "rb") as f:
        video_bytes = f.read()
    st.download_button(
        label="Save to your device",
        data=video_bytes,
        file_name=os.path.basename(filepath),
        mime="video/mp4",
        icon=":material/save:",
        type="primary",
    )

st.divider()
st.caption(":material/info: For personal use only. Respect copyright and Instagram's Terms of Service.")
