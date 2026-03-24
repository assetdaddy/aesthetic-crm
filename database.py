from __future__ import annotations

"""SQLite persistence layer for the aesthetic CRM application.

This module owns:
1. Schema creation and lightweight migrations.
2. Seed data for a realistic demo experience.
3. Query helpers used by the FastAPI layer.
4. Signature image file storage and DB backup snapshot helpers.

The code keeps the database access intentionally explicit. The project is small
enough that raw SQL remains readable, and the current shape is easier to deploy
to Render than introducing an ORM plus migrations tooling.
"""

import base64
import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
STORAGE_DIR = BASE_DIR / "storage"
SIGNATURE_DIR = STORAGE_DIR / "signatures"
BACKUP_DIR = STORAGE_DIR / "backups"
DB_PATH = BASE_DIR / "esthetic_crm.sqlite3"

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    phone TEXT NOT NULL UNIQUE,
    grade TEXT NOT NULL DEFAULT 'Regular',
    last_visit TEXT,
    memo TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    total_sessions INTEGER NOT NULL CHECK (total_sessions >= 0),
    remaining_sessions INTEGER NOT NULL CHECK (
        remaining_sessions >= 0 AND remaining_sessions <= total_sessions
    ),
    expires_at TEXT,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS visit_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL,
    visit_date TEXT NOT NULL,
    treatment_name TEXT NOT NULL,
    staff_name TEXT,
    notes TEXT,
    ticket_id INTEGER,
    used_sessions INTEGER NOT NULL DEFAULT 0 CHECK (used_sessions >= 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE,
    FOREIGN KEY (ticket_id) REFERENCES tickets(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS consent_forms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER,
    customer_name TEXT NOT NULL,
    phone TEXT NOT NULL,
    treatment_name TEXT NOT NULL,
    agreement_items TEXT NOT NULL,
    notes TEXT,
    signature_image_path TEXT,
    signed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE SET NULL
);
"""

SEED_CUSTOMERS = [
    {
        "name": "김하늘",
        "phone": "010-2451-1188",
        "grade": "VIP",
        "last_visit": "2026-03-22",
        "memo": "예민성 피부. 진정 관리 선호, 주말 오전 예약 비중 높음.",
    },
    {
        "name": "박서윤",
        "phone": "010-8874-2012",
        "grade": "Gold",
        "last_visit": "2026-03-18",
        "memo": "웨딩 전 집중 관리 진행 중. 4월 중순까지 주 1회 방문 예정.",
    },
    {
        "name": "이도현",
        "phone": "010-3329-4457",
        "grade": "Regular",
        "last_visit": "2026-03-11",
        "memo": "남성 모공/트러블 관리. 평일 저녁 선호.",
    },
    {
        "name": "최민지",
        "phone": "010-6100-8342",
        "grade": "VIP",
        "last_visit": "2026-03-24",
        "memo": "리프팅 회원권 보유. 홈케어 제품 업셀 가능성 높음.",
    },
]

SEED_TICKETS = {
    "010-2451-1188": [
        {
            "title": "수분 재생 관리 10회",
            "total_sessions": 10,
            "remaining_sessions": 6,
            "expires_at": "2026-06-30",
        },
        {
            "title": "LDM 진정 케어 5회",
            "total_sessions": 5,
            "remaining_sessions": 2,
            "expires_at": "2026-04-10",
        },
    ],
    "010-8874-2012": [
        {
            "title": "웨딩 윤곽 프로그램 8회",
            "total_sessions": 8,
            "remaining_sessions": 5,
            "expires_at": "2026-05-15",
        }
    ],
    "010-3329-4457": [
        {
            "title": "아쿠아필 6회",
            "total_sessions": 6,
            "remaining_sessions": 1,
            "expires_at": "2026-04-02",
        }
    ],
    "010-6100-8342": [
        {
            "title": "탄력 리프팅 12회",
            "total_sessions": 12,
            "remaining_sessions": 9,
            "expires_at": "2026-08-31",
        },
        {
            "title": "데콜테 순환 케어 4회",
            "total_sessions": 4,
            "remaining_sessions": 4,
            "expires_at": "2026-05-05",
        },
    ],
}

SEED_VISITS = {
    "010-2451-1188": [
        {
            "visit_date": "2026-03-22",
            "treatment_name": "수분 재생 관리",
            "staff_name": "원장 김아린",
            "notes": "붉은기 안정. 진정 앰플 반응 좋음.",
            "used_sessions": 1,
        },
        {
            "visit_date": "2026-03-08",
            "treatment_name": "LDM 진정 케어",
            "staff_name": "원장 김아린",
            "notes": "봄철 민감도 상승, 자극 최소화.",
            "used_sessions": 1,
        },
    ],
    "010-8874-2012": [
        {
            "visit_date": "2026-03-18",
            "treatment_name": "웨딩 윤곽 프로그램",
            "staff_name": "실장 서연",
            "notes": "턱선 부기 관리. 다음 방문 시 데콜테 연계 제안.",
            "used_sessions": 1,
        }
    ],
    "010-3329-4457": [
        {
            "visit_date": "2026-03-11",
            "treatment_name": "아쿠아필",
            "staff_name": "원장 김아린",
            "notes": "T존 피지 개선, 월 2회 권장.",
            "used_sessions": 1,
        }
    ],
    "010-6100-8342": [
        {
            "visit_date": "2026-03-24",
            "treatment_name": "탄력 리프팅",
            "staff_name": "원장 김아린",
            "notes": "볼륨 개선 만족도 높음. 홈케어 크림 추가 안내.",
            "used_sessions": 1,
        },
        {
            "visit_date": "2026-03-02",
            "treatment_name": "데콜테 순환 케어",
            "staff_name": "실장 서연",
            "notes": "어깨 긴장 완화. 림프 순환 반응 양호.",
            "used_sessions": 1,
        },
    ],
}


@contextmanager
def get_connection():
    """Yield a SQLite connection and always close it afterwards."""

    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_database() -> None:
    """Create directories, apply schema, run migrations, and seed demo data."""

    SIGNATURE_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    with get_connection() as connection:
        connection.executescript(SCHEMA_SQL)
        _run_migrations(connection)
        _seed_data(connection)


def list_customers(search: str | None = None) -> list[dict[str, Any]]:
    """Return customer cards used by the dashboard.

    The main list intentionally returns enough ticket data for the landing page
    while keeping heavier visit / consent histories for the dedicated detail API.
    """

    search_text = (search or "").strip()
    with get_connection() as connection:
        query = """
        SELECT
            c.id,
            c.name,
            c.phone,
            c.grade,
            c.last_visit,
            c.memo,
            COALESCE(SUM(t.remaining_sessions), 0) AS total_remaining_sessions,
            COUNT(t.id) AS active_ticket_count
        FROM customers c
        LEFT JOIN tickets t ON t.customer_id = c.id
        """
        params: list[Any] = []
        if search_text:
            query += """
            WHERE c.name LIKE ? OR c.phone LIKE ? OR COALESCE(c.memo, '') LIKE ?
            """
            like = f"%{search_text}%"
            params.extend([like, like, like])

        query += """
        GROUP BY c.id
        ORDER BY
            CASE c.grade
                WHEN 'VIP' THEN 0
                WHEN 'Gold' THEN 1
                ELSE 2
            END,
            c.name COLLATE NOCASE
        """
        customer_rows = connection.execute(query, params).fetchall()
        if not customer_rows:
            return []

        customer_ids = [row["id"] for row in customer_rows]
        ticket_rows = connection.execute(
            f"""
            SELECT
                id,
                customer_id,
                title,
                total_sessions,
                remaining_sessions,
                expires_at,
                updated_at
            FROM tickets
            WHERE customer_id IN ({", ".join("?" for _ in customer_ids)})
            ORDER BY
                CASE WHEN expires_at IS NULL THEN 1 ELSE 0 END,
                expires_at,
                title COLLATE NOCASE
            """,
            customer_ids,
        ).fetchall()

    tickets_by_customer: dict[int, list[dict[str, Any]]] = {}
    for row in ticket_rows:
        ticket = _serialize_ticket(row)
        tickets_by_customer.setdefault(ticket["customer_id"], []).append(ticket)

    return [
        {
            "id": row["id"],
            "name": row["name"],
            "phone": row["phone"],
            "grade": row["grade"],
            "last_visit": row["last_visit"],
            "memo": row["memo"],
            "total_remaining_sessions": row["total_remaining_sessions"],
            "active_ticket_count": row["active_ticket_count"],
            "tickets": tickets_by_customer.get(row["id"], []),
        }
        for row in customer_rows
    ]


def get_customer_detail(customer_id: int) -> dict[str, Any]:
    """Return the data shown inside the customer detail modal."""

    with get_connection() as connection:
        customer_row = connection.execute(
            """
            SELECT
                c.id,
                c.name,
                c.phone,
                c.grade,
                c.last_visit,
                c.memo,
                COALESCE(SUM(t.remaining_sessions), 0) AS total_remaining_sessions,
                COUNT(t.id) AS active_ticket_count
            FROM customers c
            LEFT JOIN tickets t ON t.customer_id = c.id
            WHERE c.id = ?
            GROUP BY c.id
            """,
            (customer_id,),
        ).fetchone()
        if customer_row is None:
            raise LookupError("고객을 찾을 수 없습니다.")

        ticket_rows = connection.execute(
            """
            SELECT
                id,
                customer_id,
                title,
                total_sessions,
                remaining_sessions,
                expires_at,
                updated_at
            FROM tickets
            WHERE customer_id = ?
            ORDER BY
                CASE WHEN expires_at IS NULL THEN 1 ELSE 0 END,
                expires_at,
                title COLLATE NOCASE
            """,
            (customer_id,),
        ).fetchall()

        visit_rows = connection.execute(
            """
            SELECT
                id,
                visit_date,
                treatment_name,
                staff_name,
                notes,
                used_sessions
            FROM visit_records
            WHERE customer_id = ?
            ORDER BY visit_date DESC, id DESC
            """,
            (customer_id,),
        ).fetchall()

        consent_rows = connection.execute(
            """
            SELECT
                id,
                customer_id,
                customer_name,
                phone,
                treatment_name,
                agreement_items,
                notes,
                signature_image_path,
                signed_at
            FROM consent_forms
            WHERE customer_id = ? OR phone = ?
            ORDER BY signed_at DESC, id DESC
            """,
            (customer_id, customer_row["phone"]),
        ).fetchall()

    return {
        "id": customer_row["id"],
        "name": customer_row["name"],
        "phone": customer_row["phone"],
        "grade": customer_row["grade"],
        "last_visit": customer_row["last_visit"],
        "memo": customer_row["memo"],
        "total_remaining_sessions": customer_row["total_remaining_sessions"],
        "active_ticket_count": customer_row["active_ticket_count"],
        "tickets": [_serialize_ticket(row) for row in ticket_rows],
        "visit_records": [
            {
                "id": row["id"],
                "visit_date": row["visit_date"],
                "treatment_name": row["treatment_name"],
                "staff_name": row["staff_name"],
                "notes": row["notes"],
                "used_sessions": row["used_sessions"],
            }
            for row in visit_rows
        ],
        "consents": [_serialize_consent(row) for row in consent_rows],
    }


def deduct_ticket_sessions(ticket_id: int, amount: int = 1) -> dict[str, Any]:
    """Deduct sessions safely and record the action as a visit entry."""

    if amount < 1:
        raise ValueError("차감 횟수는 1 이상이어야 합니다.")

    with get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE")
        ticket_row = connection.execute(
            """
            SELECT
                t.id,
                t.customer_id,
                c.name AS customer_name,
                t.title,
                t.total_sessions,
                t.remaining_sessions,
                t.expires_at,
                t.updated_at
            FROM tickets t
            JOIN customers c ON c.id = t.customer_id
            WHERE t.id = ?
            """,
            (ticket_id,),
        ).fetchone()

        if ticket_row is None:
            raise LookupError("해당 티켓을 찾을 수 없습니다.")
        if ticket_row["remaining_sessions"] < amount:
            raise ValueError("잔여 티켓이 부족합니다.")

        connection.execute(
            """
            UPDATE tickets
            SET
                remaining_sessions = remaining_sessions - ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (amount, ticket_id),
        )
        connection.execute(
            """
            UPDATE customers
            SET last_visit = DATE('now')
            WHERE id = ?
            """,
            (ticket_row["customer_id"],),
        )
        connection.execute(
            """
            INSERT INTO visit_records (
                customer_id,
                visit_date,
                treatment_name,
                staff_name,
                notes,
                ticket_id,
                used_sessions
            )
            VALUES (?, DATE('now'), ?, ?, ?, ?, ?)
            """,
            (
                ticket_row["customer_id"],
                ticket_row["title"],
                "CRM 자동기록",
                f"대시보드에서 티켓 {amount}회 차감 처리",
                ticket_id,
                amount,
            ),
        )

        updated_row = connection.execute(
            """
            SELECT
                t.id,
                t.customer_id,
                c.name AS customer_name,
                t.title,
                t.total_sessions,
                t.remaining_sessions,
                t.expires_at,
                t.updated_at
            FROM tickets t
            JOIN customers c ON c.id = t.customer_id
            WHERE t.id = ?
            """,
            (ticket_id,),
        ).fetchone()

    ticket = _serialize_ticket(updated_row)
    ticket["customer_name"] = updated_row["customer_name"]
    return ticket


