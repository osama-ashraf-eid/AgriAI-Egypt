---
title: Taawuny AI RAG
emoji: 🌾
colorFrom: green
colorTo: yellow
sdk: docker
pinned: false
license: mit
app_port: 7860
---

# 🌾 Taawuny AI — نظام RAG للمنصة الزراعية

نظام ذكاء اصطناعي لمنصة **تعاوني** الزراعية المصرية، يجيب على أسئلة المزارعين والتجار بدقة من خلال بيانات المنصة الحية.

## المميزات
- 🔗 **ربط كامل بين البيانات**: منتجات ↔ مزارعين ↔ مزادات ↔ طلبات ↔ تقييمات
- 🔍 **Hybrid Retrieval**: Dense (BGE-M3) + Sparse (BM25) + RRF Fusion + Reranker
- 🎯 **Multi-intent routing**: marketplace / auction / order / aggregation / platform_help
- 🗣️ **عامية مصرية تجارية** في الردود

## الـ Endpoints

| Endpoint | Method | الوظيفة |
|----------|--------|---------|
| `/api/v1/health` | GET | فحص حالة النظام |
| `/api/v1/chat` | POST | الـ chat الرئيسي |
| `/api/v1/rag/ingest` | POST | إعادة بناء الـ vector store |
| `/api/v1/rag/status` | GET | إحصائيات الـ RAG |
| `/api/v1/rag/search` | POST | بحث مباشر |
| `/docs` | GET | Swagger UI |

## المتغيرات البيئية

```env
GROQ_API_KEY=gsk_...
GROQ_API_KEYS=key1,key2,key3
USE_FAKE_DATA=true
REAL_API_BASE_URL=https://api.taawuny.com
REAL_API_KEY=...
SECRET_KEY=your-secret
```

## مثال

```bash
curl -X POST https://your-space.hf.space/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "فيه بطاطس في الفيوم؟", "user_id": "user-1", "user_role": "trader"}'
```
