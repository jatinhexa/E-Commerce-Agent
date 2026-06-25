"""
FastMCP server exposing 6 e-commerce tools.
Tools: search_products, generate_moodboard, get_recommendations,
       search_faq, track_order, create_ticket
"""
import json
import logging
import os
import uuid
from datetime import datetime, timezone

from fastmcp import FastMCP

from app.config import settings
from app.indexer import sync_all
from app.shopify_client import ShopifyClient
from app.vector_store import (
    get_similar_products,
    search_faq_content,
    search_products_in_store,
)

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

mcp = FastMCP("E-Commerce Agent — Tools")


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _get_client() -> ShopifyClient:
    return ShopifyClient(
        shop_domain=settings.shopify_shop_domain,
        access_token=settings.shopify_access_token,
        api_version=settings.shopify_api_version,
    )


def _format_product(meta: dict) -> dict:
    """Format a product metadata dict for display."""
    images = [meta.get("image_url", "")]
    if meta.get("image_url_2"):
        images.append(meta["image_url_2"])
    if meta.get("image_url_3"):
        images.append(meta["image_url_3"])
    images = [img for img in images if img]

    return {
        "title": meta.get("title", ""),
        "handle": meta.get("handle", ""),
        "product_type": meta.get("product_type", ""),
        "vendor": meta.get("vendor", ""),
        "min_price": meta.get("min_price", 0),
        "max_price": meta.get("max_price", 0),
        "currency": meta.get("currency", "USD"),
        "images": images,
        "description": meta.get("description_snippet", ""),
        "tags": meta.get("tags", []),
        "relevance_score": meta.get("relevance_score", 0),
        "product_url": f"/products/{meta.get('handle', '')}",
    }


# ─── Tool 1: Product Search ─────────────────────────────────────────────────

@mcp.tool
async def search_products(
    query: str,
    max_results: int = 10,
    min_price: float | None = None,
    max_price: float | None = None,
    product_type: str | None = None,
) -> list[dict]:
    """Search products by natural language query with optional price and type filters.
    Returns products with images, prices, and relevance scores.
    Use this when the customer is looking for specific products or browsing."""
    results = await search_products_in_store(
        query=query,
        top_k=max_results,
        min_price=min_price,
        max_price=max_price,
        product_type=product_type,
    )
    return [_format_product(r) for r in results]


# ─── Tool 2: MoodBoard ──────────────────────────────────────────────────────

@mcp.tool
async def generate_moodboard(query: str, max_items: int = 8) -> dict:
    """Generate a visual moodboard for an aesthetic or theme query.
    Returns a curated set of products with images, optimized for a visual grid display.
    Use this when the customer asks for inspiration, aesthetic boards, or themed collections."""
    # Use a broader search to get diverse results
    results = await search_products_in_store(
        query=query,
        top_k=max_items * 3,  # fetch more, then curate
    )

    # Diversify: pick at most 2 from each product type
    seen_types: dict[str, int] = {}
    curated: list[dict] = []
    for r in results:
        ptype = r.get("product_type", "Other") or "Other"
        if seen_types.get(ptype, 0) >= 2:
            continue
        seen_types[ptype] = seen_types.get(ptype, 0) + 1
        curated.append(r)
        if len(curated) >= max_items:
            break

    return {
        "theme": query,
        "item_count": len(curated),
        "products": [_format_product(c) for c in curated],
    }


# ─── Tool 3: Product Recommendations ────────────────────────────────────────

@mcp.tool
async def get_recommendations(product_handle: str, max_results: int = 5) -> list[dict]:
    """Get product recommendations similar to a given product.
    Uses semantic similarity to find related or complementary items.
    The product_handle is the Shopify product URL handle (e.g. 'blue-cotton-tshirt')."""
    # Look up product ID by handle in the collection
    from app.vector_store import get_products_collection

    collection = get_products_collection()
    # Search for the product by handle in metadata
    all_products = collection.get(include=["metadatas"])
    product_id = None
    for pid, meta in zip(all_products["ids"], all_products["metadatas"]):
        if meta.get("handle") == product_handle:
            product_id = pid
            break

    if not product_id:
        return [{"error": f"Product with handle '{product_handle}' not found in index."}]

    # Get similar products (mix of same-type and cross-type)
    similar = await get_similar_products(product_id, top_k=max_results)
    return [_format_product(s) for s in similar]


# ─── Tool 4: FAQ Search ─────────────────────────────────────────────────────