def create_consent_form(
    *,
    customer_id: int | None,
    customer_name: str,
    phone: str,
    treatment_name: str,
    agreement_items: list[str],
    notes: str | None,
    signature_data_url: str,
) -> dict[str, Any]:
    """Persist a consent form and store the signature as an image file."""

    customer_name = customer_name.strip()
    phone = phone.strip()
    treatment_name = treatment_name.strip()
    notes = (notes or "").strip() or None
    agreement_items = [item.strip() for item in agreement_items if item and item.strip()]

    if not customer_name:
        raise ValueError("고객 이름을 입력해 주세요.")
    if not phone:
        raise ValueError("연락처를 입력해 주세요.")
    if not treatment_name:
        raise ValueError("시술명을 입력해 주세요.")
    if not agreement_items:
        raise ValueError("동의 항목을 하나 이상 선택해 주세요.")

    signature_rel_path = _save_signature_image(signature_data_url, customer_name)

    try:
        with get_connection() as connection:
            consent_columns = {
                row["name"] for row in connection.execute("PRAGMA table_info(consent_forms)")
            }
            resolved_customer_id = customer_id
            if resolved_customer_id is not None:
                customer_row = connection.execute(
                    "SELECT id FROM customers WHERE id = ?",
                    (resolved_customer_id,),
                ).fetchone()
                if customer_row is None:
                    raise LookupError("선택한 고객을 찾을 수 없습니다.")
            else:
                matched_customer = connection.execute(
                    "SELECT id FROM customers WHERE phone = ?",
                    (phone,),
                ).fetchone()
                resolved_customer_id = matched_customer["id"] if matched_customer else None

            serialized_items = json.dumps(agreement_items, ensure_ascii=False)
            if "signature_data_url" in consent_columns:
                cursor = connection.execute(
                    """
                    INSERT INTO consent_forms (
                        customer_id,
                        customer_name,
                        phone,
                        treatment_name,
                        agreement_items,
                        notes,
                        signature_image_path,
                        signature_data_url
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        resolved_customer_id,
                        customer_name,
                        phone,
                        treatment_name,
                        serialized_items,
                        notes,
                        signature_rel_path,
                        signature_data_url,
                    ),
                )
            else:
                cursor = connection.execute(
                    """
                    INSERT INTO consent_forms (
                        customer_id,
                        customer_name,
                        phone,
                        treatment_name,
                        agreement_items,
                        notes,
                        signature_image_path
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        resolved_customer_id,
                        customer_name,
                        phone,
                        treatment_name,
                        serialized_items,
                        notes,
                        signature_rel_path,
                    ),
                )

            row = connection.execute(
                """
                SELECT
                    id,
                    customer_id,
                    customer_name,
                    phone,
                    treatment_name,
                    agreement_items,
                    notes,
                    signature_image_path,
                    signed_at
                FROM consent_forms
                WHERE id = ?
                """,
                (cursor.lastrowid,),
            ).fetchone()
    except Exception:
        signature_file = BASE_DIR / signature_rel_path
        signature_file.unlink(missing_ok=True)
        raise

    return _serialize_consent(row)


