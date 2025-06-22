import requests
from bs4 import BeautifulSoup
import json
import asyncio
from mcp.server import Server, NotificationOptions
import mcp.types as types
import inspect
from mcp.server.models import InitializationOptions  
import os
import httpx
from dotenv import load_dotenv

# Initialize MCP server with name "polymarket_predictions"
server = Server("polymarket_predictions")

# Load environment variables
load_dotenv()

# Scraping function for Polymarket homepage
def scrape_polymarket():
    BASE_URL = "https://polymarket.com"
    response = requests.get(BASE_URL)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    script_tag = soup.find("script", id="__NEXT_DATA__")
    data = json.loads(script_tag.string)

    # Navigate to the events data
    events = data["props"]["pageProps"]["dehydratedState"]["queries"][0]["state"]["data"]["pages"][0]["events"]
    results = []
    for event in events[:20]:
        title = event.get("title", "")
        slug = event.get("slug", "")
        url = f"{BASE_URL}/market/{slug}"
        market_info = event.get("markets", [])[0]
        outcomes = market_info.get("outcomes", [])
        prices = market_info.get("outcomePrices", [])
        outcome_probs = [
            {"outcome": outcomes[i], "probability": prices[i]}
            for i in range(min(len(outcomes), len(prices)))
        ]
        results.append({
            "title": title,
            "url": url,
            "outcomes": outcome_probs
        })
    return results

# Add NewsAPI tools to the list_tools endpoint
@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="scrape-polymarket",
            description="Scrape latest prediction markets from Polymarket homepage",
            inputSchema={"type": "object", "properties": {}, "additionalProperties": False},
        ),
        types.Tool(
            name="get-news-headlines",
            description="Get top news headlines using NewsAPI.org",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Keywords or phrase to search for in the news headlines."
                    },
                    "language": {
                        "type": "string",
                        "description": "2-letter ISO-639-1 code of the language you want to get headlines for.",
                        "default": "en"
                    },
                    "pageSize": {
                        "type": "integer",
                        "description": "Number of results to return per page (max 100)",
                        "default": 5,
                        "minimum": 1,
                        "maximum": 100
                    }
                },
                "required": ["query"]
            },
        ),
        types.Tool(
            name="get-news-everything",
            description="Get news articles using NewsAPI.org's everything endpoint (broader search).",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Keywords or phrase to search for in the news articles."
                    },
                    "language": {
                        "type": "string",
                        "description": "2-letter ISO-639-1 code of the language you want to get articles for.",
                        "default": "en"
                    },
                    "pageSize": {
                        "type": "integer",
                        "description": "Number of results to return per page (max 100)",
                        "default": 5,
                        "minimum": 1,
                        "maximum": 100
                    },
                    "from": {
                        "type": "string",
                        "description": "A date and optional time for the oldest article allowed. (YYYY-MM-DD)"
                    },
                    "sortBy": {
                        "type": "string",
                        "description": "The order to sort the articles in. Possible options: relevancy, popularity, publishedAt",
                        "enum": ["relevancy", "popularity", "publishedAt"],
                        "default": "publishedAt"
                    }
                },
                "required": ["query"]
            },
        ),
    ]

# Format NewsAPI headlines

def format_news_headlines(news_data: dict) -> str:
    """Format news headlines from NewsAPI into a readable string."""
    try:
        if not news_data or not isinstance(news_data, dict):
            return "No news data available."
        if news_data.get("status") != "ok":
            return f"NewsAPI error: {news_data.get('message', 'Unknown error')}"
        articles = news_data.get("articles", [])
        if not articles:
            return "No news articles found."
        formatted = ["Top News Headlines:\n"]
        for article in articles:
            formatted.append(
                f"Title: {article.get('title', 'N/A')}\n"
                f"Source: {article.get('source', {}).get('name', 'N/A')}\n"
                f"Published: {article.get('publishedAt', 'N/A')}\n"
                f"URL: {article.get('url', 'N/A')}\n---\n"
            )
        return "\n".join(formatted)
    except Exception as e:
        return f"Error formatting news: {str(e)}"

# Handle tool calls by name
@server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None) -> list[types.TextContent]:
    if name == "scrape-polymarket":
        try:
            results = scrape_polymarket()
            return [types.TextContent(type="text", text=json.dumps(results))]
        except Exception as e:
            return [types.TextContent(type="text", text=f"Error scraping Polymarket: {e}")]
    elif name == "get-news-headlines":
        query = arguments.get("query")
        language = arguments.get("language", "en")
        page_size = arguments.get("pageSize", 5)
        api_key = os.getenv("NEWSAPI_KEY")
        if not api_key:
            return [types.TextContent(type="text", text="Missing NEWSAPI_KEY in environment.")]
        url = "https://newsapi.org/v2/top-headlines"
        params = {"q": query, "language": language, "pageSize": page_size, "apiKey": api_key}
        async with httpx.AsyncClient() as client_http:
            resp = await client_http.get(url, params=params)
            news_data = resp.json()
        formatted_news = format_news_headlines(news_data)
        return [types.TextContent(type="text", text=formatted_news)]
    elif name == "get-news-everything":
        query     = arguments.get("query")
        api_key   = os.getenv("NEWSAPI_KEY")
        sort_by   = arguments.get("sortBy", "popularity")
        page_size = arguments.get("pageSize", 100)
        page      = arguments.get("page", 1)
        params = {
            "q":        query,
            "apiKey":   api_key,
            "sortBy":   sort_by,
            "pageSize": page_size,
            "page":     page,
        }
        if arguments.get("from"):
            params["from"] = arguments["from"]
        if arguments.get("to"):
            params["to"] = arguments["to"]
        async with httpx.AsyncClient() as client_http:
            resp = await client_http.get("https://newsapi.org/v2/everything", params=params)
            news_data = resp.json()
        formatted = format_news_headlines(news_data)
        return [types.TextContent(type="text", text=formatted)]
    return [types.TextContent(type="text", text=f"Unknown tool: {name}")]

async def main():
    # Use stdio transport for MCP communication
    from mcp.server.stdio import stdio_server
    async with stdio_server() as (read_stream, write_stream):
        # Handle both old and new MCP.run signatures
        sig = inspect.signature(server.run)
        params = sig.parameters
        if len(params) == 2:
            # traditional signature: no init options
            await server.run(read_stream, write_stream)
        else:
            # new signature: requires initialization_options object
            init_opts = InitializationOptions(
                server_name="polymarket_predictions",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={}
                )
            )
            await server.run(read_stream, write_stream, init_opts)

if __name__ == "__main__":
    asyncio.run(main())
