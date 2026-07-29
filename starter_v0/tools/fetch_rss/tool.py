from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any

import requests

from tools._shared import TIMEOUT, err


def read_rss(feed_url: str = "", limit: int = 5) -> dict[str, Any]:
    """Fetches and parses articles from a given RSS feed URL.
    
    Args:
        feed_url: The URL of the RSS feed.
        limit: Maximum number of articles to return.
        
    Returns:
        A dict containing status and the list of items parsed.
    """
    try:
        if not feed_url:
            raise ValueError("Feed URL cannot be empty")
            
        headers = {
            "User-Agent": "ResearchAgent/1.0 (academic/student lab project)"
        }
        
        response = requests.get(feed_url, headers=headers, timeout=TIMEOUT)
        response.raise_for_status()
        
        # Parse XML content
        root = ET.fromstring(response.content)
        
        # RSS usually has channel -> item list
        items = []
        # Support both RSS and Atom namespace tags if needed
        # Standard RSS uses channel/item
        channel = root.find("channel")
        xml_items = channel.findall("item") if channel is not None else root.findall(".//{*}entry")
        
        if not xml_items:
            # Try finding item elements globally without channel prefix
            xml_items = root.findall(".//item")
            
        for idx, item in enumerate(xml_items):
            if idx >= int(limit or 5):
                break
                
            # Extract elements with safety fallbacks
            def get_text(tag_name: str) -> str:
                el = item.find(tag_name)
                if el is not None:
                    return el.text or ""
                # Try finding with any namespace wildcard (for Atom feeds)
                el_wildcard = item.find(f".//{{*}}{tag_name}")
                if el_wildcard is not None:
                    return el_wildcard.text or ""
                return ""
            
            title = get_text("title")
            link = get_text("link")
            
            # Atom feeds often use <link href="..."/> instead of text content
            if not link:
                el_link = item.find(".//{*}link")
                if el_link is not None:
                    link = el_link.attrib.get("href", "")
                    
            summary = get_text("description") or get_text("summary") or get_text("content")
            published = get_text("pubDate") or get_text("published") or get_text("updated")
            
            # Clean summary from CDATA or basic HTML if necessary (keep it simple for now)
            # Just extract title, link, summary, published
            items.append({
                "title": title.strip() if title else "",
                "url": link.strip() if link else "",
                "summary": summary.strip() if summary else "",
                "published": published.strip() if published else "",
            })
            
        return {
            "tool": "fetch_rss",
            "feed_url": feed_url,
            "items": items
        }
    except Exception as exc:
        return err("fetch_rss", exc)
