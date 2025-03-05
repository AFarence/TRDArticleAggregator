import streamlit as st
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from urllib.parse import urljoin
import bleach
import json
from playwright.sync_api import sync_playwright
import os
import subprocess

# Example path; adjust if needed:
browser_path = "/home/appuser/.cache/ms-playwright/chromium-1024/chrome-linux/chrome"
if not os.path.exists(browser_path):
    subprocess.run(["playwright", "install"], check=True)


# Mapping of market names to their URLs.
market_mapping = {
    "New York": "https://therealdeal.com/new-york/",
    "South Florida": "https://therealdeal.com/miami/",
    "Los Angeles": "https://therealdeal.com/la/",
    "Chicago": "https://therealdeal.com/chicago/",
    "San Francisco": "https://therealdeal.com/san-francisco/",
    "Texas": "https://therealdeal.com/texas/"
}

def get_pub_date(soup):
    """
    Extracts and cleans the publication date string.
    If an updated date exists (inside a <span class="updated">), use that.
    """
    pub_div = soup.find('div', class_='PublishedDate_root__Rn_Fz RightRailCommon_publishedDate__FW5gI')
    if pub_div:
        updated_span = pub_div.find('span', class_='updated')
        if updated_span:
            # Remove the word "Updated" and extra whitespace.
            return updated_span.get_text().replace("Updated", "").strip()
        first_span = pub_div.find('span')
        if first_span:
            return first_span.get_text().strip()
    # Fallback: try the full-width published date.
    pub_div = soup.find('div', class_='PublishedDate_root__Rn_Fz FullWidthCommon_publishedDate__Ba6lp')
    if pub_div:
        return pub_div.get_text().strip()
    return None

def parse_article(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')
    
    # Extract title, subhead, and authors.
    title_tag = soup.find('h1', class_='Heading_root__aznJy')
    title = title_tag.text.strip() if title_tag else None

    subhead_tag = soup.find('p', class_='Subheading_root__MWlO8')
    subhead = subhead_tag.text.strip() if subhead_tag else None

    authors_tag = soup.find('section', class_='Authors_root__depgJ')
    authors = authors_tag.text.strip() if authors_tag else None

    # Use helper to get the publication date string.
    pub_date_str = get_pub_date(soup)
    
    # Convert the publication date string for sorting purposes.
    pub_date_dt = None
    if pub_date_str:
        try:
            pub_date_dt = datetime.strptime(pub_date_str, '%b %d, %Y, %I:%M %p')
        except Exception as e:
            st.error(f"Date conversion error for {url}: {e}")
    
    # Extract the article body.
    article_tag = soup.find('article', id='the-content')
    
    # If the article exists, remove unwanted elements.
    related_links = []
    if article_tag:
        # Remove any <div> elements that are slick slides.
        for slick in article_tag.find_all("div", class_="slick-slide"):
            slick.decompose()
        # Remove entire <button> elements with class "slick-arrow" (e.g., navigation buttons).
        for btn in article_tag.find_all("button", class_="slick-arrow"):
            btn.decompose()
        # Remove <figure> blocks with class "wp-block-image".
        for fig in article_tag.find_all('figure', class_='wp-block-image'):
            fig.decompose()
        # Remove any remaining <figcaption> elements.
        for fc in article_tag.find_all('figcaption', class_='wp-element-caption'):
            fc.decompose()
        # Extract and remove all anchor tags (for related links).
        for a in article_tag.find_all('a'):
            href = a.get('href')
            if href:
                absolute_href = urljoin("https://therealdeal.com", href)
                related_links.append(absolute_href)
            a.decompose()  # Remove the anchor tag from the content.
        html_content = str(article_tag)
    else:
        html_content = ""
    
    # Clean the HTML content (remove any remaining tags).
    clean_html = bleach.clean(html_content, strip=True)
    
    # Remove unwanted text.
    for unwanted in ["Sign Up for the undefined Newsletter", "SIGN UP"]:
        clean_html = clean_html.replace(unwanted, "")
    if "Read more" in clean_html:
        clean_html = clean_html.split("Read more")[0]
    
    article_data = {
        "url": url,
        "title": title,
        "subhead": subhead,
        "authors": authors,
        # Store the original (cleaned) date string.
        "pub_date": pub_date_str,
        "content": clean_html,
        "related_links": related_links,
        # Store ISO-formatted date for internal sorting (will be removed before display).
        "pub_date_dt": pub_date_dt.isoformat() if pub_date_dt else None
    }
    return article_data

def run_scraper(market_url):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        page.goto(market_url)
        page_html = page.content()
        soup = BeautifulSoup(page_html, 'html.parser')
        anchors = soup.find_all('a', class_='BlogrollPost_root__61z1B')
        relative_urls = [a.get('href') for a in anchors if a.get('href')]
        absolute_urls = [urljoin("https://therealdeal.com", rel_url) for rel_url in relative_urls]
        context.close()
        browser.close()
    
    articles = []
    for url in absolute_urls:
        try:
            article_data = parse_article(url)
            articles.append(article_data)
        except Exception as e:
            st.error(f"Error processing {url}: {e}")
    
    # Sort articles by publication datetime (most recent first).
    try:
        articles.sort(
            key=lambda a: datetime.strptime(a["pub_date"], '%b %d, %Y, %I:%M %p') if a["pub_date"] else datetime.min,
            reverse=True
        )
    except Exception as e:
        st.error(f"Sorting error: {e}")
    return articles

# Streamlit UI
st.title("Real Deal Market Scraper")

# Let the user choose a market.
market_choice = st.selectbox("Select a market:", list(market_mapping.keys()))

if st.button("Scrape Articles"):
    market_url = market_mapping[market_choice]
    with st.spinner(f"Scraping articles for {market_choice}..."):
        articles = run_scraper(market_url)
    st.success("Scraping complete!")
    
    # Remove the internal sorting field before displaying.
    for article in articles:
        article.pop("pub_date_dt", None)
    
    # Display the JSON output in a pretty, interactive format.
    st.json(articles)
