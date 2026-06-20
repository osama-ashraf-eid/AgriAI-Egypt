"""
transformer.py — FULL cross-entity enrichment.
كل document بيحتوي على كل العلاقات المرتبطة بيه.
"""
from dataclasses import dataclass, field
from .arabic_utils import normalize_arabic


@dataclass
class Document:
    text: str
    metadata: dict = field(default_factory=dict)


# ──────────────────────────────────────────────
# 1. PRODUCT  ← Farmer + Auction + Reviews
# ──────────────────────────────────────────────
class ProductTransformer:
    def transform(self, product: dict,
                  farmer: dict = None,
                  auction: dict = None,
                  bids: list = None,
                  reviews: list = None) -> Document:

        farmer      = farmer or {}
        profile     = farmer.get("farmerProfile", {}) or {}
        bids        = bids or []
        reviews     = reviews or []

        farmer_name = farmer.get("fullName", product.get("farmerName", "غير معروف"))
        farmer_gov  = profile.get("governorate", product.get("governorate", ""))
        farm_name   = profile.get("farmName", "")
        is_verified = "موثق" if farmer.get("isVerified") else "غير موثق"

        # متوسط التقييم
        avg_rating = ""
        if reviews:
            ratings = [r["rating"] for r in reviews if isinstance(r.get("rating"), (int, float))]
            if ratings:
                avg_rating = f"متوسط تقييم المزارع: {round(sum(ratings)/len(ratings), 1)} من 5 "

        # مزاد نشط مع المزايدات
        auction_ctx = "لا يوجد مزاد على هذا المنتج "
        if auction:
            winning_bids = [b for b in bids if b.get("isWinning")]
            top_bidder   = winning_bids[-1].get("bidderName", "") if winning_bids else ""
            auction_ctx  = (
                f"يوجد مزاد نشط على هذا المنتج "
                f"سعر البدء: {auction.get('startingPrice', 0)} جنيه "
                f"السعر الحالي للمزاد: {auction.get('currentPrice', 0)} جنيه "
                f"السعر الاحتياطي: {auction.get('reservePrice', 0)} جنيه "
                f"أعلى مزايد: {top_bidder} "
                f"عدد المزايدات: {len(bids)} "
                f"ينتهي المزاد: {auction.get('endDate', '')} "
                f"حالة المزاد: {auction.get('status', 'Active')} "
            )

        text = normalize_arabic(
            f"منتج: {product.get('name', 'غير معروف')} "
            f"وصف المنتج: {product.get('description', '')} "
            f"اسم المزارع: {farmer_name} "
            f"اسم المزرعة: {farm_name} "
            f"المزارع {is_verified} "
            f"محافظة المنتج: {product.get('governorate', farmer_gov or 'غير محددة')} "
            f"الكمية المتاحة: {product.get('quantity', 0)} {product.get('unit', 'كيلو')} "
            f"سعر الوحدة: {product.get('unitPrice', 0)} جنيه للكيلو "
            f"حالة المنتج: {product.get('status', 'Active')} "
            f"تاريخ الحصاد: {product.get('harvestDate', '')} "
            f"تاريخ انتهاء الصلاحية: {product.get('expiryDate', '')} "
            f"فئة المنتج: {product.get('categoryId', '')} "
            f"{avg_rating}"
            f"{auction_ctx}"
        )

        return Document(
            text=text,
            metadata={
                "doc_type":    "product",
                "id":          str(product.get("id", "")),
                "farmer_id":   str(product.get("farmerId", "")),
                "governorate": str(product.get("governorate", "")),
                "category_id": str(product.get("categoryId", "")),
                "status":      str(product.get("status", "Active")),
                "has_auction": "true" if auction else "false",
            }
        )


