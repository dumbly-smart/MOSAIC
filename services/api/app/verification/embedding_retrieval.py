"""Deterministic BGE-M3 chunks, validated vectors, and a local cosine test index."""

import hashlib
import json
import os
import urllib.request
from pathlib import Path

import numpy as np

INDEX_VERSION = "mosaic-local-vector-v1"


def _validate_rows(rows):
    if not isinstance(rows, list) or not rows:
        raise ValueError("At least one extracted record is required")
    document_ids = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Every extracted record must be an object")  # noqa: TRY004 - input data
        if not isinstance(row.get("document_id"), str) or not row["document_id"]:
            raise ValueError("Every record needs a document ID")
        if type(row.get("line")) is not int or row["line"] < 1:
            raise ValueError("Every record needs a positive normalized line number")
        if row.get("page") is not None and (type(row["page"]) is not int or row["page"] < 1):
            raise ValueError("Page numbers must be positive integers or null")
        if not isinstance(row.get("text"), str) or not row["text"].strip():
            raise ValueError("Every record needs nonempty text")
        document_ids.add(row["document_id"])
    if len(document_ids) != 1:
        raise ValueError("One embedding corpus cannot mix document IDs")


def _split_record(row, max_chars):
    text = row["text"].strip()
    if len(text) <= max_chars:
        return [dict(row, text=text, segment=1, segment_count=1)]
    words = text.split()
    if any(len(word) > max_chars for word in words):
        raise ValueError("A single token exceeds the configured chunk size")
    parts, current = [], []
    for word in words:
        candidate = " ".join([*current, word])
        if current and len(candidate) > max_chars:
            parts.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        parts.append(" ".join(current))
    return [
        dict(row, text=part, segment=i, segment_count=len(parts)) for i, part in enumerate(parts, 1)
    ]


