import re
from typing import List
from rag.transformer import Document

class AgriTextChunker:
    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def split_text(self, text: str) -> List[str]:
        if len(text) <= self.chunk_size:
            return [text]

        # التقطيع الذكي بناءً على علامات الترقيم العربية ونهاية الجمل
        sentences = re.split(r'(?<=[.،؟\n])\s+', text)
        chunks = []
        current_chunk = ""

        for sentence in sentences:
            if len(current_chunk) + len(sentence) <= self.chunk_size:
                current_chunk += sentence + " "
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence + " "

        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        return chunks

    def transform_long_document(self, raw_text: str, source_metadata: dict) -> List[Document]:
        text_chunks = self.split_text(raw_text)
        documents = []
        
        for idx, chunk in enumerate(text_chunks):
            meta = source_metadata.copy()
            meta.update({
                "chunk_index": idx,
                "total_chunks": len(text_chunks),
                "doc_type": source_metadata.get("doc_type", "unstructured_guide")
            })
            documents.append(Document(text=chunk, metadata=meta))
            
        return documents