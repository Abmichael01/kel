"""Open URLs and web searches in the user's default browser."""

from __future__ import annotations

import urllib.parse
import webbrowser
from collections.abc import Callable


class Browser:
    """Open links and searches; the opener is injectable for testing."""

    def __init__(self, *, opener: Callable[[str], object] | None = None) -> None:
        self._opener = opener or webbrowser.open

    def open_url(self, url: str) -> str:
        """Open a URL in the default browser."""
        self._opener(url)
        return f"Opened {url} in the browser."

    def search(self, query: str) -> str:
        """Open a web search for the query."""
        url = "https://www.google.com/search?q=" + urllib.parse.quote_plus(query)
        self._opener(url)
        return f"Opened a search for {query}."
