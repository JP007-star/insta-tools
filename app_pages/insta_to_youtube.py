import streamlit as st
import os
import json
import tempfile
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
    get_preconfigured_credentials,
    upload_to_youtube,
    YOUTUBE_CATEGORIES,
)

# ── Session State Initialization ──────────────────────────────────────────────
if "yt_auth_token" not in st.session_state:
    st.session_state.yt_auth_token = None
if "yt_channel" not in st.session_state:
    st.session_state.yt_channel = None
if "current_reel" not in st.session_state:
    st.session_state.current_reel = None
if "last_fetched_url" not in st.session_state:
    st.session_state.last_fetched_url = ""
if "batch_reels" not in st.session_state:
    st.session_state.batch_reels = []
if "is_publishing" not in st.session_state:
    st.session_state.is_publishing = False
if "published_results" not in st.session_state:
    st.session_state.published_results = {}

TOKEN_SAVE_PATH = os.path.join(tempfile.gettempdir(), "yt_session_token.json")

# 1. Restore from preconfigured credentials (secrets.toml / token.json)
if st.session_state.yt_channel is None:
    pre_creds = get_preconfigured_credentials()
    if pre_creds:
        channel_info = get_channel_info(pre_creds)
        if channel_info:
            st.session_state.yt_channel = channel_info
            st.session_state.yt_auth_token = {
                "token": pre_creds.token,
                "refresh_token": pre_creds.refresh_token,
                "token_uri": pre_creds.token_uri,
                "client_id": pre_creds.client_id,
                "client_secret": pre_creds.client_secret,
                "scopes": pre_creds.scopes,
            }

# 2. Restore token from tempfile if available
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
st.title(":material/cloud_upload: Instagram to YouTube Publisher")
st.caption("Paste an Instagram Reel URL — it fetches automatically, then 1-click cross-post to YouTube Shorts.")
st.divider()

# ── YouTube Channel Status Banner ─────────────────────────────────────────────
channel = st.session_state.yt_channel
if channel:
    with st.container(border=True):
        c1, c2, c3 = st.columns([1, 4, 1.2])
        with c1:
            if channel.get("thumbnail"):
                st.image(channel["thumbnail"], width=65)
            else:
                st.markdown("## :material/account_circle:")
        with c2:
            st.markdown(f"**Target Channel:** `{channel.get('title')}`")
            st.caption(f":material/check_circle: {channel.get('subscriberCount', 'Ready')} | Status: Ready to publish Shorts")
        with c3:
            if st.button("Change Account", icon=":material/swap_horiz:", type="secondary"):
                st.session_state.yt_auth_token = None
                st.session_state.yt_channel = None
                if os.path.exists(TOKEN_SAVE_PATH):
                    os.remove(TOKEN_SAVE_PATH)
                st.rerun()
else:
    with st.container(border=True):
        st.warning("⚠️ No YouTube Channel connected. Please connect your account below.")
        with st.expander("Connect YouTube Channel (OAuth Setup)"):
            c_id = st.text_input("Client ID", placeholder="xxxx.apps.googleusercontent.com")
            c_secret = st.text_input("Client Secret", type="password")
            if c_id and c_secret:
                client_config = {
                    "installed": {
                        "client_id": c_id.strip(),
                        "client_secret": c_secret.strip(),
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"],
                    }
                }
                flow = create_oauth_flow(client_config)
                auth_url, _ = flow.authorization_url(prompt="consent", access_type="offline")
                st.markdown(f"👉 **[Click here to Authorize with Google]({auth_url})**")
                auth_code = st.text_input("Paste authorization code:")
                if st.button("Connect Channel"):
                    token_dict = exchange_code_for_credentials(flow, auth_code.strip())
                    creds = get_credentials_from_dict(token_dict)
                    st.session_state.yt_auth_token = token_dict
                    st.session_state.yt_channel = get_channel_info(creds)
                    st.rerun()

st.divider()

# ── Mode Selection ────────────────────────────────────────────────────────────
mode = st.segmented_control(
    "Mode",
    options=["Single Reel (Auto-Fetch)", "Batch (Multiple Reels)"],
    default="Single Reel (Auto-Fetch)",
)

