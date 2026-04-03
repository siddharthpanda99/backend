import os
import sys
import json
from dotenv import load_dotenv

# Ensure common_lib is in the path
sys.path.append(os.path.join(os.getcwd(), "..", "Python Libs", "common_lib", "src"))

from common_lib.modules.web import YouTubeResearcher, SocialSearcher, SiteCrawler, ArchiveHelper, WebSearchManager

def test_youtube():
    print("\n--- Testing YouTube Researcher ---")
    researcher = YouTubeResearcher()
    # Using a known public video (TED Talk)
    url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ" # Never gonna give you up
    print(f"Researching video: {url}...")
    try:
        data = researcher.get_research(url)
        print(f"Title: {data.get('title')}")
        print(f"Author: {data.get('author_name')}")
        if "transcript" in data:
            print(f"Transcript Sample: {data['transcript'][:100]}...")
        else:
            print(f"Transcript Error: {data.get('transcript_error')}")
    except Exception as e:
        print(f"YouTube test failed: {e}")

def test_social():
    print("\n--- Testing Social Platform Search ---")
    load_dotenv(os.path.join("..", "Python Libs", "common_lib", ".env"))
    manager = WebSearchManager()
    searcher = SocialSearcher(manager)
    
    platforms = ["reddit", "quora", "medium"]
    query = "best mechanical keyboards 2024"
    
    for p in platforms:
        print(f"Searching {p} for '{query}'...")
        try:
            results = searcher.search(query, p, limit=2)
            for r in results:
                print(f"- {r['title']} ({r['url']})")
        except Exception as e:
            print(f"{p} search failed: {e}")

def test_sitemap():
    print("\n--- Testing Sitemap Discovery ---")
    crawler = SiteCrawler()
    domain = "https://www.google.com"
    print(f"Discovering sitemap for: {domain}...")
    try:
        links = crawler.discover_sitemap(domain)
        print(f"Found {len(links)} links in sitemap.")
        if links:
            print(f"Sample: {links[0]}")
    except Exception as e:
        print(f"Sitemap test failed: {e}")

def test_archive():
    print("\n--- Testing Archive.org Helper ---")
    helper = ArchiveHelper()
    url = "https://www.google.com"
    print(f"Looking up archive for: {url}...")
    try:
        data = helper.get_latest_snapshot(url)
        if data.get("available"):
            print(f"Found snapshot from {data['timestamp']}: {data['url']}")
        else:
            print(f"No snapshot: {data.get('message') or data.get('error')}")
    except Exception as e:
        print(f"Archive test failed: {e}")

if __name__ == "__main__":
    test_youtube()
    test_social()
    test_sitemap()
    test_archive()
