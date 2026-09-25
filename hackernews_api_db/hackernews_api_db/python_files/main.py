import hashlib
import requests
from datetime import datetime, timezone
from urllib.parse import urlparse

from database import initialise_schema, start_pipeline_log, end_pipeline_log, save_pipeline_data

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

import time

def check_link_status(url):
    start_time = time.time()

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Hackernews/1.0'
    }

    try:
        response = requests.head(url, headers=headers, timeout=5, allow_redirects=True)

        latency_ms = int((time.time() - start_time) * 1000)
        status_code = response.status_code

        is_dead = status_code >= 400
        error_type = None

        print(f"Response: HTTP {status_code} received in {latency_ms}ms")

    except requests.exceptions.Timeout:
        latency_ms = int((time.time() - start_time) * 1000)
        status_code = 0
        is_dead = True
        error_type = "TIMEOUT"
        print(f"Network Timeout after {latency_ms}ms")

    except requests.exceptions.ConnectionError:
        latency_ms = int((time.time() - start_time) * 1000)
        status_code = 0
        is_dead = True
        error_type = "DNS_OR_CONNECTION_FAILURE"
        print("Connection Failed (invalid domain or site is completely down)")

    except requests.exceptions.RequestException as e:
        latency_ms = int((time.time() - start_time) * 1000)
        status_code = 0
        is_dead = True
        error_type = f"UNEXPECTED ERROR: {type(e).__name__}"
        print(f"Unexpected Error Encountered: {error_type}")

    return {
        "http_status_code": status_code,
        "response_time_ms": latency_ms,
        "is_dead": is_dead,
        "error_type": error_type
    }

def main():
    initialise_schema()
    
    log_id = start_pipeline_log("hn_web_decay_scanner")
    if not log_id:
        print("Cannot proceed without a valid pipeline log context. Exiting.")
        return

    processed_count = 0
    status = "SUCCESS"
    error_msg = None

    try:
        story_ids = get_top_story_ids(limit=10)
        print(f"Found {len(story_ids)} top stories to process.\n")

        for idx, story_id in enumerate(story_ids, start=1):
            print(f"[{idx}/10] Processing item ID: {story_id}")
            item_data = get_item_details(story_id)

            if not item_data:
                continue

            author = item_data.get("by", "unknown")
            title = item_data.get("title", "Untitled")
            item_type = item_data.get("type", "story")
            score = item_data.get("score", 0)
            descendants = item_data.get("descendants", 0)
            unix_time = item_data.get("time")
            posted_at = datetime.fromtimestamp(unix_time, tz=timezone.utc) if unix_time else datetime.now(timezone.utc)
            raw_url = item_data.get("url")

            print(f"Title: {title}")
            print(f"Author: {author}")
            print(f"Score: {score}")
            print(f"Posted At (UTC): {posted_at}")

            if raw_url:
                domain_info = extract_domain_info(raw_url)
                print(f"External Link: {raw_url}")
                print(f"Domain: {domain_info['domain_name']} ({domain_info['tld']})")
                
                status_info = check_link_status(raw_url)
                
                item_payload = {
                    "item_id": story_id,
                    "author": author,
                    "title": title,
                    "item_type": item_type,
                    "score": score,
                    "descendants": descendants,
                    "posted_at": posted_at,
                    "raw_url": raw_url
                }
                
                save_pipeline_data(item_payload, domain_info, status_info, log_id)
                processed_count += 1
            else:
                print("No external link found")

            print("-" * 50)
            
    except Exception as main_error:
        status = "FAILED"
        error_msg = str(main_error)
        print(f"Pipeline crashed unexpectedly: {main_error}")
        
    finally:
        print(f"\nClosing pipeline log sequence. Status: {status}. Rows processed: {processed_count}")
        end_pipeline_log(log_id, status, processed_count, error_msg)

if __name__ == "__main__":
    main()