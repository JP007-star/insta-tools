import streamlit as st
import os
import tempfile
import re
from pathlib import Path

from insta_extractor import (
    is_valid_instagram_url,
    fetch_instagram_reel,
)
from youtube_publisher import (
    get_preconfigured_credentials,
    get_channel_info,
    get_credentials_from_dict,
    upload_to_youtube,
)

# ── Session state ──────────────────────────────────────────────────────────────
if "ig_result_path" not in st.session_state:
    st.session_state.ig_result_path = None
if "ig_data" not in st.session_state:
    st.session_state.ig_data = None
if "ig_last_url" not in st.session_state:
    st.session_state.ig_last_url = ""
if "ig_is_publishing" not in st.session_state:
    st.session_state.ig_is_publishing = False

# Auto-load channel credentials
if "yt_auth_token" not in st.session_state:
    pre_creds = get_preconfigured_credentials()
    if pre_creds:
        st.session_state.yt_auth_token = {
            "token": pre_creds.token,
            "refresh_token": pre_creds.refresh_token,
            "token_uri": pre_creds.token_uri,
            "client_id": pre_creds.client_id,
            "client_secret": pre_creds.client_secret,
            "scopes": pre_creds.scopes,
        }

# ── UI ─────────────────────────────────────────────────────────────────────────
st.title(":material/photo_camera: Instagram Reel Downloader & Cross-Poster")
st.caption("Paste an Instagram Reel link — it automatically fetches the video and lets you download or cross-post to YouTube.")
st.divider()

url_input = st.text_input(
    ":material/link: Instagram Reel URL",
    placeholder="https://www.instagram.com/reel/XXXXXXX/",
    help="Video will auto-fetch as soon as you paste the link!",
)

clean_url = url_input.strip()

# ── AUTO-FETCH ON PASTE ────────────────────────────────────────────────────────
if clean_url:
    if not is_valid_instagram_url(clean_url):
        st.error("That doesn't look like a valid Instagram Reel URL. It should contain `/reel/` or `/p/`.")
    else:
        if clean_url != st.session_state.ig_last_url:
            with st.spinner("🔄 Automatically fetching Instagram Reel..."):
                tmp_dir = tempfile.mkdtemp(prefix="ig_auto_")
                success, message, data = fetch_instagram_reel(clean_url, tmp_dir)

            if success and data:
                st.session_state.ig_data = data
                st.session_state.ig_result_path = data["video_path"]
                st.session_state.ig_last_url = clean_url
                st.toast("✅ Reel fetched automatically!", icon="🎉")
            else:
                st.session_state.ig_data = None
                st.session_state.ig_result_path = None
                st.error(f"Download failed: {message}")
                st.info("**Tip:** Make sure the reel is public. Private reels cannot be downloaded.")

# ── PREVIEW & ACTIONS ──────────────────────────────────────────────────────────
if st.session_state.ig_result_path and os.path.exists(st.session_state.ig_result_path):
    filepath = st.session_state.ig_result_path
    data = st.session_state.ig_data or {}

    st.divider()
    st.subheader(f":material/check_circle: Ready: {data.get('title', 'Instagram Video')}")

    # Video Player Preview
    st.video(filepath)

    if data.get("caption"):
        with st.expander(":material/description: View Instagram Caption & Hashtags", expanded=False):
            st.markdown(data["caption"])

    col1, col2 = st.columns([1, 1])

    with col1:
        with open(filepath, "rb") as f:
            st.download_button(
                label="Save MP4 to your device",
                data=f,
                file_name=os.path.basename(filepath),
                mime="video/mp4",
                icon=":material/save:",
                use_container_width=True,
            )

    with col2:
        can_yt = st.session_state.get("yt_auth_token") is not None
        crosspost_clicked = st.button(
            "🚀 Cross-Post to YouTube Shorts",
            type="primary",
            icon=":material/rocket_launch:",
            disabled=not can_yt or st.session_state.ig_is_publishing,
            use_container_width=True,
        )

    if not can_yt:
        st.caption(":material/info: Connect your YouTube account in the 'Insta to YouTube Publisher' page to enable 1-click cross-posting.")

    # ── Execute Cross-Post directly from this page ────────────────────────────
    if crosspost_clicked and data:
        st.session_state.ig_is_publishing = True
        with st.spinner("Publishing to YouTube Shorts..."):
            creds = get_credentials_from_dict(st.session_state.yt_auth_token)
            ok, msg, video_id = upload_to_youtube(
                creds=creds,
                file_path=filepath,
                title=data.get("title", "Instagram Reel #Shorts"),
                description=data.get("description", ""),
                tags=data.get("hashtags", []),
                category_id="22",
                privacy_status="public",
            )
        st.session_state.ig_is_publishing = False

        if ok and video_id:
            yt_url = f"https://youtu.be/{video_id}"
            st.success("🎉 **Successfully cross-posted to YouTube!**")
            st.markdown(f"### 👉 [Watch Short on YouTube: {yt_url}]({yt_url})")
            st.balloons()
        else:
            st.error(f"Upload failed: {msg}")

st.divider()
st.caption(":material/info: For personal use only. Respect copyright and Instagram's Terms of Service.")
