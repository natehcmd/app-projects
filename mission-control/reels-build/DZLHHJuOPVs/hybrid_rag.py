#!/usr/bin/env python3
"""
hybrid_rag.py — a small, self-contained hybrid-search RAG pipeline.

Built from portfolio idea #1 in the source reel: "RAG pipeline with hybrid
search (dense + sparse retrieval), reranking, and eval metrics — not just a
basic vector DB wrapper."

What it does:
  1. Sparse retrieval  — BM25 (Okapi), implemented from scratch.
  2. Dense retrieval   — TF-IDF cosine similarity by default (pure stdlib +
                          numpy, no downloads). If `sentence-transformers` is
                          installed, pass --dense-model to use real semantic
                          embeddings instead — same interface, better recall.
  3. Fusion            — Reciprocal Rank Fusion (RRF) combines the two
                          ranked lists into one.
  4. Reranking         — a lightweight cross-encoder-style reranker (query/
                          doc term-overlap + BM25 signal) re-scores the
                          fused top-k. Swap in a real cross-encoder by
                          replacing `rerank()`.
  5. Eval metrics      — Recall@k, MRR, and nDCG@k against a qrels file
                          (query -> list of relevant doc ids), the standard
                          way IR/RAG systems are evaluated.

No API keys, no network calls, no external services required to run the
default demo — everything operates on the small local corpus in data/.

Usage:
    python3 hybrid_rag.py                        # run demo eval over data/
    python3 hybrid_rag.py --query "how does BM25 rank documents"
    python3 hybrid_rag.py --docs data/docs.json --qrels data/qrels.json --k 5
"""

import argparse
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path

TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str):
    return TOKEN_RE.findall(text.lower())


