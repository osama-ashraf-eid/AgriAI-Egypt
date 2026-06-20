import httpx
from typing import Optional
from .base import BaseDataSource


class RealApiDataSource(BaseDataSource):

    # ── 🎯 [خريطة الـ Endpoints المركزية] ──
    # بكرة لما تستلم الـ 6 روابط من تيم الباك إند، غير الكلمات دي هنا بس في سطر واحد!
    ROUTES = {
        "products": "/api/products",
        "categories": "/api/categories",
        "auctions": "/api/auctions",
        "orders": "/api/orders",
        "users": "/api/users",
        "analytics": "/api/analytics/marketplace"
    }

    def __init__(self, base_url: str, api_key: str = "") -> None:
        self.base_url = base_url.rstrip("/")
        self.headers = {}
        if api_key:
            self.headers["Authorization"] = f"Bearer {api_key}"

    async def _get(self, path: str, params: dict = None) -> list | dict:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(
                f"{self.base_url}{path}",
                params=params or {},
                headers=self.headers,
            )
            r.raise_for_status()
            return r.json()

    async def get_products(
        self,
        governorate: Optional[str] = None,
        category_id: Optional[str] = None,
        farmer_id: Optional[str] = None,
        status: Optional[str] = "Active",
    ) -> list[dict]:
        params = {}
        if status:      params["status"]      = status
        if governorate: params["governorate"] = governorate
        if category_id: params["categoryId"]  = category_id
        if farmer_id:   params["farmerId"]    = farmer_id
        return await self._get(self.ROUTES["products"], params)

    async def get_product_by_id(self, product_id: str) -> Optional[dict]:
        try:
            return await self._get(f"{self.ROUTES['products']}/{product_id}")
        except httpx.HTTPStatusError:
            return None

    async def get_categories(self) -> list[dict]:
        return await self._get(self.ROUTES["categories"])

    async def get_auctions(self, status: Optional[str] = "Active") -> list[dict]:
        params = {"status": status} if status else {}
        return await self._get(self.ROUTES["auctions"], params)

    async def get_auction_by_id(self, auction_id: str) -> Optional[dict]:
        try:
            return await self._get(f"{self.ROUTES['auctions']}/{auction_id}")
        except httpx.HTTPStatusError:
            return None

    async def get_bids(self, auction_id: str) -> list[dict]:
        return await self._get(f"{self.ROUTES['auctions']}/{auction_id}/bids")

    async def get_orders(
        self,
        buyer_id: Optional[str] = None,
        farmer_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> list[dict]:
        params = {}
        if buyer_id:  params["buyerId"]   = buyer_id
        if farmer_id: params["farmerId"]  = farmer_id
        if status:    params["status"]    = status
        return await self._get(self.ROUTES["orders"], params)

    async def get_order_by_id(self, order_id: str) -> Optional[dict]:
        try:
            return await self._get(f"{self.ROUTES['orders']}/{order_id}")
        except httpx.HTTPStatusError:
            return None

    async def get_order_items(self, order_id: str) -> list[dict]:
        return await self._get(f"{self.ROUTES['orders']}/{order_id}/items")

    async def get_payment(self, order_id: str) -> Optional[dict]:
        try:
            return await self._get(f"{self.ROUTES['orders']}/{order_id}/payment")
        except httpx.HTTPStatusError:
            return None

    async def get_logistics(self, order_id: str) -> Optional[dict]:
        try:
            return await self._get(f"{self.ROUTES['orders']}/{order_id}/logistics")
        except httpx.HTTPStatusError:
            return None

    async def get_farmers(self, governorate: Optional[str] = None) -> list[dict]:
        params = {}
        if governorate: params["governorate"] = governorate
        return await self._get(f"{self.ROUTES['users']}/farmers", params)

    async def get_trader_by_id(self, user_id: str) -> Optional[dict]:
        try:
            return await self._get(f"{self.ROUTES['users']}/{user_id}")
        except httpx.HTTPStatusError:
            return None

    async def get_farmer_profile(self, user_id: str) -> Optional[dict]:
        try:
            return await self._get(f"{self.ROUTES['users']}/{user_id}/farmer-profile")
        except httpx.HTTPStatusError:
            return None

    async def get_reviews(self, farmer_id: Optional[str] = None) -> list[dict]:
        params = {}
        if farmer_id: params["targetFarmerId"] = farmer_id
        return await self._get("/api/reviews", params)

    async def get_marketplace_stats(self) -> dict:
        return await self._get(self.ROUTES["analytics"])