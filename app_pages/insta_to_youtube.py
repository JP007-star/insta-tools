import streamlit as st
import os
import json
import tempfile
import urllib.parse
from pathlib import Path

from insta_extractor import (
    is_valid_instagram_url,
    extract_instagram_urls,
    fetch_instagram_reel,
)
from youtube_publisher import (
    create_oauth_flow,
    exchange_code_for_credentials,
    get_credentials_from_dict,
    get_channel_info,
    upload_to_youtube,
    YOUTUBE_CATEGORIES,
)

# ── Session State Initialization ──────────────────────────────────────────────
if "yt_auth_token" not in st.session_state:
    st.session_state.yt_auth_token = None
if "yt_channel" not in st.session_state:
    st.session_state.yt_channel = None
if "extracted_reels" not in st.session_state:
    st.session_state.extracted_reels = []
if "is_publishing" not in st.session_state:
    st.session_state.is_publishing = False

TOKEN_SAVE_PATH = os.path.join(tempfile.gettempdir(), "yt_session_token.json")

# Attempt to restore token from tempfile if available
if st.session_state.yt_auth_token is None and os.path.exists(TOKEN_SAVE_PATH):
    try:
        with open(TOKEN_SAVE_PATH, "r", encoding="utf-8") as f:
            saved_token = json.load(f)
            creds = get_credentials_from_dict(saved_token)
            channel = get_channel_info(creds)
            if channel:
                st.session_state.yt_auth_token = saved_token
                st.session_state.yt_channel = channel
    except Exception:
        pass


# ── UI Header ─────────────────────────────────────────────────────────────────
st.title(":material/auto_upload: Instagram to YouTube Publisher")
st.caption(
    "Cross-post Instagram Reels to YouTube Shorts: auto-extract videos, captions, "
    "and hashtags, then publish directly to your YouTube channel."
)
st.divider()

# ── 1. YouTube Channel Connection Section ─────────────────────────────────────
st.subheader(":material/account_circle: 1. YouTube Channel Connection")

channel = st.session_state.yt_channel
if channel:
    with st.container(border=True):
        col1, col2, col3 = st.columns([1, 3, 1])
        with col1:
            if channel.get("thumbnail"):
                st.image(channel["thumbnail"], width=80)
        with col2:
            st.markdown(f"**Connected Channel:** {channel.get('title')}")
            sub_count = int(channel.get("subscriberCount", 0))
            vid_count = int(channel.get("videoCount", 0))
            st.caption(f":material/group: {sub_count:,} Subscribers  |  :material/video_library: {vid_count:,} Videos")
        with col3:
            if st.button("Disconnect", icon=":material/logout:", type="secondary"):
                st.session_state.yt_auth_token = None
                st.session_state.yt_channel = None
                if os.path.exists(TOKEN_SAVE_PATH):
                    os.remove(TOKEN_SAVE_PATH)
                st.rerun()
