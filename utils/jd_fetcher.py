"""Fetch job description text from a URL.

Supports common Chinese job sites like Boss直聘, 拉勾, 猎聘, etc.
Uses a simple HTTP GET with browser-like headers.
"""
import re

import requests


def fetch_jd_from_url(url: str) -> str:
    """Fetch a job listing page and attempt to extract the JD text.

    Returns the extracted text, or raises an error with a description.
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/130.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
    }

    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        # Try to decode with the detected encoding
        resp.encoding = resp.apparent_encoding or "utf-8"
        html = resp.text
    except requests.RequestException as e:
        raise RuntimeError(f"无法访问该网址: {e}")

    # Remove script and style content
    html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)

    # Remove HTML tags
    text = re.sub(r"<[^>]+>", "\n", html)

    # Decode common HTML entities
    text = text.replace("&nbsp;", " ").replace("&lt;", "<").replace("&gt;", ">")
    text = text.replace("&amp;", "&").replace("&quot;", '"').replace("&#x27;", "'")

    # Collapse whitespace
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()

    if len(text) < 50:
        raise RuntimeError("提取到的文本太短（可能页面需要登录或使用了复杂的渲染方式），请尝试直接粘贴JD文字。")

    return text
