"""대화용 근거 검색. 한 기업의 최신 사업보고서 청크 안에서 BM25 + 벡터 하이브리드로 찾는다.

리포트 생성은 절 제목으로 고르지만, 자유 질문은 어느 절에 답이 있는지 모르므로 검색한다.
기업 하나의 청크는 2천 개 안쪽이라 전부 메모리에 올려 계산한다(브루트포스). 벡터는
rag_evidence_embedding 에 저장된 Qwen3-Embedding 값을 그대로 쓰고, 질의 벡터만 GPU 서버에서 받는다.
임베딩 서버가 없으면 BM25 만으로 동작한다.
"""

from __future__ import annotations

import json
import math
import re
import socket
import threading
import urllib.error
import urllib.request
from collections import Counter, OrderedDict
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

import numpy as np

from .evidence import BusinessReport, EvidenceChunk

# 기존 기업분석 실험(company_context/retrieval)의 질의 지시문. 저장된 문서 벡터와 짝이 맞아야 한다.
QUERY_INSTRUCTION = "주어진 기업 분석 질문과 관련된 한국 기업 공식 자료 근거를 검색하라"

_WORD = re.compile(r"[a-zA-Z]+(?:[.-][a-zA-Z0-9]+)*|\d+(?:[.,]\d+)*(?:%|조원|억원|원|년|건)?|[가-힣]+")


def tokenize(text: str) -> list[str]:
    """영문 단어·숫자·한글 어절 + 한글 2·3글자 조각. 형태소 분석 없이도 '반도체'와 '반도체는' 이 겹치게 한다."""
    tokens: list[str] = []
    for match in _WORD.findall(text.lower()):
        tokens.append(match)
        if re.fullmatch(r"[가-힣]+", match):
            for size in (2, 3):
                tokens.extend(f"c{size}:{match[i:i + size]}" for i in range(len(match) - size + 1))
    return tokens


@dataclass(frozen=True)
class Hit:
    chunk: EvidenceChunk
    score: float
    retrievers: tuple[str, ...]


class BM25Index:
    def __init__(self, chunks: Sequence[EvidenceChunk], *, k1: float = 1.5, b: float = 0.75) -> None:
        if not chunks:
            raise ValueError("검색 문서가 비어 있습니다")
        self._chunks = list(chunks)
        self._k1, self._b = k1, b
        # 소속 법인(자회사) 이름은 표 본문에 없고 메타데이터에만 있다. 색인에 넣지 않으면
        # "우리자산운용 영업이익?" 이 그 표를 찾지 못하고 다른 자회사 표를 고른다(우리금융지주 실측).
        self._counts = [Counter(tokenize(f"{c.section_title}\n{c.entity_scope or ''}\n{c.content}")) for c in self._chunks]
        self._lengths = [sum(c.values()) for c in self._counts]
        self._avg = sum(self._lengths) / len(self._lengths)
        self._df: Counter[str] = Counter(term for counts in self._counts for term in counts)

    def _idf(self, term: str) -> float:
        n = self._df.get(term, 0)
        return math.log(1 + (len(self._chunks) - n + 0.5) / (n + 0.5))

    def search(self, query: str, *, top_k: int) -> list[Hit]:
        terms = Counter(tokenize(query))
        scored: list[tuple[float, int]] = []
        for index, (counts, length) in enumerate(zip(self._counts, self._lengths)):
            score = 0.0
            for term, qf in terms.items():
                tf = counts.get(term, 0)
                if not tf:
                    continue
                denominator = tf + self._k1 * (1 - self._b + self._b * length / self._avg)
                score += self._idf(term) * tf * (self._k1 + 1) / denominator * qf
            if score > 0:
                scored.append((score, index))
        scored.sort(key=lambda item: (-item[0], self._chunks[item[1]].evidence_id))
        return [Hit(self._chunks[i], s, ("bm25",)) for s, i in scored[:top_k]]


class QueryEncoder(Protocol):
    def encode(self, query: str) -> np.ndarray: ...


Transport = Callable[[urllib.request.Request, int], dict[str, Any]]


def _transport(request: urllib.request.Request, timeout: int) -> dict[str, Any]:
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


