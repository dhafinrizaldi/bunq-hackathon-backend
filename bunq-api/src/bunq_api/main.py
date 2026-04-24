import logging
import os
from pathlib import Path

from bunq import ApiEnvironmentType
from bunq.sdk.context.api_context import ApiContext
from bunq.sdk.context.bunq_context import BunqContext
from dotenv import load_dotenv

logger = logging.getLogger(__name__)
# Load .env from project root (bunq-api folder)
env_path = Path(__file__).parent / ".env"
load_dotenv()

api_key = os.getenv("BUNQ_API_KEY")
logger.info("BUNQ_API_KEY loaded: %s", "yes" if api_key else "NO, key is missing")

# Create an API context for production
api_context = ApiContext.create(
    ApiEnvironmentType.SANDBOX,  # SANDBOX for testing
    api_key,
    "My Device Description",
)

# Save the API context to a file for future use
api_context.save("bunq_api_context.conf")

# Load the API context into the SDK
BunqContext.load_api_context(api_context)
