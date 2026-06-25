"""
Indexing pipeline: pull data from Shopify, chunk it, embed it, and upsert into ChromaDB.
Can be triggered on startup or via the /index/sync API endpoint.
"""
import hashlib
import logging

from app.config import settings
from app.shopify_client import ShopifyClient, strip_html
from app.vector_store import index_faq_content, index_products

logger = logging.getLogger(__name__)

CHUNK_SIZE = 500  # characters per FAQ chunk
CHUNK_OVERLAP = 50


def _chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping chunks for better retrieval."""
    if not text or len(text) <= chunk_size:
        return [text] if text else []
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - overlap
    return chunks


def _make_chunk_id(source_url: str, chunk_index: int) -> str:
    raw = f"{source_url}::{chunk_index}"
    return hashlib.md5(raw.encode()).hexdigest()


def _get_client() -> ShopifyClient:
    return ShopifyClient(
        shop_domain=settings.shopify_shop_domain,
        access_token=settings.shopify_access_token,
        api_version=settings.shopify_api_version,
    )


async def sync_products() -> dict:
    """Pull all products from Shopify and index them in ChromaDB."""
    client = _get_client()
    logger.info("Fetching products from Shopify...")
    products = await client.get_products_full()
    logger.info(f"Fetched {len(products)} products.")
    count = await index_products(products)
    return {"indexed": count, "total_fetched": len(products)}


async def sync_faq_content() -> dict:
    """Pull pages, policies, and blog articles from Shopify and index them."""
    client = _get_client()
    chunks: list[dict] = []

    # ── Pages ────────────────────────────────────────────────────────────────
    logger.info("Fetching pages...")
    pages = await client.get_pages()
    for page in pages:
        text = strip_html(page.get("body", ""))
        if not text:
            continue
        url = f"/pages/{page['handle']}"
        title = page.get("title", "")
        for i, chunk in enumerate(_chunk_text(text)):
            chunks.append({
                "id": _make_chunk_id(url, i),
                "text": f"[{title}]\n{chunk}",
                "source_type": "page",
                "source_url": url,
                "source_title": title,
            })

    # ── Policies ─────────────────────────────────────────────────────────────
    logger.info("Fetching policies...")
    policies = await client.get_policies()
    for policy in policies:
        text = strip_html(policy.get("body", ""))
        if not text:
            continue
        url = policy.get("url", f"/policies/{policy.get('type', '').lower()}")
        title = policy.get("title", "")
        for i, chunk in enumerate(_chunk_text(text)):
            chunks.append({
                "id": _make_chunk_id(url, i),
                "text": f"[{title}]\n{chunk}",
                "source_type": "policy",
                "source_url": url,
                "source_title": title,
            })

    # ── Blog Articles ─────────────────────────────────────────────────────────
    logger.info("Fetching blog articles...")
    blogs = await client.get_blogs_with_articles()
    for blog in blogs:
        blog_handle = blog.get("handle", "")
        for edge in blog.get("articles", {}).get("edges", []):
            article = edge["node"]
            text = strip_html(article.get("body", ""))
            if not text:
                continue
            url = f"/blogs/{blog_handle}/{article['handle']}"
            title = article.get("title", "")
            for i, chunk in enumerate(_chunk_text(text)):
                chunks.append({
                    "id": _make_chunk_id(url, i),
                    "text": f"[{title}]\n{chunk}",
                    "source_type": "blog_article",
                    "source_url": url,
                    "source_title": title,
                })

    logger.info(f"Total FAQ chunks to index: {len(chunks)}")
    count = await index_faq_content(chunks)
    return {"indexed": count, "total_chunks": len(chunks)}


async def sync_all() -> dict:
    """Run a full sync of products and FAQ content."""
    import traceback
    try:
        logger.info("=== Starting full index sync ===")
        products_result = await sync_products()
        faq_result = await sync_faq_content()
        logger.info("=== Index sync complete ===")
        return {
            "products": products_result,
            "faq": faq_result,
        }
    except Exception as e:
        with open("error.log", "w") as f:
            f.write(traceback.format_exc())
        raise e
