import asyncio
import logging
from contextlib import AsyncExitStack
from typing import Optional

from anthropic import Anthropic
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

load_dotenv()  # load environment variables from .env

logger = logging.getLogger(__name__)


class MCPClient:
    def __init__(self, auth_token):
        # Initialize session and client objects
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.anthropic = Anthropic()
        self.conversation_history = []
        self.auth_token = auth_token

    # methods will go here

    async def connect_to_server(self, server_script_path: str):
        """Connect to an MCP server

        Args:
            server_script_path: Path to the server script (.py or .js)
        """
        is_python = server_script_path.endswith(".py")
        is_js = server_script_path.endswith(".js")
        if not (is_python or is_js):
            raise ValueError("Server script must be a .py or .js file")

        command = "python" if is_python else "node"
        server_params = StdioServerParameters(
            command=command, args=[server_script_path], env=None
        )

        stdio_transport = await self.exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        self.stdio, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(
            ClientSession(self.stdio, self.write)
        )

        await self.session.initialize()

        # List available tools
        response = await self.session.list_tools()
        tools = response.tools
        logger.info("Connected to server with tools: %s", [tool.name for tool in tools])

    async def process_query(self, query: str) -> str:
        logger.info('Processing query: "%s"', query)
        self.conversation_history.append({"role": "user", "content": query})

        response = await self.session.list_tools()
        available_tools = [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.inputSchema,
            }
            for tool in response.tools
        ]

        response = self.anthropic.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            messages=self.conversation_history,
            tools=available_tools,
        )

        final_text = []

        # Keep calling tools until Claude returns a stop_reason of "end_turn"
        while response.stop_reason == "tool_use":
            assistant_message_content = list(response.content)

            # Collect all tool results for this round before the next API call
            tool_results = []
            for content in response.content:
                if content.type == "text":
                    final_text.append(content.text)
                elif content.type == "tool_use":
                    logger.info("Calling tool %s with args %s", content.name, content.input)
                    print(123123123)
                    tool_input = {**content.input, "auth_token": self.auth_token}
                    result = await self.session.call_tool(content.name, tool_input)
                    logger.info("Tool %s returned successfully", content.name)
                    final_text.append(f"[Calling tool {content.name} with args {content.input}]")
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": content.id,
                        "content": result.content,
                    })

            self.conversation_history.append({"role": "assistant", "content": assistant_message_content})
            self.conversation_history.append({"role": "user", "content": tool_results})

            response = self.anthropic.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=4096,
                messages=self.conversation_history,
                tools=available_tools,
            )

        # Final text response
        for content in response.content:
            if content.type == "text":
                final_text.append(content.text)

        self.conversation_history.append({"role": "assistant", "content": response.content})

        return "\n".join(final_text)

    async def chat_loop(self):
        """Run an interactive chat loop"""
        print("\nMCP Client Started!")
        print("Type your queries or 'quit' to exit.")

        while True:
            try:
                query = input("\nQuery: ").strip()

                if query.lower() == "quit":
                    break

                response = await self.process_query(query)
                print("\n" + response)

            except Exception as e:
                print(f"\nError: {str(e)}")

    async def cleanup(self):
        """Clean up resources"""
        await self.exit_stack.aclose()


async def main():
    if len(sys.argv) < 2:
        print("Usage: python client.py <path_to_server_script>")
        sys.exit(1)

    client = MCPClient()
    try:
        await client.connect_to_server(sys.argv[1])
        await client.chat_loop()
    finally:
        await client.cleanup()


if __name__ == "__main__":
    import sys

    asyncio.run(main())
