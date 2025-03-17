import streamlit as st
import json

# Load the JSON data.
# @st.cache_data
def load_articles():
    try:
        with open("articles_from_rss.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

articles = load_articles()

st.title("TRD Real Estate Articles")

# Get unique markets.
markets = sorted({article.get("market", "Unknown") for article in articles})
selected_market = st.selectbox("Select a Market", ["All"] + markets)

# Filter articles by market if selected.
if selected_market != "All":
    filtered = [a for a in articles if a.get("market") == selected_market]
else:
    filtered = articles

st.write(f"Found {len(filtered)} articles")
st.json(filtered)