# ──────────────────────────────────────────────
# 2. AUCTION  ← Product + Bids (Winners & Losers)
# ──────────────────────────────────────────────
class AuctionTransformer:
    def transform(self, auction: dict,
                  product: dict = None,
                  bids: list = None) -> Document:

        product = product or {}
        bids    = bids or []

        # فصل الفائزين عن الخاسرين
        winning_bids = [b for b in bids if b.get("isWinning")]
        losing_bids  = [b for b in bids if not b.get("isWinning")]

        winners_text = " | ".join(
            [f"{b.get('bidderName', '?')} (مزايدة: {b.get('amount', 0)} جنيه)" for b in winning_bids]
        ) or "لا يوجد فائز بعد"

        losers_text = " | ".join(
            [f"{b.get('bidderName', '?')} (مزايدة: {b.get('amount', 0)} جنيه)" for b in losing_bids]
        ) or "لا يوجد مزايدات خاسرة"

        all_bidders = " | ".join(
            [f"{b.get('bidderName', '?')}: {b.get('amount', 0)} جنيه {'(فائز)' if b.get('isWinning') else '(خاسر)'}"
             for b in sorted(bids, key=lambda x: x.get("amount", 0), reverse=True)]
        ) or "لا توجد مزايدات"

        # نحدد الفائز النهائي من winnerId في الأوكشن أو من isWinning في الـ bids
        winner_id   = auction.get("winnerId", "")
        winner_name = ""
        if winner_id:
            for b in bids:
                if b.get("bidderId") == winner_id:
                    winner_name = b.get("bidderName", "")
                    break
        if not winner_name and winning_bids:
            winner_name = winning_bids[-1].get("bidderName", "")

        text = normalize_arabic(
            f"مزاد على منتج: {auction.get('productName', 'غير معروف')} "
            f"وصف المنتج: {product.get('description', '')} "
            f"الكمية: {product.get('quantity', 0)} {product.get('unit', 'كيلو')} "
            f"اسم المزارع: {auction.get('farmerName', 'غير معروف')} "
            f"سعر البدء: {auction.get('startingPrice', 0)} جنيه "
            f"السعر الاحتياطي: {auction.get('reservePrice', 0)} جنيه "
            f"السعر الحالي: {auction.get('currentPrice', 0)} جنيه "
            f"حالة المزاد: {auction.get('status', 'Active')} "
            f"تاريخ البداية: {auction.get('startDate', '')} "
            f"تاريخ الانتهاء: {auction.get('endDate', '')} "
            f"عدد المزايدات الكلي: {len(bids)} "
            f"الفائز بالمزاد: {winner_name or 'لم يُحدد بعد'} "
            f"معرف الفائز: {winner_id or 'لا يوجد'} "
            f"قائمة الفائزين: {winners_text} "
            f"قائمة الخاسرين: {losers_text} "
            f"كل المزايدات: {all_bidders} "
        )

        return Document(
            text=text,
            metadata={
                "doc_type":   "auction",
                "id":         str(auction.get("id", "")),
                "product_id": str(auction.get("productId", "")),
                "farmer_id":  str(auction.get("farmerId", "")),
                "status":     str(auction.get("status", "Active")),
                "has_winner": "true" if winner_name else "false",
            }
        )


# ──────────────────────────────────────────────
# 3. BID  ← Auction + Product + Bidder (مفرد لكل مزايدة)
# ──────────────────────────────────────────────
class BidTransformer:
    def transform(self, bid: dict,
                  auction: dict = None,
                  product: dict = None) -> Document:

        auction = auction or {}
        product = product or {}

        outcome = "فاز بالمزاد" if bid.get("isWinning") else "خسر المزاد"

        text = normalize_arabic(
            f"مزايدة بواسطة: {bid.get('bidderName', 'غير معروف')} "
            f"معرف المزايد: {bid.get('bidderId', '')} "
            f"مبلغ المزايدة: {bid.get('amount', 0)} جنيه "
            f"نتيجة المزايدة: {outcome} "
            f"المزايد {outcome} في مزاد: {auction.get('productName', product.get('name', 'غير معروف'))} "
            f"المزارع صاحب المنتج: {auction.get('farmerName', '')} "
            f"وصف المنتج: {product.get('description', '')} "
            f"الكمية: {product.get('quantity', 0)} {product.get('unit', 'كيلو')} "
            f"السعر الابتدائي للمزاد: {auction.get('startingPrice', 0)} جنيه "
            f"السعر النهائي للمزاد: {auction.get('currentPrice', 0)} جنيه "
            f"حالة المزاد: {auction.get('status', '')} "
            f"وقت المزايدة: {bid.get('bidTime', '')} "
            f"معرف المزاد: {bid.get('auctionId', '')} "
        )

        return Document(
            text=text,
            metadata={
                "doc_type":   "bid",
                "id":         str(bid.get("id", "")),
                "auction_id": str(bid.get("auctionId", "")),
                "bidder_id":  str(bid.get("bidderId", "")),
                "is_winning": "true" if bid.get("isWinning") else "false",
                "product_id": str(auction.get("productId", "")),
            }
        )


