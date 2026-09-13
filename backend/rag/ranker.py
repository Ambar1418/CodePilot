"""Deterministic Context Quality Ranker for retrieved code chunks."""
from __future__ import annotations
import re
from typing import List, Dict, Any
from backend.models.schemas import SearchResult


class ContextRanker:
    def rank(
        self,
        results: List[SearchResult],
        task_query: str,
        target_files: List[str] = None,
        target_symbols: List[str] = None,
    ) -> List[SearchResult]:
        """
        Rerank SearchResult objects deterministically based on:
        1. Semantic score (from FAISS similarity)
        2. Symbol match score
        3. File path relevance
        4. Task keyword overlap
        """
        if not results:
            return []

        target_files = [f.lower() for f in (target_files or [])]
        target_symbols = [s.lower() for s in (target_symbols or [])]
        query_words = set(re.findall(r"\w+", task_query.lower()))

        scored_results = []
        for res in results:
            score = 0.0

            # 1. Semantic base score (0.0 to 1.0)
            score += min(max(res.score, 0.0), 1.0) * 0.4

            # 2. Symbol match score
            if res.symbol_name:
                sym_lower = res.symbol_name.lower()
                if sym_lower in target_symbols:
                    score += 0.3
                elif any(word in sym_lower for word in query_words if len(word) > 3):
                    score += 0.15

            # 3. File path relevance
            file_lower = res.file_path.lower()
            if any(tf in file_lower for tf in target_files):
                score += 0.2
            elif any(word in file_lower for word in query_words if len(word) > 3):
                score += 0.1

            # 4. Keyword overlap in content
            content_words = set(re.findall(r"\w+", res.content.lower()[:300]))
            overlap = len(query_words.intersection(content_words))
            if query_words:
                score += min(overlap / len(query_words), 1.0) * 0.1

            scored_results.append((score, res))

        # Sort descending by calculated score, preserving deterministic order
        scored_results.sort(key=lambda x: x[0], reverse=True)
        return [res for _, res in scored_results]
