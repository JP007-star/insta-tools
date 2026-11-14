import streamlit as st
import yt_dlp
import os
import tempfile
import re
from pathlib import Path

st.set_page_config(
    page_title="Instagram Reel Downloader",
    page_icon=":material/download:",
    layout="centered",
)

# ── Helpers ────────────────────────────────────────────────────────────────────

def is_valid_instagram_url(url: str) -> bool:
    pattern = r"(https?://)?(www\.)?instagram\.com/(reel|reels|p)/[\w-]+/?"
    return bool(re.match(pattern, url.strip()))


def download_reel(url: str, output_dir: str) -> tuple[bool, str, str | None]:
    """
    Downloads the reel to output_dir.
    Returns (success, message, filepath_or_none).
    """
    ydl_opts = {
        "outtmpl": os.path.join(output_dir, "%(title)s.%(ext)s"),
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "quiet": True,
        "no_warnings": True,
        "merge_output_format": "mp4",
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            # Normalise extension
            if not filename.endswith(".mp4"):
                filename = os.path.splitext(filename)[0] + ".mp4"
            if os.path.exists(filename):
                return True, "Download complete!", filename
            # Sometimes yt-dlp writes the merged file with a slightly different name
            candidates = list(Path(output_dir).glob("*.mp4"))
            if candidates:
                return True, "Download complete!", str(candidates[0])
            return False, "File not found after download.", None
    except yt_dlp.utils.DownloadError as exc:
        return False, f"Download failed: {exc}", None
    except Exception as exc:
        return False, f"Unexpected error: {exc}", None


# ── Session state defaults ─────────────────────────────────────────────────────

if "result_path" not in st.session_state:
    st.session_state.result_path = None
if "downloading" not in st.session_state:
    st.session_state.downloading = False

# ── UI ─────────────────────────────────────────────────────────────────────────

st.title(":material/download: Instagram Reel Downloader")
st.caption("Paste an Instagram Reel link and download it as an MP4.")

st.divider()

url_input = st.text_input(
    "Instagram Reel URL",
    placeholder="https://www.instagram.com/reel/XXXXXXX/",
    label_visibility="visible",
)

download_clicked = st.button(
    "Download reel",
    icon=":material/cloud_download:",
    type="primary",
    disabled=st.session_state.downloading,
)

# ── Download logic ─────────────────────────────────────────────────────────────

if download_clicked:
    url = url_input.strip()

    if not url:
        st.warning("Please paste an Instagram Reel URL first.")
    elif not is_valid_instagram_url(url):
        st.error(
            "That doesn't look like a valid Instagram Reel URL. "
            "It should contain `/reel/` or `/p/`."
        )
    else:
        st.session_state.downloading = True
        st.session_state.result_path = None

        with st.spinner("Downloading reel — this may take a moment…"):
            tmp_dir = tempfile.mkdtemp(prefix="ig_reel_")
            success, message, filepath = download_reel(url, tmp_dir)

        st.session_state.downloading = False

        if success and filepath:
            st.session_state.result_path = filepath
            st.success(message)
        else:
            st.error(message)
            st.info(
                "**Tip:** Make sure the reel is public. "
                "Private reels cannot be downloaded."
            )

# ── Show download button if file is ready ──────────────────────────────────────

if st.session_state.result_path and os.path.exists(st.session_state.result_path):
    filepath = st.session_state.result_path
    st.divider()
    st.subheader(":material/check_circle: Reel ready!")

    # In-app preview
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

# ── Footer ─────────────────────────────────────────────────────────────────────

st.divider()
st.caption(
    ":material/info: For personal use only. "
    "Respect copyright and Instagram's Terms of Service."
)
