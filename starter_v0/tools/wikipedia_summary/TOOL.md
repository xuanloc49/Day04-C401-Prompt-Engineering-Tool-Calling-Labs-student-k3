---
name: wikipedia_summary
track: bonus
kind: live_api
provider: Wikipedia
requires_env: []
inputs: [query, language]
outputs: [title, summary, url]
side_effect: false
---
# wikipedia_summary

Fetches a quick definition, page title, summary, and URL from Wikipedia REST API based on the query.
Supports language choice (`vi` or `en`). Useful for answering basic entity definition questions.
