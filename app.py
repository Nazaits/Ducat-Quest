# app.py
import streamlit as st
import logic
import db
import ssl

# def no_windows_certs(*args, **kwargs):
#     pass

# if hasattr(ssl.SSLContext, '_load_windows_store_certs'):
#     ssl.SSLContext._load_windows_store_certs = no_windows_certs

st.set_page_config(page_title="Ducat Quest", layout="wide")
def main():
    db.init_db()
    st.title("Ducat Quest - AI Gamified Todo Tracker")
    st.sidebar.success("Use the page menu for navigation.")
    st.write(
        """
        Welcome to Ducat Quest! Earn ducats for tasks, spend them in your custom shop, and let AI do the boring parts.
        """
    )
    logic.show_ducat_bar()

if __name__ == "__main__":
    main()
