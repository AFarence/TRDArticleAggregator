import streamlit as st
import json

# Load the JSON data.
def load_articles():
    try:
        with open("trd_articles.json", "r", encoding="utf-8") as f:
            articles = json.load(f)
            # Sort articles by pub_date_dt in descending order
            articles.sort(key=lambda x: x.get("pub_date_dt", ""), reverse=True)
            return articles
    except Exception:
        return []

articles = load_articles()

st.title("TRD Real Estate Articles")

# Get unique markets.
markets = sorted({article.get("market") or "Unknown" for article in articles})
selected_market = st.selectbox("Select a Market", ["All"] + markets)

# Filter articles by market if selected.
if selected_market != "All":
    filtered = [a for a in articles if a.get("market") == selected_market]
else:
    filtered = articles

if st.button("Refresh Data"):
    st.rerun()

st.write(f"Found {len(filtered)} articles")
st.json(filtered)