# ──────────────────────────────────────────────
# 4. ORDER  ← Items + Logistics + Payment + Product
# ──────────────────────────────────────────────
class OrderTransformer:
    def transform(self, order: dict, products_map: dict = None) -> Document:
        products_map = products_map or {}
        items        = order.get("items", [])
        logistics    = order.get("logistics", {}) or {}
        payment      = order.get("payment", {}) or {}

        items_text = ""
        for item in items:
            pid      = item.get("productId", "")
            p        = products_map.get(pid, {})
            p_name   = item.get("productName", p.get("name", "منتج"))
            qty      = item.get("quantity", 0)
            price    = item.get("unitPriceAtOrder", 0)
            subtotal = item.get("subtotal", qty * price)
            items_text += (
                f"منتج: {p_name} "
                f"الكمية: {qty} كيلو "
                f"السعر عند الطلب: {price} جنيه للكيلو "
                f"الإجمالي الجزئي: {subtotal} جنيه | "
            )

        driver     = logistics.get("driverName") or "لم يُحدد السائق بعد"
        drv_phone  = logistics.get("driverPhone") or "لا يوجد"
        ship_stat  = logistics.get("status", "NotScheduled")
        est_del    = logistics.get("estimatedDelivery") or "لم يُحدد"
        actual_del = logistics.get("actualDelivery") or "لم يُسلَّم بعد"

        pay_method = payment.get("method", "غير محدد")
        pay_status = payment.get("status", "غير محدد")
        pay_amount = payment.get("amount", order.get("totalAmount", 0))
        paid_at    = payment.get("paidAt") or "لم يُدفع بعد"

        addr = order.get("deliveryAddress", {}) or {}

        text = normalize_arabic(
            f"طلب رقم: {order.get('id', '')} "
            f"المشتري: {order.get('buyerName', 'غير معروف')} "
            f"معرف المشتري: {order.get('buyerId', '')} "
            f"معرف المزارع: {order.get('farmerId', '')} "
            f"تفاصيل المنتجات: {items_text} "
            f"إجمالي قيمة الطلب: {order.get('totalAmount', 0)} جنيه "
            f"حالة الطلب: {order.get('status', 'Pending')} "
            f"حالة الدفع: {pay_status} "
            f"طريقة الدفع: {pay_method} "
            f"المبلغ المدفوع: {pay_amount} جنيه "
            f"تاريخ الدفع: {paid_at} "
            f"اسم السائق: {driver} "
            f"هاتف السائق: {drv_phone} "
            f"حالة الشحن: {ship_stat} "
            f"موعد التسليم المتوقع: {est_del} "
            f"تاريخ التسليم الفعلي: {actual_del} "
            f"مدينة التسليم: {addr.get('city', '')} "
            f"محافظة التسليم: {addr.get('governorate', '')} "
            f"شارع التسليم: {addr.get('street', '')} "
            f"ملاحظات: {order.get('notes', '')} "
            f"تاريخ إنشاء الطلب: {order.get('createdAt', '')} "
        )

        return Document(
            text=text,
            metadata={
                "doc_type":       "order",
                "id":             str(order.get("id", "")),
                "buyer_id":       str(order.get("buyerId", "")),
                "farmer_id":      str(order.get("farmerId", "")),
                "status":         str(order.get("status", "Pending")),
                "payment_status": str(payment.get("status", "Unpaid")),
            }
        )