def list_recent_consents(limit: int = 8) -> list[dict[str, Any]]:
    """Return recent consent forms for the dashboard and consent lounge."""

    safe_limit = max(1, min(limit, 20))
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                id,
                customer_id,
                customer_name,
                phone,
                treatment_name,
                agreement_items,
                notes,
                signature_image_path,
                signed_at
            FROM consent_forms
            ORDER BY signed_at DESC, id DESC
            LIMIT ?
            """,
            (safe_limit,),
        ).fetchall()

    return [_serialize_consent(row) for row in rows]


def get_consent(consent_id: int) -> dict[str, Any]:
    """Return one consent form with its signature file metadata."""

    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT
                id,
                customer_id,
                customer_name,
                phone,
                treatment_name,
                agreement_items,
                notes,
                signature_image_path,
                signed_at
            FROM consent_forms
            WHERE id = ?
            """,
            (consent_id,),
        ).fetchone()

    if row is None:
        raise LookupError("전자 동의서를 찾을 수 없습니다.")
    return _serialize_consent(row)


def resolve_signature_path(relative_path: str | None) -> Path | None:
    """Resolve a stored relative path to an absolute file path."""

    if not relative_path:
        return None
    candidate = BASE_DIR / relative_path
    return candidate if candidate.exists() else None


