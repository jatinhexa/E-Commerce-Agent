from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Anthropic
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6"

    # MCP endpoints
    ecom_mcp_url: str = "http://localhost:8004/mcp"

    # Agent limits
    max_agent_iterations: int = 15

    # Session
    session_ttl_minutes: int = 60

    # Server
    agent_port: int = 8003

    # Shopify (passed to MCP tools)
    shopify_shop_domain: str = ""
    shopify_storefront_url: str = ""

    # Index sync endpoint on ecom-mcp-service
    ecom_mcp_base_url: str = "http://localhost:8004"


settings = Settings()