# --------------------------------------------------------------------------
# Sparse retrieval: BM25
# --------------------------------------------------------------------------
class BM25:
    def __init__(self, docs, k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.doc_ids = [d["id"] for d in docs]
        self.tokenized = [tokenize(d["text"]) for d in docs]
        self.doc_lens = [len(t) for t in self.tokenized]
        self.avgdl = sum(self.doc_lens) / len(self.doc_lens)
        self.df = Counter()
        for toks in self.tokenized:
            for term in set(toks):
                self.df[term] += 1
        self.n_docs = len(docs)
        self.idf = {
            term: math.log(1 + (self.n_docs - df + 0.5) / (df + 0.5))
            for term, df in self.df.items()
        }
        self.term_freqs = [Counter(t) for t in self.tokenized]

    def score(self, query: str):
        q_terms = tokenize(query)
        scores = [0.0] * self.n_docs
        for i, (tf, dl) in enumerate(zip(self.term_freqs, self.doc_lens)):
            s = 0.0
            for term in q_terms:
                if term not in tf:
                    continue
                idf = self.idf.get(term, 0.0)
                freq = tf[term]
                denom = freq + self.k1 * (1 - self.b + self.b * dl / self.avgdl)
                s += idf * (freq * (self.k1 + 1)) / denom
            scores[i] = s
        return dict(zip(self.doc_ids, scores))


# --------------------------------------------------------------------------
# Dense-ish retrieval: TF-IDF cosine similarity (no model download needed).
# If sentence-transformers is installed and --dense-model is passed, real
# sentence embeddings are used instead via the same rank() interface.
# --------------------------------------------------------------------------
class TfidfDenseRetriever:
    def __init__(self, docs):
        self.doc_ids = [d["id"] for d in docs]
        self.tokenized = [tokenize(d["text"]) for d in docs]
        self.n_docs = len(docs)
        df = Counter()
        for toks in self.tokenized:
            for term in set(toks):
                df[term] += 1
        self.idf = {t: math.log(self.n_docs / c) + 1 for t, c in df.items()}
        self.doc_vecs = [self._vectorize(t) for t in self.tokenized]

    def _vectorize(self, tokens):
        tf = Counter(tokens)
        vec = {t: (c / len(tokens)) * self.idf.get(t, 0.0) for t, c in tf.items()}
        norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
        return {t: v / norm for t, v in vec.items()}

    def score(self, query: str):
        q_vec = self._vectorize(tokenize(query)) if tokenize(query) else {}
        scores = {}
        for doc_id, dvec in zip(self.doc_ids, self.doc_vecs):
            scores[doc_id] = sum(q_vec.get(t, 0.0) * w for t, w in dvec.items())
        return scores


class SentenceTransformerRetriever:
    """Optional real dense retriever. Requires `pip install sentence-transformers`."""

    def __init__(self, docs, model_name: str):
        from sentence_transformers import SentenceTransformer
        import numpy as np

        self.np = np
        self.model = SentenceTransformer(model_name)
        self.doc_ids = [d["id"] for d in docs]
        self.doc_embs = self.model.encode(
            [d["text"] for d in docs], normalize_embeddings=True
        )

    def score(self, query: str):
        q_emb = self.model.encode([query], normalize_embeddings=True)[0]
        sims = self.doc_embs @ q_emb
        return dict(zip(self.doc_ids, sims.tolist()))


# --------------------------------------------------------------------------
# Fusion: Reciprocal Rank Fusion
# --------------------------------------------------------------------------
def ranks_from_scores(scores: dict):
    ordered = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    return {doc_id: i + 1 for i, (doc_id, _) in enumerate(ordered)}


def reciprocal_rank_fusion(rank_lists, k: int = 60):
    fused = defaultdict(float)
    for ranks in rank_lists:
        for doc_id, r in ranks.items():
            fused[doc_id] += 1.0 / (k + r)
    return dict(fused)


# --------------------------------------------------------------------------
# Reranking: cheap cross-encoder-style scorer over the fused top-k
# --------------------------------------------------------------------------
def rerank(query, docs_by_id, candidate_ids, bm25_scores):
    q_terms = set(tokenize(query))
    rescored = {}
    for doc_id in candidate_ids:
        text = docs_by_id[doc_id]["text"]
        d_terms = tokenize(text)
        overlap = len(q_terms & set(d_terms))
        overlap_ratio = overlap / max(len(q_terms), 1)
        rescored[doc_id] = 0.7 * overlap_ratio + 0.3 * bm25_scores.get(doc_id, 0.0)
    return rescored


# --------------------------------------------------------------------------
# Eval metrics
# --------------------------------------------------------------------------
def recall_at_k(ranked_ids, relevant, k):
    if not relevant:
        return None
    top_k = set(ranked_ids[:k])
    return len(top_k & set(relevant)) / len(relevant)


def mrr(ranked_ids, relevant):
    for i, doc_id in enumerate(ranked_ids, start=1):
        if doc_id in relevant:
            return 1.0 / i
    return 0.0


def ndcg_at_k(ranked_ids, relevant, k):
    def dcg(ids):
        return sum(
            1.0 / math.log2(i + 2) for i, d in enumerate(ids[:k]) if d in relevant
        )

    ideal = dcg(list(relevant)[:k] + ["_"] * max(0, k - len(relevant)))
    actual = dcg(ranked_ids)
    return actual / ideal if ideal > 0 else 0.0


# --------------------------------------------------------------------------
# Pipeline
# --------------------------------------------------------------------------
class HybridRAGPipeline:
    def __init__(self, docs, dense_model=None):
        self.docs = docs
        self.docs_by_id = {d["id"]: d for d in docs}
        self.bm25 = BM25(docs)
        if dense_model:
            self.dense = SentenceTransformerRetriever(docs, dense_model)
        else:
            self.dense = TfidfDenseRetriever(docs)

    def search(self, query: str, k: int = 5, fetch_k: int = 10):
        sparse_scores = self.bm25.score(query)
        dense_scores = self.dense.score(query)

        sparse_ranks = ranks_from_scores(sparse_scores)
        dense_ranks = ranks_from_scores(dense_scores)

        fused = reciprocal_rank_fusion([sparse_ranks, dense_ranks])
        fused_ordered = sorted(fused.items(), key=lambda kv: kv[1], reverse=True)
        candidate_ids = [doc_id for doc_id, _ in fused_ordered[:fetch_k]]

        reranked = rerank(query, self.docs_by_id, candidate_ids, sparse_scores)
        final_ordered = sorted(reranked.items(), key=lambda kv: kv[1], reverse=True)
        final_ids = [doc_id for doc_id, _ in final_ordered[:k]]
        return final_ids


def load_json(path):
    return json.loads(Path(path).read_text())


def main():
    parser = argparse.ArgumentParser(description="Hybrid search RAG pipeline demo")
    parser.add_argument("--docs", default=str(Path(__file__).parent / "data" / "docs.json"))
    parser.add_argument("--qrels", default=str(Path(__file__).parent / "data" / "qrels.json"))
    parser.add_argument("--query", default=None, help="Run a single ad-hoc query instead of the eval suite")
    parser.add_argument("--k", type=int, default=5, help="top-k results / cutoff for metrics")
    parser.add_argument(
        "--dense-model",
        default=None,
        help="Optional sentence-transformers model name (e.g. all-MiniLM-L6-v2) for real embeddings",
    )
    args = parser.parse_args()

    docs = load_json(args.docs)
    pipeline = HybridRAGPipeline(docs, dense_model=args.dense_model)

    if args.query:
        results = pipeline.search(args.query, k=args.k)
        print(f"Query: {args.query}\n")
        for rank, doc_id in enumerate(results, start=1):
            print(f"{rank}. [{doc_id}] {pipeline.docs_by_id[doc_id]['text']}")
        return

    qrels = load_json(args.qrels)
    print(f"Evaluating {len(qrels)} queries over {len(docs)} docs (k={args.k})\n")
    recalls, mrrs, ndcgs = [], [], []
    for query, relevant in qrels.items():
        ranked = pipeline.search(query, k=args.k)
        r = recall_at_k(ranked, relevant, args.k)
        m = mrr(ranked, relevant)
        n = ndcg_at_k(ranked, relevant, args.k)
        recalls.append(r)
        mrrs.append(m)
        ndcgs.append(n)
        print(f"- {query!r}")
        print(f"    top-{args.k}: {ranked}")
        print(f"    relevant:  {relevant}")
        print(f"    recall@{args.k}={r:.2f}  mrr={m:.2f}  ndcg@{args.k}={n:.2f}\n")

    print("=== Aggregate metrics ===")
    print(f"Recall@{args.k}: {sum(recalls)/len(recalls):.3f}")
    print(f"MRR:      {sum(mrrs)/len(mrrs):.3f}")
    print(f"nDCG@{args.k}:  {sum(ndcgs)/len(ndcgs):.3f}")


if __name__ == "__main__":
    main()