def create_backup_snapshot(target_path: Path) -> Path:
    """Create a SQLite backup snapshot using SQLite's native backup API."""

    source = sqlite3.connect(DB_PATH)
    destination = sqlite3.connect(target_path)
    try:
        source.backup(destination)
        destination.commit()
    finally:
        destination.close()
        source.close()
    return target_path


def _run_migrations(connection: sqlite3.Connection) -> None:
    """Add missing columns and migrate old signature data when present."""

    _ensure_column(
        connection,
        table_name="consent_forms",
        column_name="signature_image_path",
        column_ddl="TEXT",
    )
    _ensure_column(
        connection,
        table_name="consent_forms",
        column_name="created_at",
        column_ddl="TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP",
    )
    _migrate_legacy_signature_data(connection)


def _seed_data(connection: sqlite3.Connection) -> None:
    """Insert demo rows and backfill missing demo records in legacy DBs."""

    existing_count = connection.execute(
        "SELECT COUNT(*) AS count FROM customers"
    ).fetchone()["count"]
    if not existing_count:
        connection.executemany(
            """
            INSERT INTO customers (name, phone, grade, last_visit, memo)
            VALUES (:name, :phone, :grade, :last_visit, :memo)
            """,
            SEED_CUSTOMERS,
        )

        id_by_phone = {
            row["phone"]: row["id"]
            for row in connection.execute("SELECT id, phone FROM customers").fetchall()
        }

        ticket_rows: list[dict[str, Any]] = []
        for phone, tickets in SEED_TICKETS.items():
            for ticket in tickets:
                ticket_rows.append(
                    {
                        "customer_id": id_by_phone[phone],
                        "title": ticket["title"],
                        "total_sessions": ticket["total_sessions"],
                        "remaining_sessions": ticket["remaining_sessions"],
                        "expires_at": ticket["expires_at"],
                    }
                )

        connection.executemany(
            """
            INSERT INTO tickets (
                customer_id,
                title,
                total_sessions,
                remaining_sessions,
                expires_at
            )
            VALUES (
                :customer_id,
                :title,
                :total_sessions,
                :remaining_sessions,
                :expires_at
            )
            """,
            ticket_rows,
        )

    visit_count = connection.execute(
        "SELECT COUNT(*) AS count FROM visit_records"
    ).fetchone()["count"]
    if visit_count:
        return

    id_by_phone = {
        row["phone"]: row["id"]
        for row in connection.execute("SELECT id, phone FROM customers").fetchall()
    }

    visit_rows: list[dict[str, Any]] = []
    for phone, visits in SEED_VISITS.items():
        customer_id = id_by_phone.get(phone)
        if customer_id is None:
            continue
        for visit in visits:
            visit_rows.append(
                {
                    "customer_id": customer_id,
                    "visit_date": visit["visit_date"],
                    "treatment_name": visit["treatment_name"],
                    "staff_name": visit["staff_name"],
                    "notes": visit["notes"],
                    "used_sessions": visit["used_sessions"],
                }
            )

    if visit_rows:
        connection.executemany(
            """
            INSERT INTO visit_records (
                customer_id,
                visit_date,
                treatment_name,
                staff_name,
                notes,
                used_sessions
            )
            VALUES (
                :customer_id,
                :visit_date,
                :treatment_name,
                :staff_name,
                :notes,
                :used_sessions
            )
            """,
            visit_rows,
        )


