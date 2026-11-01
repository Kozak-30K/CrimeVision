
"""Persistent SQLite storage for CrimeVision investigation cases."""

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.services.forensic_schema import create_evidence_record


DEFAULT_DB_PATH = Path("data/crimevision.db")


def _utc_now():
    return datetime.now(timezone.utc).isoformat()


def _validate_text(value, field, required=False):
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string.")
    value = value.strip()
    if required and not value:
        raise ValueError(f"{field} cannot be empty.")
    return value


class CaseStore:
    """Store cases, evidence records, and analysis results in SQLite."""

    def __init__(self, db_path=DEFAULT_DB_PATH):
        self.db_path = Path(db_path).expanduser().resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def _connect(self):
        connection = sqlite3.connect(self.db_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize(self):
        """Create database tables if they do not already exist."""
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS cases (
                    case_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'open'
                        CHECK(status IN ('open', 'closed')),
                    created_at_utc TEXT NOT NULL,
                    updated_at_utc TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS evidence (
                    evidence_id TEXT PRIMARY KEY,
                    case_id TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    modality TEXT NOT NULL
                        CHECK(modality IN ('image', 'audio', 'video', 'text')),
                    sha256 TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL CHECK(size_bytes >= 0),
                    registered_at_utc TEXT NOT NULL,
                    integrity_verified INTEGER NOT NULL
                        CHECK(integrity_verified IN (0, 1)),
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    FOREIGN KEY(case_id) REFERENCES cases(case_id)
                        ON DELETE RESTRICT
                );

                CREATE INDEX IF NOT EXISTS idx_evidence_case
                    ON evidence(case_id);

                CREATE TABLE IF NOT EXISTS analysis_results (
                    result_id TEXT PRIMARY KEY,
                    case_id TEXT NOT NULL,
                    evidence_id TEXT,
                    analysis_type TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    created_at_utc TEXT NOT NULL,
                    FOREIGN KEY(case_id) REFERENCES cases(case_id)
                        ON DELETE RESTRICT,
                    FOREIGN KEY(evidence_id) REFERENCES evidence(evidence_id)
                        ON DELETE RESTRICT
                );

                CREATE INDEX IF NOT EXISTS idx_results_case
                    ON analysis_results(case_id);
                """
            )

    def create_case(self, title, description=""):
        """Create a new investigation case."""
        title = _validate_text(title, "title", required=True)
        description = _validate_text(description, "description")
        now = _utc_now()
        case_id = f"case_{uuid.uuid4().hex}"

        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO cases (
                    case_id, title, description, status,
                    created_at_utc, updated_at_utc
                ) VALUES (?, ?, ?, 'open', ?, ?)
                """,
                (case_id, title, description, now, now),
            )

        return self.get_case(case_id)

    def get_case(self, case_id):
        """Retrieve a case and its associated records."""
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM cases WHERE case_id = ?", (case_id,)
            ).fetchone()

        if row is None:
            return None
        return dict(row)

    def list_cases(self, status=None):
        """List cases, optionally filtering by open or closed status."""
        if status is not None and status not in {"open", "closed"}:
            raise ValueError("status must be 'open', 'closed', or None.")

        with self._connect() as connection:
            if status is None:
                rows = connection.execute(
                    "SELECT * FROM cases ORDER BY created_at_utc DESC"
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT * FROM cases
                    WHERE status = ?
                    ORDER BY created_at_utc DESC
                    """,
                    (status,),
                ).fetchall()

        return [dict(row) for row in rows]
    
    def get_record_counts(self):
        """Return global evidence and saved-analysis counts."""
        with self._connect() as connection:
            evidence_count = connection.execute(
                "SELECT COUNT(*) FROM evidence"
            ).fetchone()[0]

            analysis_count = connection.execute(
                "SELECT COUNT(*) FROM analysis_results"
            ).fetchone()[0]

        return {
            "evidence_count": evidence_count,
            "analysis_count": analysis_count,
        }


    def update_case(self, case_id, title=None, description=None, status=None):
        """Update case details without replacing unspecified fields."""
        if title is not None:
            title = _validate_text(title, "title", required=True)
        if description is not None:
            description = _validate_text(description, "description")
        if status is not None and status not in {"open", "closed"}:
            raise ValueError("status must be 'open' or 'closed'.")

        changes = {}
        if title is not None:
            changes["title"] = title
        if description is not None:
            changes["description"] = description
        if status is not None:
            changes["status"] = status

        if not changes:
            existing = self.get_case(case_id)
            if existing is None:
                raise KeyError(f"Case not found: {case_id}")
            return existing

        changes["updated_at_utc"] = _utc_now()
        assignments = ", ".join(f"{key} = ?" for key in changes)

        with self._connect() as connection:
            cursor = connection.execute(
                f"UPDATE cases SET {assignments} WHERE case_id = ?",
                (*changes.values(), case_id),
            )
            if cursor.rowcount == 0:
                raise KeyError(f"Case not found: {case_id}")

        return self.get_case(case_id)

    def register_evidence(
        self, case_id, file_path, modality, metadata=None
    ):
        """Hash and register an existing source file under a case."""
        if self.get_case(case_id) is None:
            raise KeyError(f"Case not found: {case_id}")
        if metadata is not None and not isinstance(metadata, dict):
            raise ValueError("metadata must be a dictionary or None.")

        # Hashes the source file; does not modify it.
        record = create_evidence_record(file_path, modality)
        metadata_json = json.dumps(
            metadata or {}, allow_nan=False, sort_keys=True
        )

        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO evidence (
                    evidence_id, case_id, filename, modality, sha256,
                    size_bytes, registered_at_utc, integrity_verified,
                    metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record["evidence_id"],
                    case_id,
                    record["filename"],
                    record["modality"],
                    record["sha256"],
                    record["size_bytes"],
                    record["registered_at_utc"],
                    int(record["integrity_verified"]),
                    metadata_json,
                ),
            )

        return self.get_evidence(record["evidence_id"])

    def get_evidence(self, evidence_id):
        """Retrieve one evidence record."""
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM evidence WHERE evidence_id = ?",
                (evidence_id,),
            ).fetchone()

        if row is None:
            return None

        record = dict(row)
        record["integrity_verified"] = bool(record["integrity_verified"])
        record["metadata"] = json.loads(record.pop("metadata_json"))
        return record

    def list_evidence(self, case_id):
        """List evidence belonging to a case."""
        if self.get_case(case_id) is None:
            raise KeyError(f"Case not found: {case_id}")

        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT evidence_id FROM evidence
                WHERE case_id = ?
                ORDER BY registered_at_utc
                """,
                (case_id,),
            ).fetchall()

        return [self.get_evidence(row["evidence_id"]) for row in rows]

    def save_analysis(
        self, case_id, analysis_type, result, evidence_id=None
    ):
        """Persist a JSON-serializable analysis result."""
        analysis_type = _validate_text(
            analysis_type, "analysis_type", required=True
        )
        if not isinstance(result, dict):
            raise ValueError("result must be a dictionary.")

        if self.get_case(case_id) is None:
            raise KeyError(f"Case not found: {case_id}")

        if evidence_id is not None:
            evidence = self.get_evidence(evidence_id)
            if evidence is None or evidence["case_id"] != case_id:
                raise ValueError(
                    "evidence_id must belong to the specified case."
                )

        result_json = json.dumps(
            result, allow_nan=False, sort_keys=True
        )
        result_id = f"result_{uuid.uuid4().hex}"

        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO analysis_results (
                    result_id, case_id, evidence_id,
                    analysis_type, result_json, created_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    result_id,
                    case_id,
                    evidence_id,
                    analysis_type,
                    result_json,
                    _utc_now(),
                ),
            )

        return self.get_analysis(result_id)

    def get_analysis(self, result_id):
        """Retrieve one stored analysis result."""
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM analysis_results WHERE result_id = ?",
                (result_id,),
            ).fetchone()

        if row is None:
            return None

        record = dict(row)
        record["result"] = json.loads(record.pop("result_json"))
        return record

    def list_analyses(self, case_id):
        """List all analysis results associated with a case."""
        if self.get_case(case_id) is None:
            raise KeyError(f"Case not found: {case_id}")

        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT result_id FROM analysis_results
                WHERE case_id = ?
                ORDER BY created_at_utc
                """,
                (case_id,),
            ).fetchall()

        return [self.get_analysis(row["result_id"]) for row in rows]
