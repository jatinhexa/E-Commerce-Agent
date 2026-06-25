import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import chat

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

app = FastAPI(
    title="E-Commerce Agent Service",
    description="Multi-turn conversational agent for Shopify stores",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router)


@app.get("/")
async def root() -> dict[str, str]:
    return {"status": "ok", "service": "ecom-agent-service"}


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy"}
