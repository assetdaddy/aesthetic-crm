from __future__ import annotations

"""FastAPI entrypoint for the premium aesthetic CRM application."""

import hmac
import os
import tempfile
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
from starlette.background import BackgroundTask
from starlette.middleware.sessions import SessionMiddleware

from database import (
    BACKUP_DIR,
    DB_PATH,
    create_backup_snapshot,
    create_consent_form,
    deduct_ticket_sessions,
    get_consent,
    get_connection,
    get_customer_detail,
    initialize_database,
    list_customers,
    list_recent_consents,
    resolve_signature_path,
)
from pdf_utils import build_consent_pdf

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"

LOGIN_FILE = TEMPLATES_DIR / "login.html"
INDEX_FILE = TEMPLATES_DIR / "index.html"
CONSENT_FILE = TEMPLATES_DIR / "consent.html"
SETTINGS_FILE = TEMPLATES_DIR / "settings.html"

APP_VERSION = "1.0.0"
ADMIN_USERNAME = os.getenv("CRM_ADMIN_USERNAME", "owner")
ADMIN_PASSWORD = os.getenv("CRM_ADMIN_PASSWORD", "cheongdam123!")
SESSION_SECRET = os.getenv("CRM_SESSION_SECRET", "change-this-secret-in-render")


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    yield


app = FastAPI(
    title="Cheongdam Atelier CRM",
    version=APP_VERSION,
    lifespan=lifespan,
)
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    max_age=60 * 60 * 12,
    same_site="lax",
    https_only=False,
)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


class TicketDeductionPayload(BaseModel):
    amount: int = Field(default=1, ge=1, le=10)


class ConsentCreatePayload(BaseModel):
    customer_id: int | None = Field(default=None, ge=1)
    customer_name: str = Field(min_length=1, max_length=50)
    phone: str = Field(min_length=7, max_length=30)
    treatment_name: str = Field(min_length=1, max_length=120)
    agreement_items: list[str] = Field(min_length=1, max_length=10)
    notes: str | None = Field(default=None, max_length=1000)
    signature_data_url: str = Field(min_length=30, max_length=500000)

    @field_validator("agreement_items")
    @classmethod
    def validate_agreement_items(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value if item and item.strip()]
        if not cleaned:
            raise ValueError("동의 항목을 하나 이상 선택해 주세요.")
        return cleaned


class LoginPayload(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=100)


@app.get("/health")
async def healthcheck() -> dict[str, str]:
    """Simple Render healthcheck endpoint."""

    return {"status": "ok", "version": APP_VERSION}


@app.get("/login", response_model=None)
async def serve_login_page(request: Request) -> FileResponse | RedirectResponse:
    if _is_authenticated(request):
        return RedirectResponse(url="/", status_code=303)
    return FileResponse(LOGIN_FILE)


@app.get("/", response_model=None)
async def serve_index(request: Request) -> FileResponse | RedirectResponse:
    return _guard_page(request, INDEX_FILE)


@app.get("/consent", response_model=None)
async def serve_consent_page(request: Request) -> FileResponse | RedirectResponse:
    return _guard_page(request, CONSENT_FILE)


@app.get("/settings", response_model=None)
async def serve_settings_page(request: Request) -> FileResponse | RedirectResponse:
    return _guard_page(request, SETTINGS_FILE)


@app.get("/api/auth/me")
async def get_current_user(request: Request) -> dict[str, str]:
    _require_authenticated_api(request)
    return {"username": request.session.get("username", ADMIN_USERNAME)}


@app.post("/api/auth/login")
async def login(payload: LoginPayload, request: Request) -> dict[str, str]:
    """Authenticate the admin user and write a session cookie."""

    username_ok = hmac.compare_digest(payload.username, ADMIN_USERNAME)
    password_ok = hmac.compare_digest(payload.password, ADMIN_PASSWORD)
    if not (username_ok and password_ok):
        raise HTTPException(status_code=401, detail="아이디 또는 비밀번호가 올바르지 않습니다.")

    request.session.clear()
    request.session["authenticated"] = True
    request.session["username"] = ADMIN_USERNAME
    return {"message": "관리자 로그인이 완료되었습니다."}


@app.post("/api/auth/logout")
async def logout(request: Request) -> dict[str, str]:
    request.session.clear()
    return {"message": "로그아웃되었습니다."}


@app.get("/api/customers")
async def get_customers(
    request: Request,
    q: str | None = Query(default=None, max_length=100),
) -> dict:
    _require_authenticated_api(request)
    customers = list_customers(q)
    return {"customers": customers, "summary": _build_summary(customers)}


@app.get("/api/customers/{customer_id}")
async def get_customer_detail_api(request: Request, customer_id: int) -> dict:
    _require_authenticated_api(request)
    try:
        customer = get_customer_detail(customer_id)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return {"customer": customer}


@app.get("/api/consents")
async def get_recent_consents_api(
    request: Request,
    limit: int = Query(default=8, ge=1, le=20),
) -> dict:
    _require_authenticated_api(request)
    return {"consents": list_recent_consents(limit=limit)}


