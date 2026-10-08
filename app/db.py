import json
import sqlite3
from contextlib import closing
from pathlib import Path

DB = Path(__file__).resolve().parents[1] / "credit_scoring.db"


def _applicant_name(name, payload):
    if name:
        return name
    if payload:
        saved_name = (json.loads(payload) if isinstance(payload, str) else payload).get(
            "applicant_name"
        )
        if isinstance(saved_name, str) and saved_name.strip():
            return saved_name.strip()
    return "Name not recorded"


def init_db():
    with closing(sqlite3.connect(DB)) as connection, connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                applicant_name TEXT NOT NULL DEFAULT '',
                risk_probability REAL,
                credit_score INTEGER,
                risk_band TEXT,
                decision TEXT,
                payload TEXT,
                result TEXT
            )
            """
        )
        columns = {
            column[1]
            for column in connection.execute("PRAGMA table_info(predictions)").fetchall()
        }
        if "applicant_name" not in columns:
            connection.execute(
                "ALTER TABLE predictions ADD COLUMN applicant_name TEXT NOT NULL DEFAULT ''"
            )
        if "result" not in columns:
            connection.execute("ALTER TABLE predictions ADD COLUMN result TEXT")
        rows = connection.execute(
            "SELECT id, payload FROM predictions WHERE applicant_name = '' AND payload IS NOT NULL"
        ).fetchall()
        for record_id, payload in rows:
            saved_name = _applicant_name("", payload)
            if saved_name != "Name not recorded":
                connection.execute(
                    "UPDATE predictions SET applicant_name = ? WHERE id = ?",
                    (saved_name, record_id),
                )


def save(payload, result):
    with closing(sqlite3.connect(DB)) as connection, connection:
        connection.execute(
            """
            INSERT INTO predictions
                (applicant_name, risk_probability, credit_score, risk_band, decision, payload, result)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload["applicant_name"],
                result["default_probability"],
                result["credit_score"],
                result["risk_band"],
                result["decision"],
                json.dumps(payload),
                json.dumps(result),
            ),
        )


def history(limit=100, applicant_name="", assessed_on=None):
    with closing(sqlite3.connect(DB)) as connection, connection:
        connection.row_factory = sqlite3.Row
        query = """
            SELECT id, created_at, applicant_name, payload, credit_score, risk_band, decision
            FROM predictions
            WHERE applicant_name = ? COLLATE NOCASE
        """
        parameters = (applicant_name.strip(),)
        if assessed_on:
            query += " AND date(created_at, 'localtime') = ?"
            parameters += (assessed_on,)
        query += " ORDER BY id DESC LIMIT ?"
        parameters += (limit,)
        records = [
            dict(row)
            for row in connection.execute(query, parameters)
        ]
    for record in records:
        record["applicant_name"] = _applicant_name(
            record["applicant_name"], record.pop("payload")
        )
    return records


def applicants():
    with closing(sqlite3.connect(DB)) as connection:
        return [
            row[0]
            for row in connection.execute(
                """
                SELECT DISTINCT applicant_name
                FROM predictions
                WHERE applicant_name IS NOT NULL AND applicant_name != ''
                ORDER BY applicant_name COLLATE NOCASE
                """
            )
        ]


def get_record(record_id):
    with closing(sqlite3.connect(DB)) as connection, connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            """
            SELECT id, created_at, applicant_name, payload, result,
                   risk_probability, credit_score, risk_band, decision
            FROM predictions
            WHERE id = ?
            """,
            (record_id,),
        ).fetchone()
    if row is None:
        return None
    record = dict(row)
    record["payload"] = json.loads(record["payload"])
    record["applicant_name"] = _applicant_name(
        record["applicant_name"], record["payload"]
    )
    if record["result"]:
        record["result"] = json.loads(record["result"])
    else:
        record["result"] = {
            "default_probability": record["risk_probability"],
            "credit_score": record["credit_score"],
            "risk_band": record["risk_band"],
            "decision": record["decision"],
            "key_factors": ["This earlier record did not retain decision factors."],
            "model": "Earlier model version",
            "threshold": None,
        }
    return record
