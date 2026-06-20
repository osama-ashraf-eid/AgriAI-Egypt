import os
import json
import math
import re
import threading
from typing import List, Dict, Tuple, Set
from utils.logger import get_logger

logger = get_logger(__name__)

ARABIC_STOP_WORDS: Set[str] = {
    "من", "في", "على", "إلى", "الى", "عن", "مع", "أن", "ان", "هل", "ما", "ماذا", 
    "كيف", "هو", "هي", "تلك", "ذاك", "هذا", "هذه", "التي", "الذي", "بين", "كل"
}


class EnterpriseFAQRetriever:
    _instance = None
    _lock = threading.Lock()  # 🎯 قفل الخيوط لتأمين الـ Singleton في بيئات الـ Production متعددة الخيوط

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            with cls._lock:  # حماية الدخول المتوازي
                if not cls._instance:
                    cls._instance = super(EnterpriseFAQRetriever, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, file_path: str | None = None):
        if self._initialized:
            return
            
        # 🎯 حل ثغرة الـ Relative Path: بناء مسار مطلق ثابت يبدأ من مكان ملف الـ utils نفسه
        if file_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.file_path = os.path.join(base_dir, "data", "platform_faq.json")
        else:
            self.file_path = file_path

        self.faqs: List[Dict] = []
        self.corpus_terms: List[List[str]] = []
        self.doc_tfs: List[Dict[str, float]] = []
        self.idfs: Dict[str, float] = {}
        self.doc_lengths: List[float] = []
        
        self._load_and_index_corpus()
        self._initialized = True

    def _normalize(self, text: str) -> str:
        if not text:
            return ""
        text = text.lower().strip()
        text = re.sub(r"[أإآ]", "ا", text)
        text = re.sub(r"ة", "ه", text)
        text = re.sub(r"ى", "ي", text)
        text = re.sub(r"[\u064B-\u0652]", "", text)
        return text

    def _tokenize(self, text: str) -> List[str]:
        normalized = self._normalize(text)
        words = re.findall(r"\w+", normalized)
        return [w for w in words if w not in ARABIC_STOP_WORDS and not w.isdigit()]

    def _load_and_index_corpus(self):
        if not os.path.exists(self.file_path):
            logger.error("faq_retriever.file_not_found_fatal", path=self.file_path)
            return

        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                self.faqs = json.load(f)

            total_docs = len(self.faqs)
            doc_counts_with_term: Dict[str, int] = {}

            for faq in self.faqs:
                rich_text = f"{faq.get('title', '')} { ' '.join(faq.get('keywords', [])) } {faq.get('content', '')}"
                tokens = self._tokenize(rich_text)
                self.corpus_terms.append(tokens)

                tf_dict: Dict[str, float] = {}
                for token in tokens:
                    tf_dict[token] = tf_dict.get(token, 0.0) + 1.0
                
                total_tokens = len(tokens) if tokens else 1
                normalized_tf = {k: v / total_tokens for k, v in tf_dict.items()}
                self.doc_tfs.append(normalized_tf)

                for token in set(tokens):
                    doc_counts_with_term[token] = doc_counts_with_term.get(token, 0) + 1

            for term, count in doc_counts_with_term.items():
                self.idfs[term] = math.log(1.0 + (total_docs / count))

            for tf_vector in self.doc_tfs:
                squared_sum = 0.0
                for term, tf_val in tf_vector.items():
                    tfidf_val = tf_val * self.idfs.get(term, 0.0)
                    squared_sum += tfidf_val ** 2
                self.doc_lengths.append(math.sqrt(squared_sum))

            logger.info("faq_retriever.corpus_indexed_successfully", total_indexed_docs=total_docs, resolved_path=self.file_path)

        except Exception as e:
            logger.error("faq_retriever.indexing_failed", error=str(e))

    def search(self, query: str, top_k: int = 1, threshold: float = 0.15) -> str:
        if not self.faqs or not query:
            return ""

        query_tokens = self._tokenize(query)
        if not query_tokens:
            return ""

        query_tf: Dict[str, float] = {}
        for token in query_tokens:
            query_tf[token] = query_tf.get(token, 0.0) + 1.0
            
        query_len = len(query_tokens)
        query_tfidf = {k: (v / query_len) * self.idfs.get(k, 0.0) for k, v in query_tf.items() if k in self.idfs}
        
        query_magnitude = math.sqrt(sum(val ** 2 for val in query_tfidf.values()))
        if query_magnitude == 0.0:
            return ""

        scores: List[Tuple[float, int]] = []

        for idx, doc_tf in enumerate(self.doc_tfs):
            dot_product = 0.0
            for term, q_tfidf_val in query_tfidf.items():
                if term in doc_tf:
                    doc_tfidf_val = doc_tf[term] * self.idfs.get(term, 0.0)
                    dot_product += q_tfidf_val * doc_tfidf_val

            doc_magnitude = self.doc_lengths[idx]
            if doc_magnitude == 0.0:
                continue

            similarity = dot_product / (query_magnitude * doc_magnitude)
            
            if similarity >= threshold:
                scores.append((similarity, idx))

        if not scores:
            return ""

        scores.sort(key=lambda x: x[0], reverse=True)
        
        matched_chunks = []
        for score, idx in scores[:top_k]:
            faq = self.faqs[idx]
            matched_chunks.append(f"### {faq['title']}\n{faq['content']}")

        logger.info("faq_retriever.vector_search_complete", best_score=round(scores[0][0], 4), matches_found=len(scores))
        return "\n\n".join(matched_chunks)


def retrieve_relevant_faqs(user_query: str) -> str:
    retriever = EnterpriseFAQRetriever()
    return retriever.search(user_query, top_k=2, threshold=0.18)