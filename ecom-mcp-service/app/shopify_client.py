"""
Extended Shopify GraphQL client for the E-Commerce Agent.
Covers: products (with full image/price/variant data), orders, customers, pages, policies, blogs.
"""
import re
from typing import Any

import httpx

# ─── GraphQL Queries ─────────────────────────────────────────────────────────

PRODUCTS_FULL_QUERY = """
query ProductsFull($first: Int!, $after: String) {
  products(first: $first, after: $after, query: "status:active") {
    edges {
      node {
        id
        title
        handle
        descriptionHtml
        productType
        vendor
        tags
        seo {
          title
          description
        }
        priceRangeV2 {
          minVariantPrice { amount currencyCode }
          maxVariantPrice { amount currencyCode }
        }
        images(first: 5) {
          edges {
            node {
              url
              altText
              width
              height
            }
          }
        }
        variants(first: 10) {
          edges {
            node {
              id
              title
              price
              availableForSale
              selectedOptions { name value }
            }
          }
        }
      }
    }
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}
"""

COLLECTIONS_QUERY = """
query Collections($first: Int!, $after: String) {
  collections(first: $first, after: $after) {
    edges {
      node {
        id
        title
        handle
        descriptionHtml
        image { url altText }
      }
    }
    pageInfo { hasNextPage endCursor }
  }
}
"""

PAGES_QUERY = """
query Pages($first: Int!, $after: String) {
  pages(first: $first, after: $after) {
    edges {
      node {
        id
        title
        handle
        body
        bodySummary
      }
    }
    pageInfo { hasNextPage endCursor }
  }
}
"""

BLOGS_WITH_ARTICLES_QUERY = """
query BlogsWithArticles($first: Int!, $after: String) {
  blogs(first: $first, after: $after) {
    edges {
      node {
        id
        title
        handle
        articles(first: 50) {
          edges {
            node {
              id
              title
              handle
              body
              image { url altText }
            }
          }
        }
      }
    }
    pageInfo { hasNextPage endCursor }
  }
}
"""

POLICIES_QUERY = """
query Policies {
  shop {
    shopPolicies {
      id
      type
      title
      body
      url
    }
  }
}
"""

ORDER_LOOKUP_QUERY = """
query OrderLookup($query: String!) {
  orders(first: 5, query: $query) {
    edges {
      node {
        id
        name
        email
        createdAt
        displayFinancialStatus
        displayFulfillmentStatus
        totalPriceSet { shopMoney { amount currencyCode } }
        fulfillments {
          trackingInfo { number url company }
          status
          updatedAt
        }
        lineItems(first: 20) {
          edges {
            node {
              title
              quantity
              originalUnitPriceSet { shopMoney { amount currencyCode } }
              variant {
                title
                image { url }
              }
            }
          }
        }
        shippingAddress {
          city
          province
          country
          zip
        }
      }
    }
  }
}
"""

CREATE_ORDER_NOTE_MUTATION = """
mutation OrderNoteUpdate($input: OrderInput!) {
  orderUpdate(input: $input) {
    order { id name note }
    userErrors { field message }
  }
}
"""


# ─── Helpers ─────────────────────────────────────────────────────────────────

def strip_html(html: str | None) -> str:
    if not html:
        return ""
    text = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", text).strip()


def normalize_shop_domain(store_url: str) -> str:
    domain = store_url.strip()
    domain = re.sub(r"^https?://", "", domain)
    return domain.split("/")[0]


# ─── Client ──────────────────────────────────────────────────────────────────

class ShopifyAPIError(Exception):
    pass


