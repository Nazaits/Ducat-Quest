import streamlit as st
import os
import db
from utils.util import( 
    rotate_shop, extract_image_from_url, add_shop_item, 
    show_ducat_bar, show_timers, smart_ducat_str, 
    buy_shop_item
)
from datetime import datetime, timedelta

ASSET_DIR = "assets"
os.makedirs(ASSET_DIR, exist_ok=True)

def rotate_shop_if_needed():
    now = datetime.now()
    last_rot = db.query("SELECT value FROM user_stats WHERE key='last_shop_rotation'")[0][0]
    last_rot_dt = datetime.fromisoformat(last_rot)
    # Find most recent Monday 12pm
    most_recent_monday = (now - timedelta(days=now.weekday())).replace(hour=12, minute=0, second=0, microsecond=0)
    if now >= most_recent_monday and last_rot_dt < most_recent_monday:
        rotate_shop()
        db.query("UPDATE user_stats SET value=? WHERE key='last_shop_rotation'", (now.isoformat(),), commit=True)

st.header("🏆 Shop & Rewards")

# --- Add new item
with st.expander("➕ Add a Reward Item"):
    link = st.text_input("Product Link (or image URL, optional)")
    value = st.number_input("Price ($)", min_value=0.0, step=1.0)
    uploaded_img = st.file_uploader("Or upload screenshot/image", type=["png", "jpg", "jpeg"])
    image_path = ""
    image_url = ""
    if not uploaded_img and link:
        # Try to extract image from link
        image_url = extract_image_from_url(link)
    if uploaded_img is not None:
        # Make a unique filename with timestamp to avoid overwrites
        save_name = f"{uploaded_img.name}"
        image_path = os.path.join(ASSET_DIR, save_name)
        with open(image_path, "wb") as f:
            f.write(uploaded_img.read())
    elif image_url:
        image_path = image_url  # If it's a URL, just use it directly in DB and display
    # --- Add to *current* rotation with ducat premium ---
    instant = st.checkbox("Add to this week's rotation instantly", value=False)
    if instant:
        st.error(
            ":warning: **This service will make the item cost 20% more!**\n\n"
            "Use this only for special rewards you want to earn *right now* — but it will cost you more ducats."
        )

    if st.button("Add to Shop"):
        add_shop_item(link, value, image_path, instant_rotation=instant, ducat_premium=0.20 if instant else 0)
        if instant:
            st.success("Reward added instantly to this week's shop (with a 20% ducat premium)!")
        else:
            st.success("Reward added to shop.")
        st.rerun()

rotate_shop_if_needed()
show_ducat_bar()
show_timers(page="shop")
# --- Shop rotation grids
st.subheader("🎲 This Week's Shop Rotation")
rotation = db.query(
    "SELECT id, name, description, ducat_value, bought, link, image FROM shop_items WHERE in_rotation=1 ORDER BY added_at"
)
if not rotation:
    st.info("No rewards in the current rotation.")
else:
    SHOP_COLS = 4

    # --- Pad the list so the grid is always even
    rotation_items = list(rotation)
    remainder = len(rotation_items) % SHOP_COLS
    if remainder:
        rotation_items += [None] * (SHOP_COLS - remainder)

    # --- Display items in a grid, keeping the grid full
    for i in range(0, len(rotation_items), SHOP_COLS):
        row = rotation_items[i:i+SHOP_COLS]
        cols = st.columns(SHOP_COLS)
        for col, item in zip(cols, row):
            if item is not None:
                rid, name, desc, ducats, bought, link, image = item
                # Your usual item rendering code goes here:
                # (image, name, desc, price, buy button, etc.)
                if image:
                    col.image(image, use_container_width=True)
                else:
                    col.image("assets/placeholder.png", use_container_width=True)
                col.markdown(f"**{name}**")
                col.markdown(f"**{smart_ducat_str(ducats)} 💰**")
                if bought:
                    col.success("Already bought")
                else:
                    if col.button(f"Buy", key=f"buy_{rid}"):
                        success = buy_shop_item(rid, ducats)
                        if success:
                            st.success(f"You bought '{name}'!")
                            st.rerun()
                        else:
                            st.error("Not enough ducats to buy this reward!")
            else:
                # Empty cell for grid alignment
                col.markdown("")


# --- Purchase history
st.subheader("🛒 Purchase History")
purchased = db.query(
    "SELECT name, description, ducat_value, added_at, image FROM shop_items WHERE bought=1 ORDER BY added_at DESC"
)
if not purchased:
    st.info("No purchases yet!")
else:
    for name, desc, ducats, added, image in purchased:
        col1, col2 = st.columns([5, 5])
        with col2:
            if image:
                st.image(image, width=100)
            else:
                st.image("assets/placeholder.png", width=100)
        with col1:
            st.write(f"- **{name}** ({smart_ducat_str(ducats)} 💰, added {added[:10]})")
        # st.markdown(desc)
