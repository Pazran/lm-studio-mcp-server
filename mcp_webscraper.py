# -------------------------------
# Web Search via SearXNG
# -------------------------------
from mcp.server.fastmcp import FastMCP
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone

server = FastMCP("Web Browser MCP Server") # use your existing FastMCP server instance
SEARX_URL = "http://localhost:8080/search"

# ----------------------------------------------------------
# 1. Long Web Search Tool
# ----------------------------------------------------------
@server.tool()
def search_web(
    query: str,
    detail_level: str = "brief",
    max_results: int = 5,
    lang: str = "en",
) -> list:
    """
    Search the web for a query.

    Params:
    - query (str): search keywords
    - detail_level (str): "brief" (default) or "full"
    - max_results (int): number of results
    - lang (str): language code, e.g., "en", "zh", "ms"

    Returns: list of search results with extracted text.
    """
    params = {
        "q": query,
        "format": "json",
        "count": max_results,
        "engines": "google,bing,duckduckgo",
        "language": lang
    }

    max_char = 5000 if detail_level == "full" else 500
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        res = requests.get(SEARX_URL, params=params, headers=headers)
        res.raise_for_status()
        data = res.json()
    except Exception as e:
        return [{"error": f"SearXNG error: {str(e)}"}]

    output = []
    for item in data.get("results", [])[:max_results]:
        url = item.get("url", "")
        title = item.get("title", "")
        snippet = item.get("content", "")
        long_text = ""

        if url: #detail_level == "full" and
            try:
                page = requests.get(url, timeout=8, headers=headers)
                soup = BeautifulSoup(page.text, "html.parser")
                for tag in soup(["script", "style", "nav", "header", "footer", "svg"]):
                    tag.decompose()
                text = soup.get_text(separator=" ", strip=True)
                long_text = " ".join(text.split())[:max_char]
            except Exception:
                pass

        output.append({
            "title": title,
            "url": url,
            "snippet": snippet,
            "long_text": long_text
        })

    return output

@server.tool()
def current_time() -> str:
    """Return current UTC datetime in ISO format"""
    return datetime.now(timezone.utc).isoformat()

# -------------------------------
# Run MCP server
# -------------------------------
if __name__ == "__main__":
    server.run()