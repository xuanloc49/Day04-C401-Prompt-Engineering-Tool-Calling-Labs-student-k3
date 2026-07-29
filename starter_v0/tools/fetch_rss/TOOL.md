---
name: fetch_rss
track: bonus
kind: live_api
provider: Custom
requires_env: []
inputs: [feed_url, limit]
outputs: [feed_url, items]
side_effect: false
---
# fetch_rss

Fetches and parses updates from RSS/Atom web feeds.
Input parameters are `feed_url` and `limit`.
Useful for retrieving structured, raw article/blog feeds from a specific URL.