def _ensure_column(
    connection: sqlite3.Connection,
    *,
    table_name: str,
    column_name: str,
    column_ddl: str,
) -> None:
    """ALTER TABLE only when a legacy database is missing the target column."""

    columns = {
        row["name"] for row in connection.execute(f"PRAGMA table_info({table_name})")
    }
    if column_name not in columns:
        connection.execute(
            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_ddl}"
        )


def _migrate_legacy_signature_data(connection: sqlite3.Connection) -> None:
    """Convert old base64 signature blobs into physical PNG files."""

    columns = {
        row["name"] for row in connection.execute("PRAGMA table_info(consent_forms)")
    }
    if "signature_data_url" not in columns:
        return

    rows = connection.execute(
        """
        SELECT id, customer_name, signature_data_url, signature_image_path
        FROM consent_forms
        WHERE signature_data_url IS NOT NULL
          AND TRIM(signature_data_url) <> ''
          AND (signature_image_path IS NULL OR TRIM(signature_image_path) = '')
        """
    ).fetchall()

    for row in rows:
        try:
            relative_path = _save_signature_image(
                row["signature_data_url"],
                row["customer_name"],
                consent_id=row["id"],
            )
        except ValueError:
            continue

        connection.execute(
            """
            UPDATE consent_forms
            SET signature_image_path = ?
            WHERE id = ?
            """,
            (relative_path, row["id"]),
        )


