from fastapi import FastAPI
import os
import logging
from bunq.sdk.context.api_context import ApiContext
from bunq.sdk.context.bunq_context import BunqContext
from dotenv import load_dotenv
from bunq.sdk.model.generated.endpoint import MonetaryAccountApiObject, PaymentApiObject
from pathlib import Path
from bunq import Pagination
from .routes import monetary_accounts, payments, users, request_inquiries
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Restore API context
logger.info("Restoring bunq API context")
api_context = ApiContext.restore("bunq_api_context.conf")
BunqContext.load_api_context(api_context)
logger.info("bunq API context loaded successfully")
# app.state.api_context = api_context

# Include routers
app.include_router(monetary_accounts.router)
app.include_router(payments.router)
app.include_router(users.router)
app.include_router(request_inquiries.router)
