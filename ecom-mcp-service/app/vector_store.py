"""
ChromaDB vector store manager.
Two collections:
  - 'products'    : product embeddings for semantic search & recommendations
  - 'faq_content' : page/policy/blog embeddings for FAQ answering
"""
import json
import logging
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings
from openai import AsyncOpenAI

from app.config import settings

logger = logging.getLogger(__name__)


# ─── Embedding Helper ─────────────────────────────────────────────────────────

_openai_client: AsyncOpenAI | None = None


def _get_openai() -> AsyncOpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
    return _openai_client


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a list of texts using OpenAI text-embedding-3-small in batches."""
    client = _get_openai()
    all_embeddings: list[list[float]] = []
    batch_size = settings.embedding_batch_size

    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        response = await client.embeddings.create(
            model=settings.embedding_model,
            input=batch,
        )
        all_embeddings.extend([item.embedding for item in response.data])

    return all_embeddings


# ─── ChromaDB Client ─────────────────────────────────────────────────────────

_chroma_client: chromadb.ClientAPI | None = None


def get_chroma() -> chromadb.ClientAPI:
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = chromadb.PersistentClient(
            path=settings.chroma_persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
    return _chroma_client


def get_products_collection() -> chromadb.Collection:
    return get_chroma().get_or_create_collection(
        name="products",
        metadata={"hnsw:space": "cosine"},
    )


def get_faq_collection() -> chromadb.Collection:
    return get_chroma().get_or_create_collection(
        name="faq_content",
        metadata={"hnsw:space": "cosine"},
    )


# ─── Products ────────────────────────────────────────────────────────────────

async def index_products(products: list[dict]) -> int:
    """
    Index a list of Shopify products into the ChromaDB 'products' collection.
    Returns the number of products indexed.
    """
    collection = get_products_collection()

    ids: list[str] = []
    texts: list[str] = []
    metadatas: list[dict] = []

    for product in products:
        pid = product["id"]  # gid://shopify/Product/123456
        # Build searchable text: title + description + tags + product type
        search_text = " ".join(
            filter(
                None,
                [
                    product.get("title", ""),
                    product.get("description_text", ""),
                    " ".join(product.get("tags", [])),
                    product.get("productType", ""),
                    product.get("vendor", ""),
                ],
            )
        )

        # Build metadata for filtering and display
        images = product.get("images", [])
        meta: dict[str, Any] = {
            "shopify_id": pid,
            "title": product.get("title", ""),
            "handle": product.get("handle", ""),
            "product_type": product.get("productType", "") or "",
            "vendor": product.get("vendor", "") or "",
            "tags": json.dumps(product.get("tags", [])),
            "min_price": product.get("min_price", 0.0),
            "max_price": product.get("max_price", 0.0),
            "currency": product.get("currency", "USD"),
            "image_url": images[0]["url"] if images else "",
            "image_alt": images[0].get("altText", "") if images else "",
            # Store up to 3 image URLs as separate fields
            "image_url_2": images[1]["url"] if len(images) > 1 else "",
            "image_url_3": images[2]["url"] if len(images) > 2 else "",
            "description_snippet": (product.get("description_text", "") or "")[:300],
        }

        ids.append(pid)
        texts.append(search_text or product.get("title", ""))
        metadatas.append(meta)

    if not ids:
        return 0

    # Generate embeddings
    logger.info(f"Generating embeddings for {len(ids)} products...")
    embeddings = await embed_texts(texts)

    # Upsert into ChromaDB
    collection.upsert(
        ids=ids,
        embeddings=embeddings,
        documents=texts,
        metadatas=metadatas,
    )
    logger.info(f"Indexed {len(ids)} products into ChromaDB.")
    return len(ids)


async def search_products_in_store(
    query: str,
    top_k: int = 10,
    min_price: float | None = None,
    max_price: float | None = None,
    product_type: str | None = None,
) -> list[dict]:
    """
    Semantic search over the products collection.
    Returns a list of product metadata dicts ordered by relevance.
    """
    collection = get_products_collection()

    # Build ChromaDB where filter
    where: dict[str, Any] = {}
    conditions = []
    if min_price is not None:
        conditions.append({"max_price": {"$gte": min_price}})
    if max_price is not None:
        conditions.append({"min_price": {"$lte": max_price}})
    if product_type:
        conditions.append({"product_type": {"$eq": product_type}})
    if len(conditions) == 1:
        where = conditions[0]
    elif len(conditions) > 1:
        where = {"$and": conditions}

    # Embed query
    [query_embedding] = await embed_texts([query])

    kwargs: dict[str, Any] = {
        "query_embeddings": [query_embedding],
        "n_results": min(top_k, max(1, collection.count())),
        "include": ["metadatas", "distances", "documents"],
    }
    if where:
        kwargs["where"] = where

    results = collection.query(**kwargs)

    output = []
    metadatas_list = results.get("metadatas", [[]])[0]
    distances_list = results.get("distances", [[]])[0]

    for meta, distance in zip(metadatas_list, distances_list):
        item = dict(meta)
        item["relevance_score"] = round(1 - distance, 4)  # cosine → similarity
        item["tags"] = json.loads(item.get("tags", "[]"))
        output.append(item)

    return output


async def get_product_by_id(product_id: str) -> dict | None:
    """Fetch a single product's metadata from the collection by Shopify ID."""
    collection = get_products_collection()
    try:
        result = collection.get(ids=[product_id], include=["metadatas", "embeddings"])
        if result["ids"]:
            return result["metadatas"][0]
    except Exception:
        pass
    return None


