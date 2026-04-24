from pydantic import BaseModel, Field
from typing import List
from decimal import Decimal


class ReceiptItem(BaseModel):
    """Represents a single item on a receipt."""
    name: str = Field(..., description="Name of the item")
    quantity: int = Field(..., gt=0, description="Quantity of the item")
    total: Decimal = Field(..., gt=0, description="Total price for this item")


class Receipt(BaseModel):
    """Represents a complete receipt with currency and line items."""
    currency: str = Field(default="EUR", description="Currency code (ISO 4217)")
    items: List[ReceiptItem] = Field(..., description="List of items on the receipt")

    def get_total(self) -> Decimal:
        """Calculate the total amount of the receipt."""
        return sum(item.total for item in self.items)

    class Config:
        json_schema_extra = {
            "example": {
                "currency": "EUR",
                "items": [
                    {
                        "name": "pasta_bolognese",
                        "quantity": 2,
                        "total": 24
                    },
                    {
                        "name": "white_wine",
                        "quantity": 1,
                        "total": 38
                    }
                ]
            }
        }


class UserSplit(BaseModel):
    """Represents what the user's split is from a receipt"""
    name: str = Field(..., description="Name of user")
    total: float = Field(..., gt=0, description="Total amount the user's split is")
    currency: str = Field(default="EUR", description="Currency code (ISO 4217)")
    description: str = Field(..., description='Description of the items within the user splits are' )

# Example usage
if __name__ == "__main__":
    # Create a receipt from dictionary
    receipt_data = {
        "currency": "EUR",
        "items": [
            {
                "name": "pasta_bolognese",
                "quantity": 2,
                "total": 24
            },
            {
                "name": "white_wine",
                "quantity": 1,
                "total": 38
            }
        ]
    }

    receipt = Receipt(**receipt_data)
    print(f"Receipt: {receipt}")
    print(f"Total: {receipt.get_total()} {receipt.currency}")
    print(f"JSON: {receipt.model_dump_json(indent=2)}")