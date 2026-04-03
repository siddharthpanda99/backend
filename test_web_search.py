import os
import sys
import json
from dotenv import load_dotenv

# Ensure common_lib is in the path
sys.path.append(os.path.join(os.getcwd(), "..", "Python Libs", "common_lib", "src"))

from common_lib.modules.web import WebSearchManager, WebExtractor, MetadataInspector

def test_search():
    print("\n--- Testing Web Search Module ---")
    load_dotenv(os.path.join("..", "Python Libs", "common_lib", ".env"))
    
    manager = WebSearchManager()
    
    # 1. Test Tavily (Keyed)
    tavily_key = os.getenv("TAVILY_API_KEY") or os.getenv("TAVILTY_API_KEY")
    if tavily_key:
        print(f"Testing Tavily Search (Key: {tavily_key[:8]}...)...")
        try:
            results = manager.search("NVIDIA stock analysis", provider="tavily", max_results=2)
            for r in results:
                print(f"- {r.title} ({r.url})")
        except Exception as e:
            print(f"Tavily search failed: {e}")
    else:
        print("Skipping Tavily (No key found in .env)")

    # 2. Test DuckDuckGo (Free)
    print("\nTesting DuckDuckGo Search...")
    try:
        results = manager.search("Open source LLM news", provider="ddg", max_results=2)
        for r in results:
            print(f"- {r.title} ({r.url})")
    except Exception as e:
        print(f"DuckDuckGo search failed: {e}")

def test_extraction():
    print("\n--- Testing Web Extraction Module ---")
    extractor = WebExtractor()
    url = "https://en.wikipedia.org/wiki/Web_search_engine"
    
    # 1. Test Trafilatura/Auto
    print(f"\nTesting Auto Extraction (Trafilatura/BS4) on: {url}...")
    try:
        result = extractor.extract(url)
        if result:
            print(f"Title: {result.title}")
            print(f"Content Sample: {result.text[:100]}...")
    except Exception as e:
        print(f"Auto extraction failed: {e}")

    # 2. Test Jina Reader
    print(f"\nTesting Jina Reader Extraction on: {url}...")
    try:
        result = extractor.extract(url, method="jina")
        if result:
            print(f"Markdown Sample: {result.markdown[:200]}...")
        else:
            print("Jina extraction returned no result.")
    except Exception as e:
        print(f"Jina extraction failed: {e}")

def test_metadata():
    print("\n--- Testing Metadata Inspection ---")
    inspector = MetadataInspector()
    url = "https://www.google.com"
    print(f"Inspecting metadata for: {url}...")
    try:
        data = inspector.inspect(url)
        print(f"Title: {data.get('title')}")
        print(f"OG Title: {data.get('opengraph', {}).get('og:title')}")
        print(f"Favicon: {data.get('links', {}).get('favicon')}")
    except Exception as e:
        print(f"Metadata inspection failed: {e}")

if __name__ == "__main__":
    test_search()
    test_extraction()
    test_metadata()