@app.get("/api/consents/{consent_id}/signature")
async def preview_signature(request: Request, consent_id: int) -> FileResponse:
    _require_authenticated_api(request)
    try:
        consent = get_consent(consent_id)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    file_path = resolve_signature_path(consent["signature_image_path"])
    if file_path is None:
        raise HTTPException(status_code=404, detail="서명 이미지 파일을 찾을 수 없습니다.")
    return FileResponse(file_path, media_type="image/png")


@app.get("/api/consents/{consent_id}/pdf", response_model=None)
async def download_consent_pdf(request: Request, consent_id: int) -> StreamingResponse:
    _require_authenticated_api(request)
    try:
        consent = get_consent(consent_id)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    signature_path = resolve_signature_path(consent["signature_image_path"])
    pdf_bytes = build_consent_pdf(consent, signature_path)
    filename = f"consent_{consent_id}_{datetime.now().strftime('%Y%m%d')}.pdf"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(iter([pdf_bytes]), media_type="application/pdf", headers=headers)


@app.post("/api/tickets/{ticket_id}/deduct")
async def deduct_ticket(
    request: Request,
    ticket_id: int,
    payload: TicketDeductionPayload,
) -> dict:
    _require_authenticated_api(request)
    try:
        ticket = deduct_ticket_sessions(ticket_id=ticket_id, amount=payload.amount)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    return {
        "message": f"{ticket['customer_name']} 고객의 티켓이 {payload.amount}회 차감되었습니다.",
        "ticket": ticket,
    }


@app.post("/api/consents")
async def create_consent(request: Request, payload: ConsentCreatePayload) -> dict:
    _require_authenticated_api(request)
    try:
        consent = create_consent_form(
            customer_id=payload.customer_id,
            customer_name=payload.customer_name,
            phone=payload.phone,
            treatment_name=payload.treatment_name,
            agreement_items=payload.agreement_items,
            notes=payload.notes,
            signature_data_url=payload.signature_data_url,
        )
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    return {
        "message": f"{consent['customer_name']} 고객의 전자 동의서가 저장되었습니다.",
        "consent": consent,
    }


@app.get("/api/admin/settings")
async def get_admin_settings(request: Request) -> dict:
    _require_authenticated_api(request)
    with get_connection() as connection:
        customer_count = connection.execute("SELECT COUNT(*) AS count FROM customers").fetchone()["count"]
        consent_count = connection.execute("SELECT COUNT(*) AS count FROM consent_forms").fetchone()["count"]
        visit_count = connection.execute("SELECT COUNT(*) AS count FROM visit_records").fetchone()["count"]
    return {
        "username": request.session.get("username", ADMIN_USERNAME),
        "app_version": APP_VERSION,
        "database_file": DB_PATH.name,
        "database_size_kb": round(DB_PATH.stat().st_size / 1024, 1) if DB_PATH.exists() else 0,
        "backup_directory": str(BACKUP_DIR.relative_to(BASE_DIR).as_posix()),
        "customer_count": customer_count,
        "consent_count": consent_count,
        "visit_count": visit_count,
    }


@app.get("/api/admin/backup")
async def download_backup(request: Request) -> FileResponse:
    """Create and download a consistent SQLite snapshot."""

    _require_authenticated_api(request)
    filename = f"cheongdam_atelier_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sqlite3"
    file_descriptor, temp_name = tempfile.mkstemp(suffix=".sqlite3")
    os.close(file_descriptor)
    temp_file = Path(temp_name)
    create_backup_snapshot(temp_file)
    return FileResponse(
        temp_file,
        media_type="application/x-sqlite3",
        filename=filename,
        background=BackgroundTask(_cleanup_temp_file, temp_file),
    )


def _guard_page(request: Request, file_path: Path) -> FileResponse | RedirectResponse:
    """Redirect unauthenticated page loads to the login screen."""

    if not _is_authenticated(request):
        next_path = quote(request.url.path)
        return RedirectResponse(url=f"/login?next={next_path}", status_code=303)
    return FileResponse(file_path)


def _is_authenticated(request: Request) -> bool:
    return bool(request.session.get("authenticated"))


def _require_authenticated_api(request: Request) -> None:
    if not _is_authenticated(request):
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")


def _build_summary(customers: list[dict]) -> dict[str, int]:
    tickets = [ticket for customer in customers for ticket in customer["tickets"]]
    low_balance_ids = {
        ticket["id"] for ticket in tickets if 0 < ticket["remaining_sessions"] <= 2
    }
    expiring_soon_ids = {
        ticket["id"]
        for ticket in tickets
        if ticket["days_until_expiry"] is not None and ticket["days_until_expiry"] <= 14
    }

    return {
        "customer_count": len(customers),
        "vip_count": sum(customer["grade"] == "VIP" for customer in customers),
        "remaining_sessions_total": sum(ticket["remaining_sessions"] for ticket in tickets),
        "low_balance_count": len(low_balance_ids),
        "expiring_soon_count": len(expiring_soon_ids),
        "focus_count": len(low_balance_ids | expiring_soon_ids),
    }


def _cleanup_temp_file(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass
