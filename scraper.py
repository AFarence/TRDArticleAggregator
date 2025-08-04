import feedparser
import json
import os
import re
import requests
from email.utils import parsedate_to_datetime
from bs4 import BeautifulSoup
import bleach
from urllib.parse import urljoin, urlparse
from datetime import datetime, timedelta

url_list = [
    "https://therealdeal.com/new-york/",
    "https://therealdeal.com/miami/",
    "https://therealdeal.com/la/",
    "https://therealdeal.com/chicago/",
    "https://therealdeal.com/san-francisco/",
    "https://therealdeal.com/texas/"
]

from urllib.parse import urlparse

def get_market_from_url(url):
    mapping = {
        "new-york": "New York",
        "miami": "South Florida",
        "la": "Los Angeles",
        "chicago": "Chicago",
        "san-francisco": "San Francisco",
        "texas": "Texas",
        "data": "Data",  # Now 'data' is considered a separate market.
        "weekend": "Weekend"  # Added 'weekend' as a separate market.
    }
    parsed = urlparse(url)
    parts = parsed.path.lstrip('/').split('/')
    if parts:
        market_slug = parts[0].lower()
        return mapping.get(market_slug, None)
    return None


# Prepend the domain to URIs that start with "/"
def extract_post_fields(post):
    original_uri = post.get('uri', '')
    full_url = "www.therealdeal.com" + original_uri if original_uri.startswith("/") else original_uri
    return {
        'title': post.get('title'),
        'url': full_url,
        'date': post.get('date')
    }

def fetch_and_extract(url, session):
    try:
        response = session.get(url)
        response.raise_for_status()  # Raise exception for HTTP errors
    except requests.RequestException as e:
        print(f"Error fetching {url}: {e}")
        return []
    
    soup = BeautifulSoup(response.content, 'html.parser')
    script_tag = soup.find("script", {"type": "application/json"})
    if not (script_tag and script_tag.string):
        print(f"No JSON found in {url}")
        return []
    
    try:
        json_text = script_tag.string.strip()
        data = json.loads(json_text)
    except json.JSONDecodeError as e:
        print(f"JSON decode error in {url}: {e}")
        return []
    
    # Navigate through the JSON structure
    editorial_posts = data.get('props', {}) \
                           .get('pageProps', {}) \
                           .get('data', {}) \
                           .get('editorialPickPosts', [])
    regular_posts = data.get('props', {}) \
                        .get('pageProps', {}) \
                        .get('data', {}) \
                        .get('posts', {}) \
                        .get('nodes', [])
    
    # Extract fields from both lists
    extracted_editorial = [extract_post_fields(post) for post in editorial_posts]
    extracted_regular = [extract_post_fields(post) for post in regular_posts]
    
    return extracted_editorial + extracted_regular

# Assuming url_list is defined
combined_posts_list = []

with requests.Session() as session:
    for url in url_list:
        posts = fetch_and_extract(url, session)
        # If you prefer a flat list (all posts in one list) rather than a list per URL:
        combined_posts_list.extend(posts)
        # Otherwise, if you want to keep the posts per URL:
        # combined_posts_list.append(posts)


def get_pub_date(soup):
    """
    Returns a cleaned publication date string from known container classes.
    Checks for an updated date if present.
    """
    pub_div = soup.find('div', class_='PublishedDate_root__Rn_Fz RightRailCommon_publishedDate__FW5gI')
    if pub_div:
        updated_span = pub_div.find('span', class_='updated')
        if updated_span:
            return updated_span.get_text().replace("Updated", "").strip()
        first_span = pub_div.find('span')
        if first_span:
            return first_span.get_text().strip()
    # Fallback: check for full-width published date.
    pub_div = soup.find('div', class_='PublishedDate_root__Rn_Fz FullWidthCommon_publishedDate__Ba6lp')
    if pub_div:
        return pub_div.get_text().strip()
    return None