@mcp.tool
async def search_faq(question: str) -> list[dict]:
    """Search store FAQs, policies, and content pages to answer customer questions.
    Use this for questions about shipping, returns, sizing, policies, store info, etc.
    Returns relevant content chunks with source attribution."""
    results = await search_faq_content(question=question, top_k=4)
    return [
        {
            "answer_text": r["text"],
            "source_type": r["source_type"],
            "source_url": r["source_url"],
            "source_title": r["source_title"],
            "relevance_score": r["relevance_score"],
        }
        for r in results
    ]


# ─── Tool 5: Order Tracking ─────────────────────────────────────────────────

@mcp.tool
async def track_order(
    order_number: str,
    email: str | None = None,
    phone: str | None = None,
) -> dict:
    """Look up order status by order number with customer verification.
    At least one of email or phone must be provided for identity verification.
    Returns order status, fulfillment info, tracking details, and line items."""
    if not email and not phone:
        return {
            "error": "Please provide the email address or phone number associated with the order for verification."
        }

    client = _get_client()
    orders = await client.lookup_order(order_number=order_number, email=email)

    if not orders:
        return {
            "error": f"No order found matching #{order_number}. Please check the order number and email address."
        }

    order = orders[0]

    # Format fulfillment info
    fulfillments = []
    for f in order.get("fulfillments", []):
        tracking_info_list = f.get("trackingInfo", [])
        for ti in tracking_info_list:
            fulfillments.append({
                "status": f.get("status", "unknown"),
                "tracking_number": ti.get("number", ""),
                "tracking_url": ti.get("url", ""),
                "carrier": ti.get("company", ""),
                "updated_at": f.get("updatedAt", ""),
            })

    # Format line items
    items = []
    for li in order.get("lineItems", []):
        variant = li.get("variant") or {}
        image = variant.get("image") or {}
        items.append({
            "title": li.get("title", ""),
            "quantity": li.get("quantity", 0),
            "variant": variant.get("title", ""),
            "image_url": image.get("url", ""),
            "unit_price": li.get("originalUnitPriceSet", {}).get("shopMoney", {}).get("amount", ""),
        })

    total = order.get("totalPriceSet", {}).get("shopMoney", {})
    shipping = order.get("shippingAddress") or {}

    return {
        "order_number": order.get("name", ""),
        "created_at": order.get("createdAt", ""),
        "financial_status": order.get("displayFinancialStatus", ""),
        "fulfillment_status": order.get("displayFulfillmentStatus", ""),
        "total_price": total.get("amount", ""),
        "currency": total.get("currencyCode", ""),
        "fulfillments": fulfillments,
        "line_items": items,
        "shipping_city": shipping.get("city", ""),
        "shipping_country": shipping.get("country", ""),
    }


# ─── Tool 6: Ticket Creation ────────────────────────────────────────────────

# Simple in-memory ticket store (replace with DB or webhook in production)
_tickets: dict[str, dict] = {}


@mcp.tool
async def create_ticket(
    customer_email: str,
    subject: str,
    description: str,
    priority: str = "normal",
    order_number: str | None = None,
) -> dict:
    """Create a support ticket when you cannot resolve a customer's issue.
    Use this as a last resort after attempting to help the customer directly.
    Returns a ticket ID and confirmation details."""
    ticket_id = f"TK-{uuid.uuid4().hex[:6].upper()}"
    now = datetime.now(timezone.utc).isoformat()

    ticket = {
        "ticket_id": ticket_id,
        "customer_email": customer_email,
        "subject": subject,
        "description": description,
        "priority": priority,
        "order_number": order_number,
        "status": "open",
        "created_at": now,
    }

    _tickets[ticket_id] = ticket
    logger.info(f"Created support ticket: {ticket_id} — {subject}")

    # If configured, also store as order note in Shopify
    if settings.ticket_backend == "shopify" and order_number:
        try:
            client = _get_client()
            orders = await client.lookup_order(order_number)
            if orders:
                note = f"[Support Ticket {ticket_id}] {subject}\n{description}\nPriority: {priority}\nEmail: {customer_email}"
                await client.append_order_note(orders[0]["id"], note)
                logger.info(f"Appended ticket note to order {order_number}")
        except Exception as e:
            logger.warning(f"Failed to append order note: {e}")

    return {
        "ticket_id": ticket_id,
        "status": "open",
        "message": f"Support ticket {ticket_id} created successfully. Our team will respond to {customer_email} within 24 hours.",
    }


# ─── Startup & Entry Point ──────────────────────────────────────────────────

if __name__ == "__main__":
    host = os.environ.get("MCP_HOST", "0.0.0.0")
    port = int(os.environ.get("MCP_PORT", "8004"))
    mcp.run(transport="http", host=host, port=port)
