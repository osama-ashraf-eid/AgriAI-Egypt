from abc import ABC, abstractmethod
from typing import Optional


class BaseDataSource(ABC):

    @abstractmethod
    async def get_products(
        self,
        governorate: Optional[str] = None,
        category_id: Optional[str] = None,
        farmer_id: Optional[str] = None,
        status: Optional[str] = "Active",
    ) -> list[dict]:
        pass

    @abstractmethod
    async def get_product_by_id(self, product_id: str) -> Optional[dict]:
        pass

    @abstractmethod
    async def get_categories(self) -> list[dict]:
        pass

    @abstractmethod
    async def get_auctions(self, status: Optional[str] = "Active") -> list[dict]:
        pass

    @abstractmethod
    async def get_auction_by_id(self, auction_id: str) -> Optional[dict]:
        pass

    @abstractmethod
    async def get_bids(self, auction_id: str) -> list[dict]:
        pass

    @abstractmethod
    async def get_orders(
        self,
        buyer_id: Optional[str] = None,
        farmer_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> list[dict]:
        pass

    @abstractmethod
    async def get_order_by_id(self, order_id: str) -> Optional[dict]:
        pass

    @abstractmethod
    async def get_order_items(self, order_id: str) -> list[dict]:
        pass

    @abstractmethod
    async def get_payment(self, order_id: str) -> Optional[dict]:
        pass

    @abstractmethod
    async def get_logistics(self, order_id: str) -> Optional[dict]:
        pass

    @abstractmethod
    async def get_farmers(self, governorate: Optional[str] = None) -> list[dict]:
        pass

    @abstractmethod
    async def get_trader_by_id(self, user_id: str) -> Optional[dict]:
        pass

    @abstractmethod
    async def get_farmer_profile(self, user_id: str) -> Optional[dict]:
        pass

    @abstractmethod
    async def get_reviews(self, farmer_id: Optional[str] = None) -> list[dict]:
        pass

    @abstractmethod
    async def get_marketplace_stats(self) -> dict:
        pass