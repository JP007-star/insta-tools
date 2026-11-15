import streamlit as st

st.set_page_config(
    page_title="Insta & YouTube Creator Tools",
    page_icon=":material/rocket_launch:",
    layout="centered",
)

pg = st.navigation([
    st.Page("app_pages/instagram.py",       title="Instagram Reel Downloader", icon=":material/photo_camera:"),
    st.Page("app_pages/youtube.py",         title="YouTube Downloader",        icon=":material/play_circle:"),
    st.Page("app_pages/insta_to_youtube.py", title="Insta to YouTube Publisher", icon=":material/cloud_upload:"),
])

pg.run()