class ShopifyClient:
    def __init__(self, shop_domain: str, access_token: str, api_version: str):
        normalized_domain = normalize_shop_domain(shop_domain)
        self._endpoint = f"https://{normalized_domain}/admin/api/{api_version}/graphql.json"
        self._headers = {
            "X-Shopify-Access-Token": access_token,
            "Content-Type": "application/json",
        }

    async def _execute(self, query: str, variables: dict | None = None) -> dict:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                self._endpoint,
                json={"query": query, "variables": variables or {}},
                headers=self._headers,
            )
        if response.status_code != 200:
            raise ShopifyAPIError(
                f"Shopify API returned HTTP {response.status_code}: {response.text[:500]}"
            )
        payload = response.json()
        if "errors" in payload:
            raise ShopifyAPIError(str(payload["errors"]))
        return payload["data"]

    async def _paginate(
        self, query: str, connection_key: str, page_size: int = 50
    ) -> list[dict]:
        nodes: list[dict] = []
        cursor: str | None = None
        while True:
            data = await self._execute(query, {"first": page_size, "after": cursor})
            connection = data[connection_key]
            for edge in connection["edges"]:
                nodes.append(edge["node"])
            page_info = connection["pageInfo"]
            if not page_info["hasNextPage"]:
                break
            cursor = page_info["endCursor"]
        return nodes

    # ── Products ─────────────────────────────────────────────────────────────

    async def get_products_full(self) -> list[dict]:
        """Fetch all active products with images, prices, variants, and tags."""
        nodes = await self._paginate(PRODUCTS_FULL_QUERY, "products")
        for node in nodes:
            # Flatten images
            node["images"] = [
                edge["node"] for edge in node["images"]["edges"]
            ]
            # Flatten variants
            node["variants"] = [
                edge["node"] for edge in node["variants"]["edges"]
            ]
            # Flatten price range for convenience
            price_range = node.get("priceRangeV2", {})
            min_price = price_range.get("minVariantPrice", {})
            max_price = price_range.get("maxVariantPrice", {})
            node["min_price"] = float(min_price.get("amount", 0))
            node["max_price"] = float(max_price.get("amount", 0))
            node["currency"] = min_price.get("currencyCode", "USD")
            node["description_text"] = strip_html(node.get("descriptionHtml", ""))
        return nodes

    # ── Collections ──────────────────────────────────────────────────────────

    async def get_collections(self) -> list[dict]:
        return await self._paginate(COLLECTIONS_QUERY, "collections")

    # ── Pages ────────────────────────────────────────────────────────────────

    async def get_pages(self) -> list[dict]:
        return await self._paginate(PAGES_QUERY, "pages")

    # ── Blogs & Articles ─────────────────────────────────────────────────────

    async def get_blogs_with_articles(self) -> list[dict]:
        return await self._paginate(BLOGS_WITH_ARTICLES_QUERY, "blogs")

    # ── Policies ─────────────────────────────────────────────────────────────

    async def get_policies(self) -> list[dict]:
        data = await self._execute(POLICIES_QUERY)
        return data["shop"]["shopPolicies"]

    # ── Orders ───────────────────────────────────────────────────────────────

    async def lookup_order(self, order_number: str, email: str | None = None) -> list[dict]:
        """
        Look up orders by order name (e.g. '#1001').
        Optionally filter by email for identity verification.
        """
        # Normalise: Shopify stores order name as '#1001'
        name = order_number.strip().lstrip("#")
        query_str = f"name:#{name}"
        if email:
            query_str += f" AND email:{email.strip().lower()}"

        data = await self._execute(ORDER_LOOKUP_QUERY, {"query": query_str})
        orders = []
        for edge in data["orders"]["edges"]:
            node = edge["node"]
            # Flatten line items
            node["lineItems"] = [e["node"] for e in node["lineItems"]["edges"]]
            orders.append(node)
        return orders

    # ── Tickets (via order note as fallback) ─────────────────────────────────

    async def append_order_note(self, order_id: str, note: str) -> dict[str, Any]:
        data = await self._execute(
            CREATE_ORDER_NOTE_MUTATION,
            {"input": {"id": order_id, "note": note}},
        )
        return data.get("orderUpdate", {})
