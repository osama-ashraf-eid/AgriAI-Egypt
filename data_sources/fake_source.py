import json
from pathlib import Path
from typing import Optional
from .base import BaseDataSource

DATA_DIR = Path(__file__).parent / "fake_data"


def _load(name: str) -> list:
    path = DATA_DIR / f"{name}.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


class FakeDataSource(BaseDataSource):

    async def get_products(
        self,
        governorate: Optional[str] = None,
        category_id: Optional[str] = None,
        farmer_id: Optional[str] = None,
        status: Optional[str] = "Active",
    ) -> list[dict]:
        items = _load("products")
        if governorate:
            items = [p for p in items if p.get("governorate") == governorate]
        if category_id:
            items = [p for p in items if p.get("categoryId") == category_id]
        if farmer_id:
            items = [p for p in items if p.get("farmerId") == farmer_id]
        if status:
            items = [p for p in items if p.get("status") == status]
        return items

    async def get_product_by_id(self, product_id: str) -> Optional[dict]:
        for p in _load("products"):
            if p["id"] == product_id:
                return p
        return None

    async def get_categories(self) -> list[dict]:
        return [
            {"id": "cat-001", "name": "Vegetables", "nameAr": "خضروات"},
            {"id": "cat-002", "name": "Tomatoes",   "nameAr": "طماطم وفليفلة"},
            {"id": "cat-003", "name": "Fruits",     "nameAr": "فاكهة"},
            {"id": "cat-004", "name": "Grains",     "nameAr": "حبوب"},
        ]

    async def get_auctions(self, status: Optional[str] = "Active") -> list[dict]:
        items = _load("auctions")
        if status:
            items = [a for a in items if a.get("status") == status]
        return items

    async def get_auction_by_id(self, auction_id: str) -> Optional[dict]:
        for a in _load("auctions"):
            if a["id"] == auction_id:
                return a
        return None

    async def get_bids(self, auction_id: str) -> list[dict]:
        return [b for b in _load("bids") if b.get("auctionId") == auction_id]

    async def get_orders(
        self,
        buyer_id: Optional[str] = None,
        farmer_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> list[dict]:
        items = _load("orders")
        if buyer_id:
            items = [o for o in items if o.get("buyerId") == buyer_id]
        if farmer_id:
            items = [o for o in items if o.get("farmerId") == farmer_id]
        if status:
            items = [o for o in items if o.get("status") == status]
        return items

    async def get_order_by_id(self, order_id: str) -> Optional[dict]:
        for o in _load("orders"):
            if o["id"] == order_id:
                return o
        return None

    async def get_order_items(self, order_id: str) -> list[dict]:
        order = await self.get_order_by_id(order_id)
        return order.get("items", []) if order else []

    async def get_payment(self, order_id: str) -> Optional[dict]:
        order = await self.get_order_by_id(order_id)
        return order.get("payment") if order else None

    async def get_logistics(self, order_id: str) -> Optional[dict]:
        order = await self.get_order_by_id(order_id)
        return order.get("logistics") if order else None

    async def get_farmers(self, governorate: Optional[str] = None) -> list[dict]:
        users = [u for u in _load("users") if u.get("role") == "Farmer"]
        if governorate:
            users = [
                u for u in users
                if u.get("farmerProfile", {}).get("governorate") == governorate
            ]
        return users

    async def get_trader_by_id(self, user_id: str) -> Optional[dict]:
        for u in _load("users"):
            if u["id"] == user_id and u.get("role") == "Trader":
                return u
        return None

    async def get_farmer_profile(self, user_id: str) -> Optional[dict]:
        for u in _load("users"):
            if u["id"] == user_id and u.get("role") == "Farmer":
                return u
        return None

    async def get_reviews(self, farmer_id: Optional[str] = None) -> list[dict]:
        items = _load("reviews")
        if farmer_id:
            items = [r for r in items if r.get("targetFarmerId") == farmer_id]
        return items

    async def get_marketplace_stats(self) -> dict:
        products = _load("products")
        auctions = _load("auctions")
        orders   = _load("orders")

        gov_count = {}
        cat_count = {}
        price_sum = {}
        price_cnt = {}

        for p in products:
            if p.get("status") == "Active":
                gov = p.get("governorate", "غير محدد")
                cat = p.get("categoryId", "غير محدد")
                price = float(p.get("unitPrice", 0))

                gov_count[gov] = gov_count.get(gov, 0) + 1
                cat_count[cat] = cat_count.get(cat, 0) + 1
                price_sum[cat] = price_sum.get(cat, 0) + price
                price_cnt[cat] = price_cnt.get(cat, 0) + 1

        avg_price = {cat: round(price_sum[cat] / price_cnt[cat], 2) for cat in price_sum}
        top_govs = sorted(gov_count.items(), key=lambda x: x[1], reverse=True)
        top_cats = sorted(cat_count.items(), key=lambda x: x[1], reverse=True)

        return {
            "total_products": len([p for p in products if p.get("status") == "Active"]),
            "total_active_auctions": len([a for a in auctions if a.get("status") == "Active"]),
            "total_orders": len(orders),
            "top_governorates": [{"name": g, "count": c} for g, c in top_govs[:5]],
            "top_categories": [{"id": c, "count": n} for c, n in top_cats[:5]],
            "avg_price_by_category": avg_price,
        }