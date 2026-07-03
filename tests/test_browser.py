"""The browser tool opens URLs and web searches in the default browser."""

from __future__ import annotations

from kel.system.browser import Browser


def test_open_url_opens_the_given_url() -> None:
    opened: list[str] = []
    browser = Browser(opener=opened.append)

    result = browser.open_url("https://example.com")

    assert opened == ["https://example.com"]
    assert "example.com" in result


def test_web_search_opens_a_search_url() -> None:
    opened: list[str] = []
    browser = Browser(opener=opened.append)

    browser.search("best pizza near me")

    assert opened[0].startswith("https://www.google.com/search?q=")
    assert "pizza" in opened[0]