else:
    st.info("Connect your YouTube Channel using a Google Cloud OAuth Client ID to enable publishing.")

    with st.expander(":material/key: How to connect your YouTube Channel (OAuth Setup)", expanded=True):
        st.markdown(
            """
            **Quick 3-step setup (free):**
            1. Go to [Google Cloud Console](https://console.cloud.google.com/) -> Create project -> Enable **YouTube Data API v3**.
            2. In **APIs & Services -> Credentials**, click **Create Credentials -> OAuth client ID** (Application Type: **Desktop App**).
            3. Download or copy your credentials, and upload/paste them below.
            """
        )

        auth_method = st.radio(
            "Authentication Method:",
            options=["Upload client_secrets.json", "Enter Client ID & Secret manually", "Upload existing token.json"],
            horizontal=True,
        )

        client_config = None

        if auth_method == "Upload client_secrets.json":
            secrets_file = st.file_uploader("Upload client_secrets.json", type=["json"], key="secrets_uploader")
            if secrets_file:
                try:
                    raw_data = json.loads(secrets_file.read().decode("utf-8"))
                    client_config = raw_data
                except Exception as e:
                    st.error(f"Invalid JSON file: {e}")

        elif auth_method == "Enter Client ID & Secret manually":
            c_id = st.text_input("Google Client ID", placeholder="xxxx.apps.googleusercontent.com")
            c_secret = st.text_input("Google Client Secret", type="password")
            if c_id and c_secret:
                client_config = {
                    "installed": {
                        "client_id": c_id.strip(),
                        "client_secret": c_secret.strip(),
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"]
                    }
                }

        elif auth_method == "Upload existing token.json":
            token_file = st.file_uploader("Upload token.json", type=["json"], key="token_uploader")
            if token_file:
                try:
                    token_data = json.loads(token_file.read().decode("utf-8"))
                    creds = get_credentials_from_dict(token_data)
                    chan_info = get_channel_info(creds)
                    if chan_info:
                        st.session_state.yt_auth_token = token_data
                        st.session_state.yt_channel = chan_info
                        with open(TOKEN_SAVE_PATH, "w", encoding="utf-8") as f:
                            json.dump(token_data, f)
                        st.success(f"Connected to {chan_info['title']}!")
                        st.rerun()
                    else:
                        st.error("Token is invalid or expired. Please re-authenticate.")
                except Exception as e:
                    st.error(f"Error loading token: {e}")

        if client_config:
            try:
                flow = create_oauth_flow(client_config)
                auth_url, _ = flow.authorization_url(prompt="consent", access_type="offline")

                st.markdown(f"**Step 2:** Click the link below to authorize your YouTube channel:")
                st.markdown(f"👉 **[Click here to Authorize with Google]({auth_url})**")

                auth_code = st.text_input(
                    "Paste the Google Authorization Code here:",
                    placeholder="4/0A...",
                    help="Copy the code from Google's authorization screen and paste it here.",
                )

                if st.button("Complete Connection", type="primary", icon=":material/check:"):
                    if not auth_code.strip():
                        st.warning("Please paste the authorization code first.")
                    else:
                        with st.spinner("Connecting to YouTube..."):
                            token_dict = exchange_code_for_credentials(flow, auth_code.strip())
                            creds = get_credentials_from_dict(token_dict)
                            chan_info = get_channel_info(creds)
                            if chan_info:
                                st.session_state.yt_auth_token = token_dict
                                st.session_state.yt_channel = chan_info
                                with open(TOKEN_SAVE_PATH, "w", encoding="utf-8") as f:
                                    json.dump(token_dict, f)
                                st.success(f"Successfully connected to {chan_info['title']}!")
                                st.rerun()
                            else:
                                st.error("Failed to verify YouTube channel with this authorization.")
            except Exception as e:
                st.error(f"OAuth initialization error: {e}")

st.divider()

# ── 2. Fetch Instagram Reels ──────────────────────────────────────────────────
st.subheader(":material/download: 2. Fetch Instagram Videos & Metadata")

fetch_mode = st.radio(
    "Mode:",
    options=["Single Reel / Post", "Batch (Multiple Reels)"],
    horizontal=True,
)

urls_to_fetch = []

if fetch_mode == "Single Reel / Post":
    single_url = st.text_input(
        "Instagram Reel / Video URL",
        placeholder="https://www.instagram.com/reel/XXXXXXXXXXX/",
    )
    if single_url.strip():
        if is_valid_instagram_url(single_url):
            urls_to_fetch = [single_url.strip()]
        else:
            st.error("Invalid Instagram URL format.")
else:
    multi_url_text = st.text_area(
        "Paste multiple Instagram Reel URLs (one per line):",
        placeholder="https://www.instagram.com/reel/AAA/\nhttps://www.instagram.com/reel/BBB/\n...",
        height=120,
    )
    if multi_url_text.strip():
        urls_to_fetch = extract_instagram_urls(multi_url_text)
        if urls_to_fetch:
            st.caption(f":material/playlist_add_check: Found {len(urls_to_fetch)} Instagram URL(s)")

fetch_clicked = st.button(
    f"Fetch Metadata & Video ({len(urls_to_fetch)})",
    type="primary",
    icon=":material/cloud_download:",
    disabled=len(urls_to_fetch) == 0,
)

if fetch_clicked:
    st.session_state.extracted_reels = []
    progress_bar = st.progress(0, text="Fetching reels...")
    temp_dir = tempfile.mkdtemp(prefix="insta_batch_")

    for idx, url in enumerate(urls_to_fetch):
        progress_text = f"Fetching ({idx + 1}/{len(urls_to_fetch)}): {url[:45]}..."
        progress_bar.progress(int((idx / len(urls_to_fetch)) * 100), text=progress_text)

        ok, msg, data = fetch_instagram_reel(url, temp_dir)
        if ok and data:
            st.session_state.extracted_reels.append(data)
        else:
            st.error(f"Failed to fetch {url}: {msg}")

    progress_bar.progress(100, text="Done fetching!")
    if st.session_state.extracted_reels:
        st.success(f"Successfully processed {len(st.session_state.extracted_reels)} reel(s)!")

