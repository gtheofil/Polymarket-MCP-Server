# Polymarket-MCP-Server
This project is an MCP server that an autonomous betting agent can use to generate predictions by combining Polymarket market data with real-time news sentiment. 

The agent:

* Scrapes Polymarket for active crypto-related markets and probabilities
* Retrieves relevant news via NewsAPI and summarizes sentiment
* Uses an LLM-based decision module to select one actionable market

To run:
pip install -e .
