"""PostgreSQL repository for cases and uploaded documents."""

from contextlib import contextmanager
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

import psycopg
from psycopg.rows import dict_row


class Database:
    def __init__(self, dsn: str, *, connect=psycopg.connect):
        self.dsn = dsn
        self.connect = connect

    @contextmanager
    def connection(self):
        with self.connect(self.dsn, row_factory=dict_row) as connection:
            yield connection

    def create_case(self, owner_id: str, title: str, description: str | None) -> dict[str, Any]:
        case_id = uuid4()
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO public.cases (id, created_by, tender_title, description)
                VALUES (%s, %s, %s, %s)
                RETURNING id, created_by, tender_title, description, status, created_at, updated_at
                """,
                (case_id, UUID(owner_id), title, description),
            )
            return cursor.fetchone()

    def get_case(self, case_id: UUID, owner_id: str) -> dict[str, Any] | None:
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, created_by, tender_title, description, status, created_at, updated_at
                FROM public.cases WHERE id = %s AND created_by = %s
                """,
                (case_id, UUID(owner_id)),
            )
            return cursor.fetchone()

    def create_document(self, document: dict[str, Any]) -> dict[str, Any]:
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO public.documents
                    (id, case_id, created_by, kind, bucket, object_path, original_filename,
                     content_type, size_bytes, sha256)
                VALUES
                    (%(id)s, %(case_id)s, %(created_by)s, %(kind)s, %(bucket)s, %(object_path)s,
                     %(original_filename)s, %(content_type)s, %(size_bytes)s, %(sha256)s)
                RETURNING id, case_id, kind, original_filename, content_type, size_bytes, sha256,
                          processing_status, created_at
                """,
                document,
            )
            return cursor.fetchone()

    def list_documents(self, case_id: UUID, owner_id: str) -> list[dict[str, Any]]:
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT d.id, d.case_id, d.kind, d.original_filename, d.content_type, d.size_bytes,
                       d.sha256, d.processing_status, d.created_at
                FROM public.documents d
                JOIN public.cases c ON c.id = d.case_id
                WHERE d.case_id = %s AND c.created_by = %s
                ORDER BY d.created_at, d.id
                """,
                (case_id, UUID(owner_id)),
            )
            return list(cursor.fetchall())


def utc_now() -> datetime:
    return datetime.now().astimezone()