# ══════════════════════════════════════════════════════════════════════════════
# MODE 1: SINGLE REEL (AUTO-FETCH & 1-CLICK CROSS-POST)
# ══════════════════════════════════════════════════════════════════════════════
if mode == "Single Reel (Auto-Fetch)":
    url_input = st.text_input(
        ":material/link: Paste Instagram Reel URL",
        placeholder="https://www.instagram.com/reel/XXXXXXXXXXX/",
        help="Paste any public Instagram reel or video URL. It will automatically fetch as soon as pasted!",
    )

    clean_url = url_input.strip()

    # ── AUTOMATIC FETCH ON PASTE ──────────────────────────────────────────────
    if clean_url:
        if not is_valid_instagram_url(clean_url):
            st.error("That does not look like a valid Instagram Reel URL.")
        else:
            # Check if this URL needs to be fetched
            if clean_url != st.session_state.last_fetched_url:
                with st.spinner("🔄 Automatically fetching Instagram video & extracting metadata..."):
                    tmp_dir = tempfile.mkdtemp(prefix="insta_auto_")
                    success, msg, data = fetch_instagram_reel(clean_url, tmp_dir)
                    if success and data:
                        st.session_state.current_reel = data
                        st.session_state.last_fetched_url = clean_url
                        st.toast("✅ Reel fetched automatically!", icon="🎉")
                    else:
                        st.session_state.current_reel = None
                        st.error(f"Failed to fetch: {msg}")

    # ── DISPLAY FETCHED REEL & CROSS-POST BUTTON ──────────────────────────────
    reel = st.session_state.current_reel

    if reel and clean_url == st.session_state.last_fetched_url:
        with st.container(border=True):
            st.markdown(f"### :material/movie: Ready to Cross-Post: @{reel.get('uploader')}")

            col_vid, col_meta = st.columns([1, 1.4])

            with col_vid:
                if os.path.exists(reel["video_path"]):
                    st.video(reel["video_path"])
                st.caption(f":material/person: Creator: **@{reel.get('uploader')}**")

            with col_meta:
                reel["title"] = st.text_input(
                    "YouTube Shorts Title",
                    value=reel.get("title", ""),
                    max_chars=100,
                    help="Auto-extracted from first sentence. Includes #Shorts tag.",
                )

                reel["description"] = st.text_area(
                    "YouTube Description",
                    value=reel.get("description", ""),
                    height=120,
                    help="Includes caption, creator attribution, and hashtags.",
                )

                tags_val = ", ".join(reel.get("hashtags", []))
                new_tags = st.text_input("Tags / Hashtags", value=tags_val)
                reel["hashtags"] = [t.strip() for t in new_tags.split(",") if t.strip()]

                c_cat, c_priv = st.columns(2)
                with c_cat:
                    category = st.selectbox(
                        "Category",
                        options=list(YOUTUBE_CATEGORIES.keys()),
                        format_func=lambda x: f"{YOUTUBE_CATEGORIES[x]}",
                        index=0,
                    )
                with c_priv:
                    privacy = st.selectbox(
                        "Privacy",
                        options=["Public", "Unlisted", "Private"],
                        index=0,
                    )

            st.divider()

            # ── Prominent Cross-Post Button ───────────────────────────────────
            can_publish = st.session_state.yt_auth_token is not None

            col_btn1, col_btn2 = st.columns([2, 1])
            with col_btn1:
                crosspost_clicked = st.button(
                    "🚀 Cross-Post to YouTube Shorts Now",
                    type="primary",
                    icon=":material/rocket_launch:",
                    disabled=not can_publish or st.session_state.is_publishing,
                    use_container_width=True,
                )
            with col_btn2:
                # Also allow direct download of the fetched file
                with open(reel["video_path"], "rb") as f:
                    st.download_button(
                        label="Download MP4",
                        data=f,
                        file_name=os.path.basename(reel["video_path"]),
                        mime="video/mp4",
                        icon=":material/download:",
                        use_container_width=True,
                    )

            if not can_publish:
                st.info(":material/info: Connect your YouTube channel above to enable cross-posting.")

            # ── Execute Cross-Post ────────────────────────────────────────────
            if crosspost_clicked:
                st.session_state.is_publishing = True
                with st.spinner("Publishing to YouTube Shorts..."):
                    creds = get_credentials_from_dict(st.session_state.yt_auth_token)
                    ok, msg, video_id = upload_to_youtube(
                        creds=creds,
                        file_path=reel["video_path"],
                        title=reel["title"],
                        description=reel["description"],
                        tags=reel["hashtags"],
                        category_id=category,
                        privacy_status=privacy,
                    )

                st.session_state.is_publishing = False

                if ok and video_id:
                    yt_url = f"https://youtu.be/{video_id}"
                    st.success(f"🎉 **Cross-Posted to YouTube Successfully!**")
                    st.markdown(f"### 👉 [Watch Short on YouTube: {yt_url}]({yt_url})")
                    st.balloons()
                else:
                    st.error(f"Upload failed: {msg}")

