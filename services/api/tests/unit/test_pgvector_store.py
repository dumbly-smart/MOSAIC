"""Verify pgvector persistence SQL and fail-closed input validation without a live database."""

import unittest
from contextlib import nullcontext

import numpy as np

from services.api.app.verification.document_pipeline import PgStore


class FakeCursor:
    def __init__(self, connection):
        self.connection = connection

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def executemany(self, sql, parameters):
        self.connection.executemany_calls.append((sql, list(parameters)))


class FakeConnection:
    def __init__(self):
        self.sql = []
        self.executemany_calls = []
        self.results = []
        self.closed = False

    def execute(self, sql, parameters=None):
        self.sql.append((sql, parameters))
        return self

    def commit(self):
        pass

    def transaction(self):
        return nullcontext()

    def cursor(self):
        return FakeCursor(self)

    def fetchall(self):
        return self.results

    def close(self):
        self.closed = True


class PgVectorStoreTests(unittest.TestCase):
    def setUp(self):
        self.connection = FakeConnection()
        self.store = PgStore(
            "postgresql://local/test",
            connection_factory=lambda *_args, **_kwargs: self.connection,
            vector_registrar=lambda connection: self.assertIs(connection, self.connection),
        )
        self.vector = np.zeros(1024, dtype=np.float32)
        self.vector[0] = 1
        self.chunk = {"id": "chunk-1", "text": "Synthetic evidence", "page": 1}

    def test_schema_enables_vector_table_and_hnsw_cosine_index(self):
        sql = "\n".join(statement for statement, _params in self.connection.sql)
        self.assertIn("CREATE EXTENSION IF NOT EXISTS vector", sql)
        self.assertIn("embedding vector(1024)", sql)
        self.assertIn("USING hnsw (embedding vector_cosine_ops)", sql)

    def test_index_is_idempotent_and_scoped(self):
        self.store.index("corpus-a", "bge-m3:latest", [self.chunk], [self.vector])
        sql, parameters = self.connection.executemany_calls[0]
        self.assertIn("ON CONFLICT", sql)
        self.assertEqual(parameters[0][0:3], ("corpus-a", "bge-m3:latest", "chunk-1"))

    def test_search_filters_scope_uses_cosine_and_adds_stable_rank(self):
        self.connection.results = [(self.chunk, 0.9)]
        hits = self.store.search("corpus-a", "bge-m3:latest", self.vector, 5)
        sql, parameters = self.connection.sql[-1]
        self.assertIn("embedding <=>", sql)
        self.assertIn("WHERE corpus_id=%s AND model=%s", sql)
        self.assertEqual(parameters[1:3], ("corpus-a", "bge-m3:latest"))
        self.assertEqual((hits[0]["rank"], hits[0]["similarity"]), (1, 0.9))

    def test_invalid_vectors_scope_and_k_are_rejected(self):
        for action in (
            lambda: self.store.index("", "model", [self.chunk], [self.vector]),
            lambda: self.store.index("corpus", "model", [self.chunk], [[1, 0]]),
            lambda: self.store.search("corpus", "model", [1, 0], 5),
            lambda: self.store.search("corpus", "model", self.vector, 0),
        ):
            with self.subTest(action=action), self.assertRaises(ValueError):
                action()

    def test_close_releases_connection(self):
        self.store.close()
        self.assertTrue(self.connection.closed)