def build_chunks(rows, *, max_chars=1600, max_records=8, overlap_records=1):
    """Build page-bounded chunks without losing oversized-record provenance."""
    _validate_rows(rows)
    if type(max_chars) is not int or max_chars < 32:
        raise ValueError("max_chars must be an integer of at least 32")
    if type(max_records) is not int or max_records < 1:
        raise ValueError("max_records must be a positive integer")
    if type(overlap_records) is not int or not 0 <= overlap_records < max_records:
        raise ValueError("overlap_records must be nonnegative and smaller than max_records")
    segments = [segment for row in rows for segment in _split_record(row, max_chars)]
    result, group = [], []

    def flush():
        if not group:
            return
        text = "\n".join(row["text"] for row in group)
        identity = json.dumps(
            {
                "document_id": group[0]["document_id"],
                "page": group[0]["page"],
                "line_start": group[0]["line"],
                "line_end": group[-1]["line"],
                "segments": [r["segment"] for r in group],
                "text": text,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        result.append(
            {
                "id": hashlib.sha256(identity.encode()).hexdigest(),
                "document_id": group[0]["document_id"],
                "page": group[0]["page"],
                "line_start": min(r["line"] for r in group),
                "line_end": max(r["line"] for r in group),
                "text": text,
                "rows": [dict(r) for r in group],
            }
        )

    for segment in segments:
        candidate = "\n".join([*(r["text"] for r in group), segment["text"]])
        if group and (
            segment["page"] != group[0]["page"]
            or len(group) >= max_records
            or len(candidate) > max_chars
        ):
            old = list(group)
            flush()
            group = (
                old[-overlap_records:]
                if overlap_records and segment["page"] == old[0]["page"]
                else []
            )
            while (
                group and len("\n".join([*(r["text"] for r in group), segment["text"]])) > max_chars
            ):
                group.pop(0)
        group.append(segment)
    flush()
    if len({chunk["id"] for chunk in result}) != len(result):
        raise ValueError("Chunk IDs are not unique")
    return result


def corpus_id(chunks):
    if not chunks:
        raise ValueError("Cannot identify an empty corpus")
    canonical = json.dumps(chunks, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def criterion_query(criterion):
    required = ("id", "clause", "field", "unit")
    if not isinstance(criterion, dict) or any(
        not isinstance(criterion.get(k), str) or not criterion[k].strip() for k in required
    ):
        raise ValueError("Criterion lacks text required for retrieval")
    return (
        f"Current bidder evidence for {criterion['field']}. "
        f"Tender requirement: {criterion['clause']}. Expected unit: {criterion['unit']}."
    )


def evaluate_retrieval_report(report, expected):
    """Measure exact synthetic evidence recall without feeding the key to retrieval."""
    if not isinstance(report, dict) or not isinstance(report.get("results"), list):
        raise ValueError("Invalid retrieval report")  # noqa: TRY004 - external JSON
    if not isinstance(expected, dict) or not isinstance(expected.get("criteria"), list):
        raise ValueError("Invalid retrieval answer key")  # noqa: TRY004 - external JSON
    found = {result.get("criterion_id"): result for result in report["results"]}
    checks = []
    for truth in expected["criteria"]:
        if not all(key in truth for key in ("criterion_id", "quote", "page")):
            raise ValueError("Retrieval answer key is incomplete")
        matched = next(
            (
                hit
                for hit in found.get(truth["criterion_id"], {}).get("hits", [])
                if hit.get("page") == truth["page"] and truth["quote"] in hit.get("text", "")
            ),
            None,
        )
        checks.append(
            {
                "criterion_id": truth["criterion_id"],
                "expected_page": truth["page"],
                "found": matched is not None,
                "rank": matched.get("rank") if matched else None,
                "similarity": matched.get("similarity") if matched else None,
            }
        )
    total = len(checks)
    criteria_found = sum(check["found"] for check in checks)
    return {
        "scope": "synthetic answer-key evaluation only",
        "criteria_total": total,
        "criteria_found": criteria_found,
        "recall_at_k": criteria_found / total if total else 0,
        "checks": checks,
    }


def validate_vectors(vectors, count, dimension):
    vectors = np.asarray(vectors)
    if vectors.shape != (count, dimension) or vectors.dtype.kind not in "fc":
        raise ValueError("Embedding matrix has an unexpected shape or type")
    if not np.isfinite(vectors).all():
        raise ValueError("Embedding matrix contains nonfinite values")
    norms = np.linalg.norm(vectors, axis=1)
    if not np.allclose(norms, 1, atol=1e-4):
        raise ValueError("Embeddings must be L2 normalized")


class BgeM3Embedder:
    name = "BAAI/bge-m3"
    provider = "sentence-transformers"
    dimension = 1024

    def __init__(self, device="cpu"):
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(self.name, device=device)
        self.model.max_seq_length = 512
        actual = self.model.get_sentence_embedding_dimension()
        if actual != self.dimension:
            raise RuntimeError(f"Expected {self.dimension} BGE-M3 dimensions, received {actual}")

    def _encode(self, texts, query, batch_size=4):
        if (
            not isinstance(texts, list)
            or not texts
            or any(not isinstance(t, str) or not t.strip() for t in texts)
        ):
            raise ValueError("Embedding input must be a nonempty list of text")
        method = getattr(self.model, "encode_query" if query else "encode_document", None)
        if method is None:
            method = self.model.encode
        vectors = method(
            texts,
            batch_size=batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
            convert_to_numpy=True,
        )
        vectors = np.asarray(vectors, dtype=np.float32)
        validate_vectors(vectors, len(texts), self.dimension)
        return vectors

    def encode_documents(self, texts, batch_size=4):
        return self._encode(texts, False, batch_size)

    def encode_queries(self, texts, batch_size=4):
        return self._encode(texts, True, batch_size)


class OllamaBgeM3Embedder:
    """Dense BGE-M3 adapter for Ollama's local, batched embedding endpoint."""

    name = "bge-m3:latest"
    provider = "ollama"
    dimension = 1024

    def __init__(self, host=None, *, dimension=None, timeout=240, num_gpu=None):
        self.host = (host or os.environ.get("MOSAIC_OLLAMA_URL", "http://127.0.0.1:11434")).rstrip(
            "/"
        )
        self.timeout = timeout
        configured_gpu = os.environ.get("MOSAIC_EMBEDDING_NUM_GPU", "0")
        self.num_gpu = int(configured_gpu) if num_gpu is None else num_gpu
        if self.num_gpu < 0:
            raise ValueError("MOSAIC_EMBEDDING_NUM_GPU must be nonnegative")
        self.runtime = {"num_gpu": self.num_gpu}
        if dimension is not None:
            self.dimension = dimension

    def _encode(self, texts):
        if (
            not isinstance(texts, list)
            or not texts
            or any(not isinstance(text, str) or not text.strip() for text in texts)
        ):
            raise ValueError("Embedding input must be a nonempty list of text")
        payload = {
            "model": self.name,
            "input": texts,
            "truncate": False,
            "keep_alive": "5m",
            "options": self.runtime,
        }
        request = urllib.request.Request(
            self.host + "/api/embed",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                answer = json.load(response)
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError("Ollama BGE-M3 embedding request failed") from exc
        if not isinstance(answer, dict) or answer.get("model") != self.name:
            raise ValueError("Ollama returned an unexpected embedding model")
        vectors = np.asarray(answer.get("embeddings"), dtype=np.float32)
        if vectors.shape != (len(texts), self.dimension) or not np.isfinite(vectors).all():
            raise ValueError("Ollama returned invalid embedding vectors")
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        if np.any(norms <= 0):
            raise ValueError("Ollama returned a zero embedding vector")
        vectors /= norms
        validate_vectors(vectors, len(texts), self.dimension)
        return vectors

    def encode_documents(self, texts, batch_size=4):
        del batch_size  # Ollama receives the already bounded batch in one request.
        return self._encode(texts)

    def encode_queries(self, texts, batch_size=4):
        del batch_size  # BGE-M3 uses the same dense encoding operation for both roles.
        return self._encode(texts)


def make_embedder(provider="ollama"):
    if provider == "ollama":
        return OllamaBgeM3Embedder()
    if provider == "sentence-transformers":
        return BgeM3Embedder()
    raise ValueError("Unknown embedding provider")


class LocalVectorIndex:
    """Exact cosine index for reproducible testing; production storage remains pgvector."""

    def __init__(self, metadata, chunks, vectors):
        self.metadata, self.chunks = metadata, chunks
        self.vectors = np.asarray(vectors, dtype=np.float32)
        validate_vectors(self.vectors, len(chunks), metadata["dimension"])

    @classmethod
    def build(cls, chunks, embedder, target, *, batch_size=4, progress=None):
        if not chunks:
            raise ValueError("Cannot embed an empty chunk list")
        if type(batch_size) is not int or batch_size < 1:
            raise ValueError("batch_size must be positive")
        target = Path(target)
        if target.exists():
            raise ValueError("Index output exists; choose a new directory")
        vectors = []
        for start in range(0, len(chunks), batch_size):
            batch = chunks[start : start + batch_size]
            encoded = embedder.encode_documents([chunk["text"] for chunk in batch])
            validate_vectors(encoded, len(batch), embedder.dimension)
            vectors.append(encoded)
            if progress:
                progress(f"Embedded {min(start + batch_size, len(chunks))}/{len(chunks)} chunks")
        matrix = np.concatenate(vectors).astype(np.float32)
        metadata = {
            "index_version": INDEX_VERSION,
            "provider": getattr(embedder, "provider", None),
            "model": embedder.name,
            "runtime": getattr(embedder, "runtime", {}),
            "dimension": embedder.dimension,
            "normalized": True,
            "corpus_id": corpus_id(chunks),
            "chunk_count": len(chunks),
        }
        temporary = target.with_name(target.name + ".building")
        if temporary.exists():
            raise ValueError("An unfinished index build already exists")
        temporary.mkdir(parents=True)
        (temporary / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        (temporary / "chunks.json").write_text(json.dumps(chunks, indent=2), encoding="utf-8")
        np.save(temporary / "vectors.npy", matrix, allow_pickle=False)
        os.replace(temporary, target)
        return cls(metadata, chunks, matrix)

    @classmethod
    def load(cls, target, *, expected_corpus_id=None):
        target = Path(target)
        try:
            metadata = json.loads((target / "metadata.json").read_text(encoding="utf-8"))
            chunks = json.loads((target / "chunks.json").read_text(encoding="utf-8"))
            vectors = np.load(target / "vectors.npy", allow_pickle=False)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            raise ValueError("Vector index is missing or corrupt") from exc
        if (
            metadata.get("index_version") != INDEX_VERSION
            or not isinstance(metadata.get("provider"), str)
            or not metadata["provider"]
            or metadata.get("chunk_count") != len(chunks)
        ):
            raise ValueError("Vector index metadata is incompatible")
        if corpus_id(chunks) != metadata.get("corpus_id"):
            raise ValueError("Vector index corpus hash does not match its chunks")
        if expected_corpus_id and expected_corpus_id != metadata["corpus_id"]:
            raise ValueError("Vector index belongs to a different corpus")
        return cls(metadata, chunks, vectors)

    def search(self, query, *, top_k=5):
        query = np.asarray(query, dtype=np.float32)
        if query.shape != (self.metadata["dimension"],) or not np.isfinite(query).all():
            raise ValueError("Query vector has an invalid shape or values")
        norm = np.linalg.norm(query)
        if not np.isclose(norm, 1, atol=1e-4):
            raise ValueError("Query vector must be normalized")
        if type(top_k) is not int or not 1 <= top_k <= min(100, len(self.chunks)):
            raise ValueError("top_k is outside the supported index range")
        scores = self.vectors @ query
        order = np.argsort(-scores, kind="stable")[:top_k]
        return [
            dict(self.chunks[i], similarity=float(scores[i]), rank=rank)
            for rank, i in enumerate(order, 1)
        ]