# Your parse_article function (as defined)
def parse_article(url):
    """
    Fetches the article page at `url`, extracts and cleans:
      - Title, subhead, authors, publication date, and full article content.
    Unwanted HTML elements are removed.
    """
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return {}
    
    soup = BeautifulSoup(response.content, 'html.parser')
    
    title_tag = soup.find('h1', class_='Heading_root__aznJy')
    title = title_tag.get_text(strip=True) if title_tag else ""
    
    subhead_tag = soup.find('p', class_='Subheading_root__MWlO8')
    subhead = subhead_tag.get_text(strip=True) if subhead_tag else ""
    
    authors_tag = soup.find('section', class_='Authors_root__depgJ')
    authors = authors_tag.get_text(strip=True) if authors_tag else ""
    # Ensures that 'ByAuthor Name' becomes 'By Author Name'
    authors = re.sub(r"^By(?=\S)", "By ", authors)

    
    # Assuming you have a helper function get_pub_date() defined elsewhere:
    pub_date_str = get_pub_date(soup)
    pub_date_dt = None
    if pub_date_str:
        cleaned = re.sub(r'\s+UTC$', '', pub_date_str)
    try:
        pub_date_dt = datetime.strptime(cleaned, '%b %d, %Y, %I:%M %p')
    except Exception as e:
        print(f"Date conversion error for {url}: {e}")
    
    article_tag = soup.find('article', id='the-content')
    related_links = []  # To capture any links from the article.
    content = ""
    if article_tag:
        # Remove unwanted elements.
        for tag in article_tag.find_all(["div", "button", "figure", "figcaption"]):
            tag.decompose()
        # Extract and remove all anchor tags, storing their absolute URLs.
        for a in article_tag.find_all('a'):
            href = a.get('href')
            if href:
                related_links.append(urljoin("https://therealdeal.com", href))
            a.replace_with(a.get_text())
        content = article_tag.get_text(separator="\n", strip=True)
    
    clean_text = bleach.clean(content, tags=[], strip=True)
    for unwanted in ["Sign Up for the undefined Newsletter", "Read more"]:
        clean_text = clean_text.replace(unwanted, "")
    
    return {
        "url": url,
        "title": title,
        "subhead": subhead,
        "authors": authors,
        "pub_date": pub_date_str,
        "pub_date_dt": pub_date_dt.isoformat() if pub_date_dt else "",
        "content": clean_text,
        "related_links": related_links,
    }

final_articles = []

for post in combined_posts_list:
    # Ensure the URL is fully qualified.
    url = post.get("url", "")
    if not url.startswith("http"):
        url = "https://" + url
    
    # Fetch additional article details.
    article_details = parse_article(url)
    
    # Merge JSON data and article details.
    merged = {**post, **article_details}
    
    # Add the market by extracting it from the URL.
    merged["market"] = get_market_from_url(url)
    
    final_articles.append(merged)

# final_articles now contains the combined data for each URL.

output_file = 'trd_articles.json'

# Load existing articles if the file exists, otherwise start with an empty list.
if os.path.exists(output_file):
    with open(output_file, 'r') as f:
        try:
            existing_articles = json.load(f)
        except json.JSONDecodeError:
            existing_articles = []
else:
    existing_articles = []

# Assume final_articles is your list of newly scraped articles.
# First, create a set of normalized URLs from the existing articles.
def normalize_url(url):
    # Remove protocol and trailing slashes for consistency (or adjust as needed)
    return url.rstrip('/')

existing_urls = {normalize_url(article['url']) for article in existing_articles}

# Filter new articles: only add those whose normalized URL is not already present.
new_articles = [article for article in final_articles if normalize_url(article['url']) not in existing_urls]

# Combine the articles (existing and new)
combined_articles = existing_articles + new_articles

# Deduplicate in case there are any duplicates within the combined list.
# Using a dictionary keyed by the normalized URL ensures only one instance per URL.
unique_articles_dict = {}
for article in combined_articles:
    norm_url = normalize_url(article['url'])
    unique_articles_dict[norm_url] = article

# Convert the deduplicated dictionary back into a list.
final_unique_articles = list(unique_articles_dict.values())

# ─── only keep stories from the last 7 days ───
one_week_ago = datetime.now() - timedelta(days=7)

final_unique_articles = [
    article
    for article in final_unique_articles
    # article['pub_date_dt'] is an ISO string—convert it back to datetime
    if article.get('pub_date_dt')
       and datetime.fromisoformat(article['pub_date_dt']) >= one_week_ago
]

with open(output_file, 'w') as f:
    json.dump(final_unique_articles, f, indent=4)

print(f"Added {len(new_articles)} new articles. Total articles stored: {len(final_unique_articles)}.")