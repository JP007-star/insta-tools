import os
import subprocess
import sys

# ── Bootstrap Deno (needed by yt-dlp EJS signature solver) ────────────────────
DENO_BIN = os.path.expanduser("~/.deno/bin/deno")
DENO_DIR = os.path.expanduser("~/.deno/bin")

if not os.path.exists(DENO_BIN):
    try:
        subprocess.run(
            "curl -fsSL https://deno.land/install.sh | sh",
            shell=True, check=False
        )
    except Exception:
        pass

if DENO_DIR not in os.environ.get("PATH", ""):
    os.environ["PATH"] = DENO_DIR + os.pathsep + os.environ.get("PATH", "")

# ── Streamlit app ──────────────────────────────────────────────────────────────
import streamlit as st

st.set_page_config(
    page_title="Insta & YouTube Downloader",
    page_icon=":material/download:",
    layout="centered",
)

pg = st.navigation([
    st.Page("app_pages/instagram.py", title="Instagram Reel", icon=":material/photo_camera:"),
    st.Page("app_pages/youtube.py",   title="YouTube",        icon=":material/play_circle:"),
])

pg.run()
