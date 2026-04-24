# BUNQ HACKATHON 7.0 Repository

![GitHub](https://img.shields.io/github/license/user/repo) ![Status](https://img.shields.io/badge/status-active-brightgreen) ![Version](https://img.shields.io/badge/version-1.0-blue)

## Introduction

This repository contains the source code to the backend-related services for bunq's Hackthon 7.0. There are three services available for this backend:

- MCP Client
- MCP Server
- Customized BUNQ API

## Backend flow

There will be three running servers: one to access the BUNQ API (to gather user-related data such as user details, payments, accounts, etc) and another to access the MCP client, which current only holds one POST API endpoint at the url '/query' to submit queries to the MCP client. Lastly, we have the MCP server which holds our tools to be used by the MCP client.

## Developer Tools

This repo uses [just](https://github.com/casey/just) as a task runner. Install it via:

```sh
brew install just
```

Available recipes from the repo root:

```sh
just sync                # uv sync all services including tests
just bunq-init           # generate bunq_api_context.conf (run once)
just bunq-seed           # runs seed_deposits.py to request enough money from sugar daddy to match mockdata
just lint                # ruff check all three services
just format              # ruff format all three services
just fix                 # ruff check --fix + ruff format all three services
just bunq-api            # start the bunq API server (port 8000)
just mcp-client          # start the MCP client as a FastAPI server (port 8001), spawns the MCP server automatically
just mcp-client-terminal # run the MCP client interactively in the terminal, spawns the MCP server automatically
just all                 # start bunq-api and mcp-client concurrently (MCP server spawned automatically)
just test                # run integration tests (requires just all to be running)
```

## Requirements

Ensure that you have uv installed, all of the three services uses uv for project and package management.

Refer to the uv docs to install it: https://docs.astral.sh/uv/getting-started/installation/

## Preliminary Notes

The sections that follow will guide you on how to setup each of these three services. When you start at a new section (like once you've setup the BUNQ API and ready to move on to the MCP Client section), ensure you're at the base project directory, meaning your terminal should show something like this:

```sh
dhafinrz-ubuntu@DESKTOP-O3D42L5:~/projects/bunq-hackathon-7.0$
```

## BUNQ API

The first thing you need to do is to create a bunq API KEY, refer to the bunq API docs: https://doc.bunq.com/basics/authentication/api-keys.

Once you have retrieved the API key, create a .env file at the **project root** with the following variables:

```sh
BUNQ_API_KEY=your_bunq_key
ANTHROPIC_API_KEY=your_anthropic_key
ALPACA_KEY=your_alpaca_paper_trading_key
ALPACA_SECRET=your_alpaca_paper_trading_secret
```

Then, you would need to create an virtual environment by running the following command:

```sh
cd bunq-api
uv sync
source .venv/bin/activate
```

Next, generate the bunq API context file (this only needs to be done once):

```sh
just bunq-init
```

This will create a `bunq_api_context.conf` file in the `bunq-api` directory, which the server needs to authenticate with bunq.

To run the server, ensure your terminal is at the bunq-api directory and run:

```sh
uvicorn src.bunq_api.app:app --reload
```

Now, the server should be running on port 8000. You can verify this by going to the following link in your browser: http://127.0.0.1:8000/users/me

## MCP Client

The Anthropic API key is read from the root .env file created in the BUNQ API section above.

Then, you would need to create an virtual environment by running the following command:

```sh
cd mcp-client
uv sync
source .venv/bin/activate
```

The MCP Client can be run as an API service or within your terminal. The idea was that initially I created the MCP client within the terminal; where I can simply write my prompts in the terminal and the client will return a response. However, I decided to build a frontend as a UI for this hackathon, so that's why I setup the option to access the client via an API.

To run the MCP client as a server, run:

```sh
uv run client.py ../mcp-server/server.py
```

You should see the following output in the terminal, note that the server will be active on port 8001 because port 8000 is reserved for our BUNQ API:

```sh
(mcp-client) dhafinrz-ubuntu@DESKTOP-O3D42L5:~/projects/bunq-hackathon-7.0/mcp-client$ uv run app.py ../mcp-server/server.py
INFO:     Started server process [64179]
INFO:     Waiting for application startup.
Processing request of type ListToolsRequest

Connected to server with tools: ['get_payments', 'create_payment', 'create_request_inquiry', 'send_payment_by_name', 'send_request_inq_by_name', 'get_user_detail', 'get_alpaca_account', 'get_stock_quote', 'place_stock_order', 'get_alpaca_positions', 'get_alpaca_orders', 'get_investment_history']
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8001 (Press CTRL+C to quit)
```

To run the MCP client in the terminal, run:

```sh
uv run client.py ../mcp-server/server.py
```

You should see the following output in the terminal:

```sh
(mcp-client) dhafinrz-ubuntu@DESKTOP-O3D42L5:~/projects/bunq-hackathon-7.0/mcp-client$ uv run client.py ../mcp-server/server.py
Processing request of type ListToolsRequest

Connected to server with tools: ['get_payments', 'create_payment', 'create_request_inquiry', 'send_payment_by_name', 'send_request_inq_by_name', 'get_user_detail', 'get_alpaca_account', 'get_stock_quote', 'place_stock_order', 'get_alpaca_positions', 'get_alpaca_orders', 'get_investment_history']

MCP Client Started!
Type your queries or 'quit' to exit.

Query:
```

## MCP Server

To ensure the MCP server has all the required python packages, run the following:

```sh
cd mcp-server
uv sync
```

The MCP server does not need to be run manually, this is because the MCP client connects to the MCP server when it initializes.

You can also use Claude Desktop to act as an MCP client (instead of the one created in mcp-client). This is nice for testing in case you don't want to run the frontend yourself.

You can do so by following this docs from the official MCP site (refer to the 'Testing your server with Claude for Desktop' section): https://modelcontextprotocol.io/docs/develop/build-server

## Important Notes

The bare minimum service that needs to run is the BUNQ API server, this is because regardless of how you want to run the MCP client (via Claude Desktop, terminal or the client server) the MCP server itself needs to have access to the BUNQ API server. Therefore, please ensure that this BUNQ API server is always running.