class RemoteQueryEncoder:
    """OpenAI 호환 /v1/embeddings. 실패하면 EmbeddingUnavailable 을 던지고 호출자는 BM25 만 쓴다."""

    def __init__(self, *, base_url: str, api_key: str, model: str = "main", timeout_seconds: int = 20, transport: Transport | None = None) -> None:
        base = base_url.rstrip("/")
        self._endpoint = f"{base}/embeddings" if base.endswith("/v1") else f"{base}/v1/embeddings"
        self._api_key, self._model, self._timeout = api_key, model, timeout_seconds
        self._transport = transport or _transport

    def encode(self, query: str) -> np.ndarray:
        body = {"model": self._model, "input": [f"Instruct: {QUERY_INSTRUCTION}\nQuery:{query}"], "encoding_format": "float"}
        request = urllib.request.Request(
            self._endpoint,
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            payload = self._transport(request, self._timeout)
            vector = np.asarray(payload["data"][0]["embedding"], dtype=np.float32)
        except (urllib.error.URLError, TimeoutError, socket.timeout, KeyError, IndexError, TypeError, ValueError) as error:
            raise EmbeddingUnavailable(str(error)) from error
        norm = float(np.linalg.norm(vector))
        if vector.ndim != 1 or norm == 0:
            raise EmbeddingUnavailable("질의 벡터가 비었습니다")
        return vector / norm


class EmbeddingUnavailable(RuntimeError):
    pass


class VectorIndex:
    def __init__(self, chunks: Sequence[EvidenceChunk], vectors: dict[str, np.ndarray]) -> None:
        pairs = [(c, vectors[c.evidence_id]) for c in chunks if c.evidence_id in vectors]
        if not pairs:
            raise ValueError("벡터가 있는 문서가 없습니다")
        self._chunks = [c for c, _ in pairs]
        matrix = np.stack([v for _, v in pairs]).astype(np.float32)
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        self._matrix = matrix / norms

    @property
    def size(self) -> int:
        return len(self._chunks)

    def search(self, query_vector: np.ndarray, *, top_k: int) -> list[Hit]:
        if query_vector.shape[0] != self._matrix.shape[1]:
            raise ValueError("질의와 문서 임베딩 차원이 다릅니다")
        scores = self._matrix @ query_vector
        order = sorted(range(len(self._chunks)), key=lambda i: (-float(scores[i]), self._chunks[i].evidence_id))[:top_k]
        return [Hit(self._chunks[i], float(scores[i]), ("vector",)) for i in order]


def fuse(rankings: Sequence[Sequence[Hit]], *, top_k: int, k: int = 60) -> list[Hit]:
    """Reciprocal Rank Fusion. 점수 척도가 다른 BM25 와 코사인을 순위로만 합친다."""
    fused: dict[str, tuple[float, Hit, set[str]]] = {}
    for ranking in rankings:
        for rank, hit in enumerate(ranking, start=1):
            key = hit.chunk.evidence_id
            score, _, names = fused.get(key, (0.0, hit, set()))
            fused[key] = (score + 1.0 / (k + rank), hit, names | set(hit.retrievers))
    ordered = sorted(fused.values(), key=lambda item: (-item[0], item[1].chunk.evidence_id))
    return [Hit(hit.chunk, score, tuple(sorted(names))) for score, hit, names in ordered[:top_k]]


class CompanyRetriever:
    """기업별 색인을 만들어 LRU 로 들고 있다. 색인 만들기는 BM25 수백 ms, 벡터 로딩은 DB 왕복 한 번이다."""

    def __init__(
        self,
        *,
        load_vectors: Callable[[BusinessReport], dict[str, np.ndarray]] | None = None,
        encoder: QueryEncoder | None = None,
        cache_size: int = 16,
    ) -> None:
        self._load_vectors = load_vectors
        self._encoder = encoder
        self._cache: OrderedDict[str, tuple[BM25Index, VectorIndex | None]] = OrderedDict()
        self._cache_size = cache_size
        self._lock = threading.Lock()

    def _indexes(self, report: BusinessReport) -> tuple[BM25Index, VectorIndex | None]:
        key = f"{report.corp_code}:{report.rcept_no}"
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                return self._cache[key]
        bm25 = BM25Index(report.chunks)
        vector: VectorIndex | None = None
        if self._load_vectors is not None and self._encoder is not None:
            try:
                vectors = self._load_vectors(report)
                if vectors:
                    vector = VectorIndex(report.chunks, vectors)
            except Exception:  # noqa: BLE001 — 벡터가 없어도 BM25 로 답한다
                vector = None
        with self._lock:
            self._cache[key] = (bm25, vector)
            while len(self._cache) > self._cache_size:
                self._cache.popitem(last=False)
        return bm25, vector

    def search(self, report: BusinessReport, query: str, *, top_k: int = 8) -> list[Hit]:
        bm25, vector = self._indexes(report)
        rankings: list[list[Hit]] = [bm25.search(query, top_k=top_k * 2)]
        if vector is not None and self._encoder is not None:
            try:
                rankings.append(vector.search(self._encoder.encode(query), top_k=top_k * 2))
            except (EmbeddingUnavailable, ValueError):
                pass
        return fuse(rankings, top_k=top_k)
