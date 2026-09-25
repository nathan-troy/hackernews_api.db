import hashlib
import requests
from datetime import datetime, timezone
from urllib.parse import urlparse

BASE_URL = "https://hacker-news.firebaseio.com/v0"

def get_top_story_ids(limit):
    url = f"{BASE_URL}/topstories.json"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        story_ids = response.json()
        return story_ids[:limit]
    except requests.exceptions.RequestException as e:
        print(f"Error fetching top stories: {e}")
        return []

def get_item_details(item_id):
    url = f"{BASE_URL}/item/{item_id}.json"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching item {item_id}: {e}")
        return None

def extract_domain_info(raw_url):
    if not raw_url:
        return None

    parsed_url = urlparse(raw_url)
    domain_name = parsed_url.netloc.lower()

    if domain_name.startswith("www."):
        domain_name = domain_name[4:]

    tld = f".{domain_name.split('.')[-1]}" if '.' in domain_name else "unknown"

    domain_hash = hashlib.sha256(domain_name.encode('utf-8')).hexdigest()

    return {
        "domain_name": domain_name,
        "tld": tld,
        "domain_hash": domain_hash
    }

def main():
    story_ids = get_top_story_ids(limit=10)
    print(f"Found {len(story_ids)} top stories to process.\n")

    for idx, story_id in enumerate(story_ids, start=1):
        print(f"[{idx}/10] Processing item ID: {story_id}")
        item_data = get_item_details(story_id)

        if not item_data:
            continue

        author = item_data.get("by")
        title = item_data.get("title")
        item_type = item_data.get("type")
        score = item_data.get("score", 0)
        descendants = item_data.get("descendants", 0)

        unix_time = item_data.get("time")
        posted_at = datetime.fromtimestamp(unix_time, tz=timezone.utc) if unix_time else None

        raw_url = item_data.get("url")

        print(f"Title: {title}")
        print(f"Author: {author}")
        print(f"Score: {score}")
        print(f"Posted At (UTC): {posted_at}")

        if raw_url:
            domain_info = extract_domain_info(raw_url)
            print(f"External Link: {raw_url}")
            print(f"Domain: {domain_info['domain_name']} ({domain_info['tld']})")
        else:
            print("No external link found")

        print("-" * 50)

if __name__ == "__main__":
    main()
