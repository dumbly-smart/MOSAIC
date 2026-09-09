"""PostgreSQL repository for cases and uploaded documents."""

from contextlib import contextmanager
from typing import Any
from uuid import UUID, uuid4

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


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

    def get_documents_for_run(self, case_id: UUID, owner_id: str) -> list[dict[str, Any]]:
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT d.id, d.kind, d.bucket, d.object_path, d.original_filename
                FROM public.documents d
                JOIN public.cases c ON c.id = d.case_id
                WHERE d.case_id = %s AND c.created_by = %s
                ORDER BY d.created_at, d.id
                """,
                (case_id, UUID(owner_id)),
            )
            return list(cursor.fetchall())

    def create_verification_run(self, case_id: UUID, owner_id: str) -> dict[str, Any] | None:
        run_id = uuid4()
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO public.verification_runs
                    (id, case_id, created_by, status, policy_version)
                SELECT %s, id, created_by, 'queued', %s
                FROM public.cases WHERE id = %s AND created_by = %s
                RETURNING id, case_id, status, policy_version, score, result, error_message,
                          created_at, started_at, completed_at
                """,
                (run_id, "tender-evidence-quota-v2", case_id, UUID(owner_id)),
            )
            return cursor.fetchone()

    def get_verification_run(self, run_id: UUID, owner_id: str) -> dict[str, Any] | None:
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, case_id, status, policy_version, score, result, error_message,
                       created_at, started_at, completed_at
                FROM public.verification_runs WHERE id = %s AND created_by = %s
                """,
                (run_id, UUID(owner_id)),
            )
            return cursor.fetchone()

    def mark_verification_running(self, run_id: UUID) -> None:
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE public.verification_runs SET status = 'running', started_at = now()
                WHERE id = %s AND status = 'queued'
                """,
                (run_id,),
            )

    def complete_verification_run(
        self, run_id: UUID, criteria: list[dict[str, Any]], report: dict[str, Any]
    ) -> None:
        with self.connection() as connection, connection.cursor() as cursor:
            for criterion in criteria:
                cursor.execute(
                    """
                    INSERT INTO public.criteria
                        (id, verification_run_id, criterion_id, rule_version, definition)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        uuid4(),
                        run_id,
                        criterion["id"],
                        criterion.get("rule_version", "unknown"),
                        Jsonb(criterion),
                    ),
                )
            for finding in report["results"]:
                cursor.execute(
                    """
                    INSERT INTO public.findings
                        (id, verification_run_id, criterion_id, status, severity, earned_points,
                         explanation, evidence)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        uuid4(),
                        run_id,
                        finding["criterion_id"],
                        finding["status"],
                        finding.get("severity", "medium"),
                        finding["earned_points"],
                        finding["reason"],
                        Jsonb(finding.get("evidence") or {}),
                    ),
                )
            cursor.execute(
                """
                UPDATE public.verification_runs
                SET status = %s, score = %s, result = %s, completed_at = now()
                WHERE id = %s
                """,
                (
                    "needs_manual_review" if report["review_required"] else "completed",
                    report["score"],
                    Jsonb(report),
                    run_id,
                ),
            )

    def fail_verification_run(self, run_id: UUID, message: str) -> None:
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE public.verification_runs
                SET status = 'failed', error_message = %s, completed_at = now()
                WHERE id = %s
                """,
                (message[:1000], run_id),
            )
