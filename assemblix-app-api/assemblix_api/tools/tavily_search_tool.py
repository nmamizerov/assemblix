# /tools/tavily_search_tool.py

from typing import Any

import httpx

from assemblix_api.tools import BaseTool, ToolParameter
from assemblix_api.tools.registry import ToolContext, register_tool


class TavilySearchTool(BaseTool):
    """
    Web search tool using Tavily Search API.

    Tavily is optimized for AI agents:
    - Returns concise, relevant results
    - No ads or spam
    - Fast response times
    - Designed for RAG and agent use cases

    Get API key: https://tavily.com (free tier available)
    """

    def __init__(self, api_key: str | None = None):
        """
        Initialize Tavily search tool.

        Args:
            api_key: Tavily API key (from https://tavily.com)
        """
        self.api_key = api_key
        self.api_url = "https://api.tavily.com/search"

    @property
    def name(self) -> str:
        return "web_search"

    @property
    def description(self) -> str:
        return (
            "Search the internet for current information, news, facts, or data. "
            "Use this when you need up-to-date information that's not in your training data. "
            "Best for: current events, weather, prices, statistics, recent developments."
        )

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="query",
                type="string",
                description="Search query. Be specific and use relevant keywords for best results.",
                required=True,
            ),
            ToolParameter(
                name="max_results",
                type="number",
                description="Maximum number of results to return (1-10). Default is 5.",
                required=False,
            ),
        ]

    async def execute(self, query: str, max_results: int = 5) -> Any:  # type: ignore[override]  # tool-specific named params; base accepts **kwargs
        """
        Execute web search via Tavily API.

        Args:
            query: Search query
            max_results: Number of results to return (1-10)

        Returns:
            Search results with titles, snippets, and URLs

        Raises:
            RuntimeError: If search fails or API key is missing
        """
        if not self.api_key:
            return {
                "error": "Tavily API key not configured",
                "message": "Please set TAVILY_API_KEY in environment or credentials",
                "query": query,
            }
        # Validate max_results
        max_results = max(1, min(10, int(max_results)))

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.api_url,
                    json={
                        "api_key": self.api_key,
                        "query": query,
                        "max_results": max_results,
                        "search_depth": "basic",  # "basic" or "advanced"
                        "include_answer": True,  # Include AI-generated answer
                        "include_raw_content": False,  # Don't include full page content
                    },
                    timeout=30.0,
                )

                if response.status_code != 200:
                    return {
                        "error": f"Tavily API error: {response.status_code}",
                        "message": response.text,
                        "query": query,
                    }

                data = response.json()

                # Format results for LLM
                results = []
                for item in data.get("results", []):
                    results.append(
                        {
                            "title": item.get("title", ""),
                            "url": item.get("url", ""),
                            "content": item.get("content", ""),
                            "score": item.get("score", 0.0),
                        }
                    )

                return {
                    "query": query,
                    "answer": data.get("answer", ""),  # AI-generated summary
                    "results": results,
                    "total_results": len(results),
                }

        except httpx.TimeoutException:
            return {
                "error": "Search timeout",
                "message": "Tavily API request timed out after 30 seconds",
                "query": query,
            }
        except Exception as e:
            return {
                "error": "Search failed",
                "message": str(e),
                "query": query,
            }


@register_tool("web_search")
def _build_tavily(ctx: ToolContext) -> TavilySearchTool:
    """web_search factory: the Tavily key is taken from settings."""
    return TavilySearchTool(api_key=ctx.settings.tavily_api_key)
