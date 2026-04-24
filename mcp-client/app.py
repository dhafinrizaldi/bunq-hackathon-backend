import logging
import sys
from contextlib import asynccontextmanager
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from client import MCPClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s"
)
logger = logging.getLogger(__name__)

# Global client instance
mcp_client = MCPClient()

class QueryRequest(BaseModel):
    query: str
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

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)