# ══════════════════════════════════════════════════════════════════════════════
# MODE 2: BATCH CROSS-POST (MULTIPLE REELS)
# ══════════════════════════════════════════════════════════════════════════════
else:
    st.markdown("**Paste multiple Instagram Reel URLs to auto-extract and bulk cross-post:**")
    batch_text = st.text_area(
        "Instagram URLs (one per line):",
        placeholder="https://www.instagram.com/reel/AAAAA/\nhttps://www.instagram.com/reel/BBBBB/\nhttps://www.instagram.com/reel/CCCCC/",
        height=140,
    )

    detected_urls = extract_instagram_urls(batch_text) if batch_text.strip() else []

    if detected_urls:
        st.caption(f":material/playlist_add_check: **{len(detected_urls)} valid URL(s) detected**")

    fetch_batch_clicked = st.button(
        f"Fetch All ({len(detected_urls)}) Videos",
        type="primary",
        icon=":material/cloud_download:",
        disabled=len(detected_urls) == 0 or st.session_state.is_publishing,
    )

    if fetch_batch_clicked:
        st.session_state.batch_reels = []
        progress_bar = st.progress(0, text="Fetching reels...")
        batch_tmp = tempfile.mkdtemp(prefix="insta_batch_")

        for i, u in enumerate(detected_urls):
            progress_bar.progress(int((i / len(detected_urls)) * 100), text=f"Fetching ({i + 1}/{len(detected_urls)})...")
            ok, msg, data = fetch_instagram_reel(u, batch_tmp)
            if ok and data:
                st.session_state.batch_reels.append(data)
            else:
                st.error(f"Error fetching {u}: {msg}")

        progress_bar.progress(100, text="All videos fetched!")
        st.success(f"Fetched {len(st.session_state.batch_reels)} video(s)!")

    # Batch Display & Publish
    batch_items = st.session_state.batch_reels
    if batch_items:
        st.divider()
        st.subheader(f":material/playlist_play: Ready for Bulk Cross-Post ({len(batch_items)} Videos)")

        c_bcat, c_bpriv = st.columns(2)
        with c_bcat:
            batch_cat = st.selectbox(
                "Default Category",
                options=list(YOUTUBE_CATEGORIES.keys()),
                format_func=lambda x: f"{YOUTUBE_CATEGORIES[x]}",
                index=0,
                key="batch_cat",
            )
        with c_bpriv:
            batch_priv = st.selectbox(
                "Default Privacy",
                options=["Public", "Unlisted", "Private"],
                index=0,
                key="batch_priv",
            )

        for idx, item in enumerate(batch_items):
            with st.expander(f"#{idx + 1}: {item['title']}", expanded=False):
                item["title"] = st.text_input(f"Title #{idx + 1}", value=item["title"], key=f"btitle_{idx}")
                item["description"] = st.text_area(f"Description #{idx + 1}", value=item["description"], key=f"bdesc_{idx}")

        can_publish = st.session_state.yt_auth_token is not None
        bulk_publish_clicked = st.button(
            f"🚀 Bulk Cross-Post All {len(batch_items)} to YouTube",
            type="primary",
            icon=":material/rocket_launch:",
            disabled=not can_publish or st.session_state.is_publishing,
        )

        if bulk_publish_clicked:
            st.session_state.is_publishing = True
            creds = get_credentials_from_dict(st.session_state.yt_auth_token)
            pub_bar = st.progress(0, text="Publishing to YouTube...")

            for i, item in enumerate(batch_items):
                pub_bar.progress(int((i / len(batch_items)) * 100), text=f"Publishing ({i + 1}/{len(batch_items)}): {item['title'][:30]}...")
                ok, msg, vid_id = upload_to_youtube(
                    creds=creds,
                    file_path=item["video_path"],
                    title=item["title"],
                    description=item["description"],
                    tags=item["hashtags"],
                    category_id=batch_cat,
                    privacy_status=batch_priv,
                )
                st.session_state.published_results[item["url"]] = {"ok": ok, "msg": msg, "id": vid_id}

            pub_bar.progress(100, text="Bulk cross-posting complete!")
            st.session_state.is_publishing = False

            st.success("Batch publishing finished! Results:")
            for u, res in st.session_state.published_results.items():
                if res["ok"]:
                    st.markdown(f"✅ Published: [https://youtu.be/{res['id']}](https://youtu.be/{res['id']})")
                else:
                    st.markdown(f"❌ Failed ({u}): {res['msg']}")

st.divider()
st.caption(":material/info: Content is uploaded directly to your connected YouTube channel via YouTube Data API v3.")
