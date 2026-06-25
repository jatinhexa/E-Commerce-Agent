# E-Commerce AI Agent

An intelligent, multi-turn conversational agent for Shopify stores. The system consists of a Next.js frontend, a FastAPI-based Conversational Agent service, and an MCP (Model Context Protocol) service that handles vector embeddings and Shopify integrations.

## Architecture
The project is split into three main services:
1. **Frontend (`/frontend`)**: A Next.js web application providing the user interface for the chat.
2. **Agent Service (`/ecom-agent-service`)**: The core AI logic handling user queries, conversational memory, and routing tool requests to the MCP service.
3. **MCP Service (`/ecom-mcp-service`)**: Handles data indexing from Shopify to a local ChromaDB vector store, handles tool execution, and connects to the OpenAI/Anthropic APIs.

---

## 1. Setup & Installation

Before running the application, you need to install the dependencies for all three services. You should open a separate terminal window for each service.

### E-Commerce MCP Service
Requires Python 3.10+
```bash
cd ecom-mcp-service
# Recommended: Create and activate a virtual environment
python -m venv venv
venv\Scripts\activate  # On Windows

# Install dependencies
pip install -r requirements.txt
```

### E-Commerce Agent Service
Requires Python 3.10+
```bash
cd ecom-agent-service
# Recommended: Create and activate a virtual environment
python -m venv venv
venv\Scripts\activate  # On Windows

# Install dependencies
pip install -r requirements.txt
```

### Frontend Service
Requires Node.js 18+
```bash
cd frontend
# Install dependencies
npm install
```

---

## 2. Environment Variables

Each service requires its own `.env` file. You must create these files in their respective folders before running the services.

### `ecom-mcp-service/.env`
```env
# Shopify credentials
SHOPIFY_SHOP_DOMAIN=your-store-name.myshopify.com
SHOPIFY_ACCESS_TOKEN=your_shopify_access_token
SHOPIFY_API_VERSION=2025-01

# OpenAI API key for embeddings
OPENAI_API_KEY=your_openai_api_key
EMBEDDING_MODEL=text-embedding-3-small

# ChromaDB persistence directory
CHROMA_PERSIST_DIR=./data/chroma/my_store_index

# Server configuration
MCP_HOST=0.0.0.0
MCP_PORT=8004
```

### `ecom-agent-service/.env`
```env
# Anthropic API Key
ANTHROPIC_API_KEY=your_anthropic_api_key
ANTHROPIC_MODEL=claude-sonnet-3-5

# MCP Server Connection
ECOM_MCP_URL=http://localhost:8004/mcp
ECOM_MCP_BASE_URL=http://localhost:8004

# Server configuration
AGENT_PORT=8003
```

---

## 3. Running the Application

You must run all three services simultaneously. Open **three separate terminal windows**.

### Terminal 1: Run the MCP Service
This service must be started first as the Agent relies on it.
```bash
cd ecom-mcp-service
# Activate your virtual environment if you used one
uvicorn app.main:app --host 0.0.0.0 --port 8004 --reload
```

### Terminal 2: Run the Agent Service
```bash
cd ecom-agent-service
# Activate your virtual environment if you used one
uvicorn app.main:app --host 0.0.0.0 --port 8003 --reload
```

### Terminal 3: Run the Frontend
```bash
cd frontend
npm run dev
```

The application is now running! You can view the chat interface by navigating to `http://localhost:3000` in your browser.

---

## 4. Indexing Data (Initial Setup)

Before the AI agent can answer questions about your products, you need to pull your products from Shopify into the local ChromaDB database. 

Ensure the `ecom-mcp-service` is running, then open a new terminal window and run:

```powershell
# Using PowerShell
curl.exe -X POST http://127.0.0.1:8004/index/sync

# OR using native PowerShell commands
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8004/index/sync"
```

This may take a few minutes depending on the size of your store. Once complete, your agent will be fully aware of your store's inventory!