# ──────────────────────────────────────────────
# 5. REVIEW  ← Order + Products
# ──────────────────────────────────────────────
class ReviewTransformer:
    def transform(self, review: dict, order: dict = None) -> Document:
        order_products = ""
        if order:
            for item in order.get("items", []):
                order_products += f"{item.get('productName', '')} "

        text = normalize_arabic(
            f"تقييم للمزارع: {review.get('targetFarmerName', 'غير معروف')} "
            f"معرف المزارع المُقيَّم: {review.get('targetFarmerId', '')} "
            f"اسم المُقيِّم: {review.get('reviewerName', '')} "
            f"معرف المُقيِّم: {review.get('reviewerId', '')} "
            f"رقم الطلب المُقيَّم: {review.get('orderId', '')} "
            f"المنتجات التي تم تقييمها: {order_products.strip() or 'غير محدد'} "
            f"درجة التقييم: {review.get('rating', 0)} من 5 نجوم "
            f"تعليق التقييم: {review.get('comment', '')} "
            f"التقييم معتمد: {'نعم' if review.get('isApproved') else 'لا'} "
            f"تاريخ التقييم: {review.get('createdAt', '')} "
        )

        return Document(
            text=text,
            metadata={
                "doc_type":    "review",
                "id":          str(review.get("id", "")),
                "farmer_id":   str(review.get("targetFarmerId", "")),
                "reviewer_id": str(review.get("reviewerId", "")),
                "order_id":    str(review.get("orderId", "")),
                "rating":      str(review.get("rating", 0)),
            }
        )


# ──────────────────────────────────────────────
# 6. FARMER  ← Products + Reviews + Orders + Bids activity
# ──────────────────────────────────────────────
class FarmerTransformer:
    def transform(self, farmer: dict,
                  products: list = None,
                  reviews: list = None,
                  orders: list = None) -> Document:

        profile  = farmer.get("farmerProfile", {}) or {}
        products = products or []
        reviews  = reviews or []
        orders   = orders or []

        product_names  = "، ".join([p.get("name", "") for p in products[:10]]) or "لا توجد منتجات"
        active_prods   = [p for p in products if p.get("status") == "Active"]
        total_qty      = sum(p.get("quantity", 0) for p in active_prods)

        price_list     = [p.get("unitPrice", 0) for p in active_prods if p.get("unitPrice")]
        avg_price      = round(sum(price_list) / len(price_list), 1) if price_list else 0
        min_price      = min(price_list) if price_list else 0
        max_price      = max(price_list) if price_list else 0

        avg_rating = 0.0
        rating_count = 0
        if reviews:
            ratings      = [r["rating"] for r in reviews if isinstance(r.get("rating"), (int, float))]
            rating_count = len(ratings)
            avg_rating   = round(sum(ratings) / len(ratings), 1) if ratings else 0

        review_comments = " | ".join([r.get("comment", "") for r in reviews[:3]])

        total_orders     = len(orders)
        delivered_orders = len([o for o in orders if o.get("status") == "Delivered"])
        total_revenue    = sum(o.get("totalAmount", 0) for o in orders)

        text = normalize_arabic(
            f"مزارع: {farmer.get('fullName', 'غير معروف')} "
            f"معرف المزارع: {farmer.get('id', '')} "
            f"اسم المزرعة: {profile.get('farmName', '')} "
            f"وصف المزرعة: {profile.get('description', '')} "
            f"محافظة المزرعة: {profile.get('governorate', '')} "
            f"مساحة المزرعة: {profile.get('farmSize', '')} فدان "
            f"المزارع {'موثق ومعتمد' if farmer.get('isVerified') else 'غير موثق'} "
            f"تاريخ الانضمام للمنصة: {farmer.get('joinDate', '')} "
            f"المحاصيل المعروضة: {product_names} "
            f"عدد المنتجات النشطة: {len(active_prods)} منتج "
            f"إجمالي الكميات المتاحة: {total_qty} كيلو "
            f"متوسط سعر البيع: {avg_price} جنيه للكيلو "
            f"أقل سعر: {min_price} جنيه | أعلى سعر: {max_price} جنيه "
            f"متوسط التقييم: {avg_rating} من 5 نجوم "
            f"عدد التقييمات: {rating_count} تقييم "
            f"تعليقات المشترين: {review_comments or 'لا توجد تعليقات'} "
            f"عدد الطلبات الكلي: {total_orders} طلب "
            f"عدد الطلبات المسلمة: {delivered_orders} طلب "
            f"إجمالي المبيعات: {total_revenue} جنيه "
        )

        return Document(
            text=text,
            metadata={
                "doc_type":    "farmer",
                "id":          str(farmer.get("id", "")),
                "governorate": str(profile.get("governorate", "")),
                "is_verified": "true" if farmer.get("isVerified") else "false",
            }
        )