st.divider()

# ── 3. Review, Edit & Publish to YouTube ──────────────────────────────────────
reels = st.session_state.extracted_reels

if reels:
    st.subheader(f":material/edit_note: 3. Review & Publish ({len(reels)} Reel{'s' if len(reels) > 1 else ''})")

    # Global Publishing Settings
    with st.container(border=True):
        st.markdown("**Global YouTube Settings**")
        col_cat, col_priv = st.columns(2)
        with col_cat:
            cat_choice = st.selectbox(
                "YouTube Category",
                options=list(YOUTUBE_CATEGORIES.keys()),
                format_func=lambda x: f"{YOUTUBE_CATEGORIES[x]} ({x})",
                index=0,
            )
        with col_priv:
            privacy_choice = st.selectbox(
                "Privacy Status",
                options=["Public", "Unlisted", "Private"],
                index=0,
                help="Recommended: Start with Unlisted or Private to review before making Public.",
            )

    # Edit individual video cards
    for idx, r in enumerate(reels):
        with st.container(border=True):
            st.markdown(f"### Video {idx + 1}: @{r.get('uploader')}")
            col_v, col_m = st.columns([1, 2])

            with col_v:
                if os.path.exists(r["video_path"]):
                    st.video(r["video_path"])
                else:
                    st.warning("Video file not found.")

            with col_m:
                r["title"] = st.text_input(
                    f"Title #{idx + 1}",
                    value=r.get("title", ""),
                    max_chars=100,
                    key=f"title_{idx}",
                )

                r["description"] = st.text_area(
                    f"Description #{idx + 1}",
                    value=r.get("description", ""),
                    height=130,
                    key=f"desc_{idx}",
                )

                tag_string = ", ".join(r.get("hashtags", []))
                edited_tags = st.text_input(
                    f"Tags / Hashtags #{idx + 1} (comma separated)",
                    value=tag_string,
                    key=f"tags_{idx}",
                )
                r["hashtags"] = [t.strip() for t in edited_tags.split(",") if t.strip()]

    st.divider()

    # ── Publish Button ────────────────────────────────────────────────────────
    can_publish = st.session_state.yt_auth_token is not None

    if not can_publish:
        st.warning("Please connect your YouTube channel in Step 1 before publishing.")

    publish_btn = st.button(
        f"Publish {len(reels)} Video(s) to YouTube",
        type="primary",
        icon=":material/upload:",
        disabled=not can_publish or st.session_state.is_publishing,
    )

    if publish_btn:
        st.session_state.is_publishing = True
        creds = get_credentials_from_dict(st.session_state.yt_auth_token)

        pub_progress = st.progress(0, text="Starting YouTube upload...")
        results = []

        for idx, r in enumerate(reels):
            pub_progress.progress(
                int((idx / len(reels)) * 100),
                text=f"Uploading ({idx + 1}/{len(reels)}): {r['title'][:40]}...",
            )

            success, msg, video_id = upload_to_youtube(
                creds=creds,
                file_path=r["video_path"],
                title=r["title"],
                description=r["description"],
                tags=r["hashtags"],
                category_id=cat_choice,
                privacy_status=privacy_choice,
            )

            results.append({
                "title": r["title"],
                "success": success,
                "message": msg,
                "video_id": video_id,
            })

        pub_progress.progress(100, text="Publishing complete!")
        st.session_state.is_publishing = False

        # Display results summary
        st.subheader(":material/task_alt: Upload Results")
        for res in results:
            if res["success"]:
                vid_url = f"https://youtu.be/{res['video_id']}"
                st.success(f"**Uploaded:** {res['title']}")
                st.markdown(f"👉 **Watch on YouTube:** [{vid_url}]({vid_url})")
            else:
                st.error(f"**Failed:** {res['title']} — {res['message']}")

st.divider()
st.caption(":material/info: Cross-posting tool for creators. Ensure you have the rights to content before publishing.")
