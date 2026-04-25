import logging
import sys
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from client import MCPClient

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s"
)
logger = logging.getLogger(__name__)

# Global client instance
mcp_client = MCPClient()


class QueryRequest(BaseModel):
    query: str


class ReceiptRequest(BaseModel):
    image_base64: str
    media_type: str = "image/jpeg"


class InterpretSplitRequest(BaseModel):
    description: str
    payee_email: str
    participants: list[dict]   # [{email, name}]
    items: list[dict]          # [{id, description, total_price, quantity}]


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    if len(sys.argv) < 2:
        raise RuntimeError("Usage: python app.py <path_to_server_script>")
    logger.info("Connecting to MCP server: %s", sys.argv[1])
    await mcp_client.connect_to_server(sys.argv[1])
    logger.info("MCP server connected")
    yield
    # Shutdown
    logger.info("Shutting down MCP client")
    await mcp_client.cleanup()


app = FastAPI(lifespan=lifespan)
# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/query")
async def handle_query(request: QueryRequest):
    try:
        logger.info("Received query: %s", request.query)
        result = await mcp_client.process_query(request.query)
        logger.info("Query processed successfully")
        return {"response": result}
    except Exception as e:
        logger.error("Error processing query: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/process_receipt")
async def handle_process_receipt(request: ReceiptRequest):
    try:
        logger.info("Processing receipt image (%s)", request.media_type)
        result = await mcp_client.process_receipt_image(request.image_base64, request.media_type)
        logger.info("Receipt processed: %d items extracted", len(result.get("items", [])))
        return result
    except Exception as e:
        logger.error("Error processing receipt: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/interpret_split")
async def handle_interpret_split(request: InterpretSplitRequest):
    try:
        logger.info(
            "Interpreting split: %d items, %d participants",
            len(request.items), len(request.participants),
        )
        result = await mcp_client.interpret_split(
            description=request.description,
            payee_email=request.payee_email,
            participants=request.participants,
            items=request.items,
        )
        return result
    except Exception as e:
        logger.error("Error interpreting split: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/transcribe")
async def handle_transcribe(audio: UploadFile = File(...)):
    try:
        data = await audio.read()
        logger.info("Transcribing audio: %s (%d bytes)", audio.filename, len(data))
        result = await mcp_client.transcribe_audio(data, audio.filename or "audio.m4a")
        return result
    except Exception as e:
        logger.error("Error transcribing audio: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
