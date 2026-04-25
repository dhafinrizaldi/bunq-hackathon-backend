import asyncio
import io
import json
import logging
import os
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Optional

from anthropic import Anthropic
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

load_dotenv()  # load environment variables from .env
# Fallback to workspace root .env when mcp-client/.env is missing or blank.
if not os.getenv("ANTHROPIC_API_KEY") or not os.getenv("OPENAI_API_KEY"):
    load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=True)

logger = logging.getLogger(__name__)


class MCPClient:
    def __init__(self):
        # Initialize session and client objects
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.anthropic = Anthropic()
        self.conversation_history = []
        self._openai = None  # lazy-init so missing key doesn't crash startup

    def _get_openai(self):
        if self._openai is None:
            from openai import OpenAI
            self._openai = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        return self._openai

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
        # Append new user message to persistent history
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

        # Use the full history instead of a fresh list
        response = self.anthropic.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            messages=self.conversation_history,  # ← use shared history
            tools=available_tools,
        )

        final_text = []
        assistant_message_content = []

        for content in response.content:
            if content.type == "text":
                final_text.append(content.text)
                assistant_message_content.append(content)
            elif content.type == "tool_use":
                tool_name = content.name
                tool_args = content.input

                logger.info("Calling tool %s with args %s", tool_name, tool_args)
                result = await self.session.call_tool(tool_name, tool_args)
                logger.info("Tool %s returned successfully", tool_name)
                final_text.append(f"[Calling tool {tool_name} with args {tool_args}]")

                assistant_message_content.append(content)
                self.conversation_history.append(
                    {  # ← append to shared history
                        "role": "assistant",
                        "content": assistant_message_content,
                    }
                )
                self.conversation_history.append(
                    {  # ← append to shared history
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": content.id,
                                "content": result.content,
                            }
                        ],
                    }
                )

                response = self.anthropic.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=1000,
                    messages=self.conversation_history,  # ← use shared history
                    tools=available_tools,
                )

                final_text.append(response.content[0].text)

        # Save the final assistant response to history
        self.conversation_history.append(
            {"role": "assistant", "content": response.content[0].text}
        )

        return "\n".join(final_text)

    async def process_receipt_image(self, image_base64: str, media_type: str = "image/jpeg") -> dict:
        """Extract receipt line items from a base64-encoded image using Claude Vision."""
        extract_tool = {
            "name": "extract_receipt",
            "description": "Extract all line items from a receipt image into structured data",
            "input_schema": {
                "type": "object",
                "properties": {
                    "currency": {
                        "type": "string",
                        "description": "Currency code ISO 4217, e.g. EUR",
                    },
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string", "description": "Item name"},
                                "quantity": {"type": "integer", "description": "Quantity ordered"},
                                "total": {
                                    "type": "number",
                                    "description": "Total price for this line (quantity × unit price). Negative for discounts.",
                                },
                            },
                            "required": ["name", "quantity", "total"],
                        },
                    },
                },
                "required": ["currency", "items"],
            },
        }
        print("Hell")
        response = self.anthropic.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            tools=[extract_tool],
            tool_choice={"type": "tool", "name": "extract_receipt"},
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": image_base64,
                            },
                        },
                        {
                            "type": "text",
                            "text": (
                                "Extract all line items from this receipt. "
                                "Include every item with its quantity and total price. "
                                "For discounts, include them as separate items with negative total values."
                            ),
                        },
                    ],
                }
            ],
        )

        for block in response.content:
            if block.type == "tool_use" and block.name == "extract_receipt":
                return block.input

        raise ValueError("Claude did not return structured receipt data")

    async def interpret_split(
        self,
        description: str,
        payee_email: str,
        participants: list[dict],
        items: list[dict],
    ) -> dict:
        """Map a free-text split description to per-participant item allocations.

        Returns:
            {
              "currency": "EUR",
              "allocations": [
                {
                  "participant_email": "...",
                  "total_amount": 12.34,
                  "items": [
                    {"item_id": 1, "description": "...", "share_amount": 5.50}
                  ]
                },
                ...
              ]
            }
        """
        record_split_tool = {
            "name": "record_split",
            "description": (
                "Record per-participant allocations for a receipt based on the user's "
                "free-text description of who had what. The sum of share_amount across "
                "all participants for each item MUST equal that item's total_price. "
                "Every receipt item MUST appear in at least one allocation. The payee "
                "(identified by payee_email) is included as a participant for items they "
                "consumed themselves; do not skip them."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "currency": {
                        "type": "string",
                        "description": "ISO 4217 currency code, e.g. EUR",
                    },
                    "allocations": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "participant_email": {"type": "string"},
                                "total_amount": {
                                    "type": "number",
                                    "description": "Sum of this participant's item shares",
                                },
                                "items": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "item_id": {"type": "integer"},
                                            "description": {"type": "string"},
                                            "share_amount": {"type": "number"},
                                        },
                                        "required": ["item_id", "share_amount"],
                                    },
                                },
                            },
                            "required": ["participant_email", "total_amount", "items"],
                        },
                    },
                },
                "required": ["currency", "allocations"],
            },
        }

        prompt = f"""You are splitting a bar/restaurant bill among friends.

The user (payee) is {payee_email}. They paid the full bill and want to request money
back from the others. Include the payee as a participant for any items they consumed
themselves — they need a share too, even though they won't be billed for it.

The full participant list (including the payee) is:
{json.dumps([{"email": payee_email, "name": "the user (me/I)"}] + list(participants), indent=2)}

The receipt items (with stable integer ids) are:
{json.dumps(items, indent=2)}

The user's description of who had what:
\"\"\"{description}\"\"\"

Rules:
- Use participant_email values exactly as listed above. Do not invent emails.
- The user often refers to themselves as "I", "me", or "myself" — that's {payee_email}.
- If an item is shared by N people, divide its total_price by N. Round each share to 2
  decimals. If shares don't sum exactly to total_price due to rounding, push the
  rounding remainder onto the payee's share.
- Every receipt item MUST be assigned to at least one participant. If the description
  is ambiguous about an item, default to splitting it evenly among everyone.
- total_amount per participant = sum of their item share_amount values.
- Output one entry per participant who has at least one item. Skip participants with
  zero items.

Call the record_split tool now with the structured allocation."""

        response = self.anthropic.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            tools=[record_split_tool],
            tool_choice={"type": "tool", "name": "record_split"},
            messages=[{"role": "user", "content": prompt}],
        )

        for block in response.content:
            if block.type == "tool_use" and block.name == "record_split":
                return block.input

        raise ValueError("Claude did not return structured split data")

    async def transcribe_audio(self, audio_bytes: bytes, filename: str) -> dict:
        """Transcribe an audio recording via OpenAI Whisper. Returns {'transcript': str}."""
        if not os.getenv("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY not set")

        client = self._get_openai()
        # OpenAI SDK expects a file-like object with a name (used to infer format)
        buf = io.BytesIO(audio_bytes)
        buf.name = filename or "audio.m4a"

        # Run the blocking SDK call in a thread so we don't block the event loop
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: client.audio.transcriptions.create(
                model="whisper-1",
                file=buf,
            ),
        )
        # SDK returns a Transcription object with `.text`
        text = getattr(result, "text", None) or ""
        return {"transcript": text}

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