def _save_signature_image(
    signature_data_url: str,
    customer_name: str,
    consent_id: int | None = None,
) -> str:
    """Decode a base64 data URL and write the signature PNG to disk."""

    if not signature_data_url.startswith("data:image/png;base64,"):
        raise ValueError("서명 데이터가 올바르지 않습니다.")

    _, encoded = signature_data_url.split(",", 1)
    try:
        image_bytes = base64.b64decode(encoded)
    except ValueError as error:
        raise ValueError("서명 데이터를 해석할 수 없습니다.") from error

    slug = "".join(ch for ch in customer_name if ch.isalnum()) or "customer"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = f"consent_{consent_id}" if consent_id is not None else uuid.uuid4().hex[:8]
    filename = f"{slug}_{timestamp}_{suffix}.png"
    file_path = SIGNATURE_DIR / filename
    file_path.write_bytes(image_bytes)
    return str(file_path.relative_to(BASE_DIR).as_posix())


def _serialize_ticket(row: sqlite3.Row) -> dict[str, Any]:
    total_sessions = row["total_sessions"]
    remaining_sessions = row["remaining_sessions"]
    progress_percent = 0
    if total_sessions:
        progress_percent = int(round((remaining_sessions / total_sessions) * 100))

    return {
        "id": row["id"],
        "customer_id": row["customer_id"],
        "title": row["title"],
        "total_sessions": total_sessions,
        "remaining_sessions": remaining_sessions,
        "used_sessions": total_sessions - remaining_sessions,
        "expires_at": row["expires_at"],
        "updated_at": row["updated_at"],
        "days_until_expiry": _days_until(row["expires_at"]),
        "progress_percent": progress_percent,
    }


def _serialize_consent(row: sqlite3.Row) -> dict[str, Any]:
    signature_path = row["signature_image_path"]
    return {
        "id": row["id"],
        "customer_id": row["customer_id"],
        "customer_name": row["customer_name"],
        "phone": row["phone"],
        "treatment_name": row["treatment_name"],
        "agreement_items": json.loads(row["agreement_items"]),
        "notes": row["notes"],
        "signed_at": row["signed_at"],
        "signature_image_path": signature_path,
        "signature_available": bool(resolve_signature_path(signature_path)),
    }


def _days_until(value: str | None) -> int | None:
    if not value:
        return None
    return (date.fromisoformat(value) - date.today()).days
