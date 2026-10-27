"""The Alignment Squeeze -- an interactive model of why agents start cheating.

Run with:  streamlit run streamlit_app.py
"""

import streamlit as st

st.set_page_config(
    page_title="The alignment squeeze",
    page_icon=":material/balance:",
    layout="wide",
    initial_sidebar_state="expanded",
)

pages = [
    st.Page("app_pages/simulate.py", title="Watch it happen",
            icon=":material/play_circle:", default=True),
    st.Page("app_pages/mechanism.py", title="Why it happens",
            icon=":material/functions:"),
    st.Page("app_pages/solutions.py", title="Solutions lab",
            icon=":material/shield:"),
    st.Page("app_pages/landscape.py", title="Where the failure lives",
            icon=":material/grid_view:"),
    st.Page("app_pages/about.py", title="Model & limitations",
            icon=":material/info:"),
]

st.navigation(pages).run()
