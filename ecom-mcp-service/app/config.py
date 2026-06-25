from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Shopify credentials
    shopify_shop_domain: str = ""
    shopify_access_token: str = ""
    shopify_api_version: str = "2025-01"

    # OpenAI for embeddings
    openai_api_key: str = ""
    embedding_model: str = "text-embedding-3-small"
    embedding_batch_size: int = 50

    # ChromaDB
    chroma_persist_dir: str = "./data/chroma/"

    # Ticket system: "shopify" or "webhook"
    ticket_backend: str = "shopify"
    ticket_webhook_url: str = ""

    # Server
    mcp_host: str = "0.0.0.0"
    mcp_port: int = 8004


settings = Settings()
