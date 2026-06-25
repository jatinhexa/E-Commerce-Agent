"""
Main entry point for ecom-mcp-service.
Serves the FastMCP tools on /mcp AND a REST endpoint for index sync at /index/sync.
"""
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.indexer import sync_all
from app.server import mcp

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Mount the FastMCP SSE app
mcp_app = mcp.http_app(path="/")

app = FastAPI(
    title="E-Commerce MCP Service",
    description="MCP tools + indexing for Shopify e-commerce agent",
    version="1.0.0",
    lifespan=mcp_app.lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount MCP at /mcp
app.mount("/mcp", mcp_app)


@app.get("/")
async def root():
    return {"status": "ok", "service": "ecom-mcp-service"}


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.post("/index/sync")
async def index_sync():
    """Trigger a full re-index of products and FAQ content from Shopify."""
    logger.info("Index sync triggered via REST API")
    result = await sync_all()
    return result
