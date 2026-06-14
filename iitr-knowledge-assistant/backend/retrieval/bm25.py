import re
import math

def tokenize(text: str) -> list[str]:
    # Fix letter-digit concatenation typos from PDF extraction (e.g. of6.0 -> of 6.0)
    cleaned = re.sub(r"([a-zA-Z])([0-9])", r"\1 \2", text)
    cleaned = re.sub(r"([0-9])([a-zA-Z])", r"\1 \2", cleaned)
    # Match words, allowing internal dots/hyphens (e.g. R.7, CSIR-NET, A.3)
    return re.findall(r"\b\w+(?:[.-]\w+)*\b", cleaned.lower())

class BM25Okapi:
    def __init__(self, corpus: list[str], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus_size = len(corpus)
        self.doc_lens = []
        self.doc_term_freqs = []
        self.nd = {}  # term -> number of docs containing term
        
        for doc in corpus:
            tokens = tokenize(doc)
            self.doc_lens.append(len(tokens))
            
            freqs = {}
            for t in tokens:
                freqs[t] = freqs.get(t, 0) + 1
            self.doc_term_freqs.append(freqs)
            
            for t in freqs:
                self.nd[t] = self.nd.get(t, 0) + 1
                
        self.avg_doc_len = sum(self.doc_lens) / self.corpus_size if self.corpus_size > 0 else 0
        
        # Precompute IDF
        self.idf = {}
        for term, freq in self.nd.items():
            self.idf[term] = math.log((self.corpus_size - freq + 0.5) / (freq + 0.5) + 1.0)
            
    def get_scores(self, query: str) -> list[float]:
        query_tokens = tokenize(query)
        scores = []
        for doc_idx in range(self.corpus_size):
            score = 0.0
            freqs = self.doc_term_freqs[doc_idx]
            doc_len = self.doc_lens[doc_idx]
            
            for term in query_tokens:
                if term not in freqs:
                    continue
                tf = freqs[term]
                idf = self.idf.get(term, 0.0)
                numerator = tf * (self.k1 + 1)
                denominator = tf + self.k1 * (1.0 - self.b + self.b * (doc_len / self.avg_doc_len))
                score += idf * (numerator / denominator)
            scores.append(score)
        return scores

    def search(self, query: str, chunks: list[dict], top_k: int = 20) -> list[dict]:
        scores = self.get_scores(query)
        scored_chunks = []
        for idx, score in enumerate(scores):
            if score > 0.0:  # Only retrieve chunks with some keyword overlap
                chunk = chunks[idx]
                scored_chunks.append({
                    "chunk_id": chunk["chunk_id"],
                    "chunk": chunk["text"],
                    "page": chunk["page"],
                    "document": chunk["document"],
                    "doc_type": chunk.get("doc_type", "sop"),
                    "full_page": chunk.get("full_page", chunk["text"]),
                    "index": chunk.get("index", idx),
                    "bm25_score": score,
                })
        scored_chunks.sort(key=lambda x: x["bm25_score"], reverse=True)
        return scored_chunks[:top_k]

_global_bm25: BM25Okapi | None = None

def get_bm25_index(chunks: list[dict], force_rebuild: bool = False) -> BM25Okapi:
    global _global_bm25
    if _global_bm25 is None or force_rebuild:
        corpus = [c.get("text", c.get("chunk", "")) for c in chunks]
        _global_bm25 = BM25Okapi(corpus)
    return _global_bm25

def search_bm25(query: str, chunks: list[dict], top_k: int = 20) -> list[dict]:
    bm25 = get_bm25_index(chunks)
    return bm25.search(query, chunks, top_k=top_k)
