"""
pipeline.py — Full ingestion (6 entity types) + multi-collection query + analytics.
"""
import asyncio
from utils.logger import get_logger
from config import settings, get_data_source
from rag.transformer import (
    ProductTransformer, AuctionTransformer, BidTransformer,
    OrderTransformer, ReviewTransformer, FarmerTransformer,
)
from rag.vector_store import get_vector_store

logger = get_logger(__name__)
NO_CONTEXT_MESSAGE = "NO_CONTEXT"


class RAGPipeline:
    def __init__(self):
        self.store  = get_vector_store()
        self.source = get_data_source()

    # ════════════════════════════════════════
    # INGESTION — بناء 6 collections مترابطة
    # ════════════════════════════════════════

    async def _ingest_farmers(self, products_all, reviews_all, orders_all) -> int:
        farmers = await self.source.get_farmers()
        t = FarmerTransformer()
        docs = []
        for f in farmers:
            fid = f["id"]
            docs.append(t.transform(
                f,
                products=[p for p in products_all if p.get("farmerId") == fid],
                reviews =[r for r in reviews_all  if r.get("targetFarmerId") == fid],
                orders  =[o for o in orders_all   if o.get("farmerId") == fid],
            ))
        if docs:
            await asyncio.to_thread(self.store.add_documents, docs)
        logger.info("ingest.farmers", n=len(docs))
        return len(docs)

    async def _ingest_products(self, products_all, farmers_map,
                                auctions_map, bids_by_product, reviews_all) -> int:
        t = ProductTransformer()
        docs = []
        for p in products_all:
            fid     = p.get("farmerId", "")
            pid     = p.get("id", "")
            auction = auctions_map.get(pid)
            a_bids  = bids_by_product.get(pid, [])
            docs.append(t.transform(
                p,
                farmer  = farmers_map.get(fid),
                auction = auction,
                bids    = a_bids,
                reviews = [r for r in reviews_all if r.get("targetFarmerId") == fid],
            ))
        if docs:
            await asyncio.to_thread(self.store.add_documents, docs)
        logger.info("ingest.products", n=len(docs))
        return len(docs)

    async def _ingest_auctions(self, auctions_all, products_map, bids_all) -> int:
        t = AuctionTransformer()
        docs = []
        for a in auctions_all:
            aid  = a["id"]
            pid  = a.get("productId", "")
            bids = [b for b in bids_all if b.get("auctionId") == aid]
            docs.append(t.transform(
                a,
                product = products_map.get(pid),
                bids    = bids,
            ))
        if docs:
            await asyncio.to_thread(self.store.add_documents, docs)
        logger.info("ingest.auctions", n=len(docs))
        return len(docs)

    async def _ingest_bids(self, bids_all, auctions_map, products_map) -> int:
        """كل bid بيتحول لـ document مستقل — ده اللي كان مش موجود"""
        t = BidTransformer()
        docs = []
        for b in bids_all:
            aid     = b.get("auctionId", "")
            auction = auctions_map.get(aid, {})
            pid     = auction.get("productId", "")
            docs.append(t.transform(
                b,
                auction = auction,
                product = products_map.get(pid),
            ))
        if docs:
            await asyncio.to_thread(self.store.add_documents, docs)
        logger.info("ingest.bids", n=len(docs))
        return len(docs)

    async def _ingest_orders(self, orders_all, products_map) -> int:
        t = OrderTransformer()
        docs = []
        for o in orders_all:
            docs.append(t.transform(o, products_map=products_map))
        if docs:
            await asyncio.to_thread(self.store.add_documents, docs)
        logger.info("ingest.orders", n=len(docs))
        return len(docs)

    async def _ingest_reviews(self, reviews_all, orders_map) -> int:
        t = ReviewTransformer()
        docs = []
        for r in reviews_all:
            order = orders_map.get(r.get("orderId", ""))
            docs.append(t.transform(r, order=order))
        if docs:
            await asyncio.to_thread(self.store.add_documents, docs)
        logger.info("ingest.reviews", n=len(docs))
        return len(docs)

    async def ingest_all(self, force_rebuild: bool = False) -> dict:
        if force_rebuild:
            logger.info("ingest.clearing_store")
            await asyncio.to_thread(self.store.clear_all)

        # ─── سحب كل البيانات مرة واحدة (batch fetch) ───
        products_all = await self.source.get_products(status=None)
        auctions_all = await self.source.get_auctions(status=None)
        orders_all   = await self.source.get_orders()
        reviews_all  = await self.source.get_reviews()
        farmers_all  = await self.source.get_farmers()

        # سحب كل الـ bids لكل المزادات
        bids_all = []
        for a in auctions_all:
            bids_all.extend(await self.source.get_bids(a["id"]))

        # ─── Lookup maps لـ O(1) access ───
        farmers_map      = {f["id"]: f for f in farmers_all}
        products_map     = {p["id"]: p for p in products_all}
        auctions_map     = {a["id"]: a for a in auctions_all}
        orders_map       = {o["id"]: o for o in orders_all}
        # map: productId → auction
        auction_by_prod  = {a["productId"]: a for a in auctions_all}
        # map: productId → list of bids
        bids_by_product  = {}
        for b in bids_all:
            aid = b.get("auctionId", "")
            a   = auctions_map.get(aid, {})
            pid = a.get("productId", "")
            bids_by_product.setdefault(pid, []).append(b)

        # ─── Ingest بالترتيب الصح ───
        counts = {}
        counts["farmers"]  = await self._ingest_farmers(products_all, reviews_all, orders_all)
        counts["products"] = await self._ingest_products(
            products_all, farmers_map, auction_by_prod, bids_by_product, reviews_all
        )
        counts["auctions"] = await self._ingest_auctions(auctions_all, products_map, bids_all)
        counts["bids"]     = await self._ingest_bids(bids_all, auctions_map, products_map)
        counts["orders"]   = await self._ingest_orders(orders_all, products_map)
        counts["reviews"]  = await self._ingest_reviews(reviews_all, orders_map)

        total = sum(counts.values())
        logger.info("ingest.done", total=total, breakdown=counts)

        await self._rebuild_bm25()
        return counts

    async def _rebuild_bm25(self):
        from rag.retriever import update_bm25_corpus
        try:
            col   = self.store.collection
            total = col.count()
            if total == 0:
                return
            all_docs = []
            batch    = 500
            for offset in range(0, total, batch):
                res = col.get(limit=batch, offset=offset,
                              include=["documents", "metadatas"])
                for text, meta in zip(res["documents"], res["metadatas"]):
                    all_docs.append({"text": text, "metadata": meta or {}})
            update_bm25_corpus(all_docs)
            logger.info("bm25.rebuilt", size=len(all_docs))
        except Exception as e:
            logger.error("bm25.rebuild_failed", error=str(e))

    # ════════════════════════════════════════
    # QUERY — بحث في نوع واحد أو أكتر
    # ════════════════════════════════════════

    def query(
        self,
        clean_query: str,
        keywords: list[str] = None,
        doc_type: str = None,            # None = كل الأنواع
        doc_types: list[str] = None,     # قائمة أنواع متعددة
        top_k: int = None,
        governorate: str = None,
        extra_filters: dict = None,
        use_reranker: bool = True,
        intent: str = "marketplace",
        min_score: float = None,
    ) -> tuple[list[dict], str]:
        from rag.retriever import retrieve

        # لو في doc_types بيعمل union من كل type
        if doc_types and len(doc_types) > 1:
            return self._query_multi(
                clean_query=clean_query,
                keywords=keywords,
                doc_types=doc_types,
                top_k=top_k,
                governorate=governorate,
                extra_filters=extra_filters,
                use_reranker=use_reranker,
                intent=intent,
                min_score=min_score,
            )

        # single-type query
        effective_type = doc_type or (doc_types[0] if doc_types else None)
        where = self._build_where(
            doc_type=effective_type,
            governorate=governorate,
            extra_filters=extra_filters,
        )

        results = retrieve(
            query=clean_query,
            keywords=keywords,
            top_k=top_k or settings.RERANK_TOP_K,
            where=where,
            use_reranker=use_reranker,
            min_score=min_score or settings.MIN_RERANK_SCORE,
        )

        return results, self._build_context(results, intent=intent)

    def _query_multi(
        self,
        clean_query: str,
        keywords: list[str],
        doc_types: list[str],
        top_k: int,
        governorate: str,
        extra_filters: dict,
        use_reranker: bool,
        intent: str,
        min_score: float,
    ) -> tuple[list[dict], str]:
        """بيدور في أكتر من collection ويعمل merge للنتائج."""
        from rag.retriever import retrieve

        per_type_k = max(4, (top_k or settings.RERANK_TOP_K))
        all_results = []

        for dt in doc_types:
            where = self._build_where(
                doc_type=dt,
                governorate=governorate,
                extra_filters=None,   # extra_filters بس على نوع واحد
            )
            res = retrieve(
                query=clean_query,
                keywords=keywords,
                top_k=per_type_k,
                where=where,
                use_reranker=use_reranker,
                min_score=min_score or settings.MIN_RERANK_SCORE,
            )
            all_results.extend(res)

        # re-sort المجموع بالـ rerank score أو score
        all_results.sort(
            key=lambda x: x.get("rerank_score", x.get("score", 0)),
            reverse=True
        )
        final = all_results[:top_k or settings.RERANK_TOP_K]
        return final, self._build_context(final, intent=intent)

    def _build_where(
        self,
        doc_type: str = None,
        governorate: str = None,
        extra_filters: dict = None,
    ) -> dict | None:
        clauses = []
        if doc_type:
            clauses.append({"doc_type": {"$eq": doc_type}})
        if governorate:
            clauses.append({"governorate": {"$eq": governorate}})
        if extra_filters:
            for k, v in extra_filters.items():
                clauses.append({k: {"$eq": str(v)}})

        if not clauses:
            return None
        if len(clauses) == 1:
            return clauses[0]
        return {"$and": clauses}

    def _build_context(self, results: list[dict], intent: str = "marketplace") -> str:
        if not results:
            return NO_CONTEXT_MESSAGE
        return "\n\n".join(f"[{i}] {r['text']}" for i, r in enumerate(results, 1))

    # ════════════════════════════════════════
    # ANALYTICS — إحصائيات شاملة
    # ════════════════════════════════════════

    async def query_analytics(self, governorate: str = None) -> tuple[list, str]:
        try:
            products_all = await self.source.get_products(status=None, governorate=governorate)
            auctions_all = await self.source.get_auctions(status=None)
            orders_all   = await self.source.get_orders()
            farmers_all  = await self.source.get_farmers()
            reviews_all  = await self.source.get_reviews()
            bids_all     = []
            for a in auctions_all:
                bids_all.extend(await self.source.get_bids(a["id"]))
        except Exception as e:
            logger.error("analytics.fetch_failed", error=str(e))
            return [], NO_CONTEXT_MESSAGE

        active_prods  = [p for p in products_all if p.get("status") == "Active"]
        active_aucts  = [a for a in auctions_all if a.get("status") == "Active"]
        pending_ords  = [o for o in orders_all   if o.get("status") == "Pending"]
        delivered_ords= [o for o in orders_all   if o.get("status") == "Delivered"]
        verified_farm = [f for f in farmers_all  if f.get("isVerified")]
        winning_bids  = [b for b in bids_all     if b.get("isWinning")]
        losing_bids   = [b for b in bids_all     if not b.get("isWinning")]

        total_rev   = sum(o.get("totalAmount", 0) for o in orders_all)
        avg_ord     = round(total_rev / len(orders_all), 1) if orders_all else 0

        price_list  = [(p.get("name", "?"), p.get("unitPrice", 0), p.get("governorate", "?"))
                       for p in active_prods if p.get("unitPrice")]
        cheapest    = min(price_list, key=lambda x: x[1]) if price_list else None
        priciest    = max(price_list, key=lambda x: x[1]) if price_list else None
        qty_list    = [(p.get("name", "?"), p.get("quantity", 0)) for p in active_prods]
        max_qty     = max(qty_list, key=lambda x: x[1]) if qty_list else None
        total_qty   = sum(q for _, q in qty_list)

        avg_rating = 0.0
        if reviews_all:
            ratings    = [r["rating"] for r in reviews_all if isinstance(r.get("rating"), (int, float))]
            avg_rating = round(sum(ratings) / len(ratings), 1) if ratings else 0

        # توزيع المحافظات
        gov_map = {}
        for p in active_prods:
            g = p.get("governorate", "غير محدد")
            gov_map.setdefault(g, {"products": 0, "qty": 0})
            gov_map[g]["products"] += 1
            gov_map[g]["qty"]      += p.get("quantity", 0)
        gov_lines = "\n".join(
            f"  - {g}: {v['products']} منتج | {v['qty']} كيلو"
            for g, v in sorted(gov_map.items(), key=lambda x: x[1]["products"], reverse=True)
        )

        # top مزارعين بالتقييم
        farm_ratings = {}
        for r in reviews_all:
            fid = r.get("targetFarmerId", "")
            fname = r.get("targetFarmerName", "؟")
            farm_ratings.setdefault(fid, {"name": fname, "ratings": []})
            farm_ratings[fid]["ratings"].append(r.get("rating", 0))
        top_farmers = sorted(
            [(v["name"], round(sum(v["ratings"])/len(v["ratings"]), 1), len(v["ratings"]))
             for v in farm_ratings.values() if v["ratings"]],
            key=lambda x: x[1], reverse=True
        )
        top_farmers_text = " | ".join(
            [f"{name}: {avg} من 5 ({count} تقييم)" for name, avg, count in top_farmers[:5]]
        ) or "لا توجد تقييمات"

        context = f"""
── إحصائيات منصة تعاوني الزراعية الشاملة ──

📦 المنتجات:
- إجمالي المنتجات النشطة: {len(active_prods)}
- إجمالي الكميات المعروضة: {total_qty} كيلو
- أرخص منتج: {f"{cheapest[0]} بـ {cheapest[1]} جنيه من {cheapest[2]}" if cheapest else "غير متاح"}
- أغلى منتج: {f"{priciest[0]} بـ {priciest[1]} جنيه من {priciest[2]}" if priciest else "غير متاح"}
- أكبر كمية: {f"{max_qty[0]}: {max_qty[1]} كيلو" if max_qty else "غير متاح"}

⏱️ المزادات:
- المزادات النشطة الآن: {len(active_aucts)}
- إجمالي المزادات: {len(auctions_all)}
- إجمالي المزايدات: {len(bids_all)}
- مزايدات فائزة: {len(winning_bids)} | خاسرة: {len(losing_bids)}

📋 الطلبات:
- إجمالي الطلبات: {len(orders_all)}
- معلقة: {len(pending_ords)} | مسلمة: {len(delivered_ords)}
- إجمالي الإيرادات: {total_rev} جنيه
- متوسط قيمة الطلب: {avg_ord} جنيه

👤 المزارعون:
- إجمالي المزارعين: {len(farmers_all)}
- موثقون ومعتمدون: {len(verified_farm)}
- إجمالي التقييمات: {len(reviews_all)}
- متوسط تقييم المزارعين: {avg_rating} من 5
- أفضل المزارعين بالتقييم: {top_farmers_text}

📍 توزيع المنتجات بالمحافظات:
{gov_lines}
""".strip()

        return products_all, context


def get_pipeline() -> RAGPipeline:
    return RAGPipeline()