async def get_similar_products(
    product_id: str, top_k: int = 5, exclude_same_type: bool = False
) -> list[dict]:
    """
    Find products similar to the given product by vector similarity.
    """
    collection = get_products_collection()
    try:
        result = collection.get(ids=[product_id], include=["embeddings", "metadatas"])
        if not result["ids"]:
            return []
        embedding = result["embeddings"][0]
        source_meta = result["metadatas"][0]
    except Exception:
        return []

    where: dict[str, Any] = {}
    if exclude_same_type and source_meta.get("product_type"):
        where = {"product_type": {"$ne": source_meta["product_type"]}}

    kwargs: dict[str, Any] = {
        "query_embeddings": [embedding],
        "n_results": min(top_k + 1, max(1, collection.count())),
        "include": ["metadatas", "distances"],
    }
    if where:
        kwargs["where"] = where

    results = collection.query(**kwargs)
    output = []
    for meta, dist in zip(
        results.get("metadatas", [[]])[0],
        results.get("distances", [[]])[0],
    ):
        if meta.get("shopify_id") == product_id:
            continue  # skip self
        item = dict(meta)
        item["relevance_score"] = round(1 - dist, 4)
        item["tags"] = json.loads(item.get("tags", "[]"))
        output.append(item)

    return output[:top_k]


# ─── FAQ Content ─────────────────────────────────────────────────────────────

async def index_faq_content(content_chunks: list[dict]) -> int:
    """
    Index FAQ content chunks.
    Each chunk: { id, text, source_type, source_url, source_title }
    """
    collection = get_faq_collection()
    if not content_chunks:
        return 0

    ids = [chunk["id"] for chunk in content_chunks]
    texts = [chunk["text"] for chunk in content_chunks]
    metadatas = [
        {
            "source_type": chunk.get("source_type", "unknown"),
            "source_url": chunk.get("source_url", ""),
            "source_title": chunk.get("source_title", ""),
        }
        for chunk in content_chunks
    ]

    logger.info(f"Generating embeddings for {len(ids)} FAQ chunks...")
    embeddings = await embed_texts(texts)

    collection.upsert(
        ids=ids,
        embeddings=embeddings,
        documents=texts,
        metadatas=metadatas,
    )
    logger.info(f"Indexed {len(ids)} FAQ chunks into ChromaDB.")
    return len(ids)


async def search_faq_content(question: str, top_k: int = 4) -> list[dict]:
    """Semantic search over FAQ content."""
    collection = get_faq_collection()
    count = collection.count()
    if count == 0:
        return []

    [query_embedding] = await embed_texts([question])

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(top_k, count),
        include=["metadatas", "documents", "distances"],
    )

    output = []
    for meta, doc, dist in zip(
        results.get("metadatas", [[]])[0],
        results.get("documents", [[]])[0],
        results.get("distances", [[]])[0],
    ):
        output.append(
            {
                "text": doc,
                "source_type": meta.get("source_type", ""),
                "source_url": meta.get("source_url", ""),
                "source_title": meta.get("source_title", ""),
                "relevance_score": round(1 - dist, 4),
            }
        )

    return output
