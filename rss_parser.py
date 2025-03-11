import feedparser
import json
import os
import requests
from email.utils import parsedate_to_datetime
from bs4 import BeautifulSoup
import bleach
from urllib.parse import urljoin
from datetime import datetime

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

def parse_article(url):
    """
    Fetches the article page at `url`, extracts and cleans:
      - Title, subhead, authors, publication date, and full article content.
    Unwanted HTML elements (like divs, buttons, figures, figcaptions, and anchor tags) are removed.
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
    
    pub_date_str = get_pub_date(soup)
    pub_date_dt = None
    if pub_date_str:
        try:
            pub_date_dt = datetime.strptime(pub_date_str, '%b %d, %Y, %I:%M %p')
        except Exception as e:
            print(f"Date conversion error for {url}: {e}")
    
    # Locate the main article content.
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
            # Replace the anchor tag with its inner text so the text remains.
            a.replace_with(a.get_text())

        # Extract plain text with newlines between blocks.
        content = article_tag.get_text(separator="\n", strip=True)
    # Clean any stray HTML.
    clean_text = bleach.clean(content, tags=[], strip=True)

    # Remove specific unwanted text fragments.
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

def main():
    # Define RSS feeds with market names.
    feeds = {
        "New York": "https://therealdeal.com/new-york/feed/",
        "South Florida": "https://therealdeal.com/miami/feed/",
        "Los Angeles": "https://therealdeal.com/la/feed/",
        "Chicago": "https://therealdeal.com/chicago/feed/",
        "Texas": "https://therealdeal.com/texas/feed/",
        "San Francisco": "https://therealdeal.com/san-francisco/feed/",
        "National": "https://therealdeal.com/national/feed/",
    }

    output_file = "articles_from_rss.json"
    articles_dict = {}

    # Load existing articles to avoid duplicates.
    if os.path.exists(output_file):
        with open(output_file, "r", encoding="utf-8") as f:
            try:
                existing_articles = json.load(f)
                for article in existing_articles:
                    link = article.get("link")
                    if link:
                        articles_dict[link] = article
            except json.JSONDecodeError:
                articles_dict = {}

    # Process each RSS feed.
    for market, feed_url in feeds.items():
        feed = feedparser.parse(feed_url)
        for entry in feed.entries:
            link = entry.get("link", "")
            if not link or link in articles_dict:
                continue

            published_str = entry.get("pubDate", entry.get("published", ""))
            try:
                published_dt = parsedate_to_datetime(published_str)
            except Exception:
                published_dt = None

            # Fetch full article content by parsing the article page.
            article_data = parse_article(link)
            # If no full content could be retrieved, fall back to the summary from the RSS.
            if not article_data.get("content"):
                article_data["content"] = entry.get("summary", "")

            article_data["market"] = market
            article_data["published"] = published_str
            article_data["published_dt"] = published_dt.isoformat() if published_dt else ""
            # Use the "author" key from the feed if available.
            article_data["author"] = entry.get("author", "Unknown")
            articles_dict[link] = article_data

    articles = list(articles_dict.values())
    # Sort by publication date (most recent first).
    articles.sort(
        key=lambda a: parsedate_to_datetime(a["published"]) if a["published"] else datetime.min,
        reverse=True
    )

    # Save the merged articles to JSON.
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(articles, f, indent=2, ensure_ascii=False)

    print(f"Articles extracted and merged saved to {output_file}")

if __name__ == "__main__":
    main()
