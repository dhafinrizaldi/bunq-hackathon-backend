"""
Quick test: send a receipt image directly to the Anthropic API using
the same logic as MCPClient.process_receipt_image.

Usage:
    python test_receipt_extraction.py path/to/receipt.jpg
"""
import base64
import json
import sys
from pathlib import Path

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()


def extract_receipt(image_path: str) -> dict:
    path = Path(image_path)
    suffix = path.suffix.lower()
    media_type_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}
    media_type = media_type_map.get(suffix, "image/jpeg")

    image_b64 = base64.b64encode(path.read_bytes()).decode("utf-8")

    client = Anthropic()
    extract_tool = {
        "name": "extract_receipt",
        "description": "Extract all line items from a receipt image into structured data",
        "input_schema": {
            "type": "object",
            "properties": {
                "currency": {"type": "string", "description": "Currency code ISO 4217, e.g. EUR"},
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "Item name"},
                            "quantity": {"type": "integer", "description": "Quantity ordered"},
                            "total": {
                                "type": "number",
                                "description": "Total price for this line. Negative for discounts.",
                            },
                        },
                        "required": ["name", "quantity", "total"],
                    },
                },
            },
            "required": ["currency", "items"],
        },
    }

    response = client.messages.create(
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
                        "source": {"type": "base64", "media_type": media_type, "data": image_b64},
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


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_receipt_extraction.py <image_path>")
        sys.exit(1)

    result = extract_receipt(sys.argv[1])
    print(json.dumps(result, indent=2))
    print(f"\nTotal items extracted: {len(result['items'])}")
    total = sum(i['total'] for i in result['items'])
    print(f"Sum of all line items: {result['currency']} {total:.2f}")
