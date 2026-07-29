from __future__ import annotations

import urllib.parse
from typing import Any

import requests

from tools._shared import TIMEOUT, err


def wikipedia_summary(query: str = "", language: str = "vi") -> dict[str, Any]:
    """Fetches a quick summary of a topic from Wikipedia using REST API.
    
    Args:
        query: The search query or page title.
        language: Language code of Wikipedia (e.g., 'vi' or 'en').
        
    Returns:
        A dict containing title, summary, url, or error info.
    """
    try:
        if not query:
            raise ValueError("Query cannot be empty")
            
        # Clean and encode the title
        clean_title = query.strip().replace(" ", "_")
        encoded_title = urllib.parse.quote(clean_title)
        
        url = f"https://{language}.wikipedia.org/api/rest_v1/page/summary/{encoded_title}"
        headers = {
            "User-Agent": "ResearchAgent/1.0 (academic/student lab project)"
        }
        
        response = requests.get(url, headers=headers, timeout=TIMEOUT)
        
        if response.status_code == 404:
            raise ValueError(f"Wikipedia page not found for query: '{query}' in language: '{language}'")
            
        response.raise_for_status()
        data = response.json()
        
        title = data.get("title", query)
        summary = data.get("extract", "")
        page_url = data.get("content_urls", {}).get("desktop", {}).get("page", "")
        
        return {
            "tool": "wikipedia_summary",
            "query": query,
            "language": language,
            "title": title,
            "summary": summary,
            "url": page_url
        }
    except Exception as exc:
        return err("wikipedia_summary", exc)
