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
