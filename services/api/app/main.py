"""MOSAIC FastAPI application."""

from hashlib import sha256
from pathlib import Path
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .auth import AuthenticatedUser, AuthenticationError, SupabaseJWTVerifier
from .config import Settings, get_settings
from .database import Database
from .schemas import (
    CaseCreate,
    CaseResponse,
    DocumentKind,
    DocumentResponse,
    HealthResponse,
    LoginRequest,
    TokenResponse,
    UserResponse,
)
from .storage import StorageError, SupabaseStorage

bearer = HTTPBearer(auto_error=False)


def _build_services(settings: Settings):
    database = Database(settings.database_url) if settings.database_url else None
    storage = None
    verifier = None
    if settings.supabase_url and settings.supabase_secret_key:
        storage = SupabaseStorage(
            str(settings.supabase_url), settings.supabase_secret_key, settings.storage_bucket
        )
    if settings.supabase_url and settings.supabase_publishable_key:
        verifier = SupabaseJWTVerifier(
            str(settings.supabase_url), settings.supabase_publishable_key
        )
    return database, storage, verifier


def create_app(*, settings=None, database=None, storage=None, verifier=None) -> FastAPI:
    settings = settings or get_settings()
    defaults = _build_services(settings)
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="Officer-facing API for tender and bidder document verification.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.settings = settings
    app.state.database = database or defaults[0]
    app.state.storage = storage or defaults[1]
    app.state.verifier = verifier or defaults[2]

    @app.get("/health", response_model=HealthResponse, tags=["system"])
    def health(request: Request):
        configured = all(
            (request.app.state.database, request.app.state.storage, request.app.state.verifier)
        )
        return {"status": "ok", "configured": configured}

    @app.post("/v1/auth/login", response_model=TokenResponse, tags=["authentication"])
    def login(body: LoginRequest, request: Request):
        verifier_service = require_service(request, "verifier")
        try:
            return verifier_service.sign_in(body.email, body.password.get_secret_value())
        except AuthenticationError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc

    @app.get("/v1/me", response_model=UserResponse, tags=["authentication"])
    def me(user: Annotated[AuthenticatedUser, Depends(current_user)]):
        return {"id": user.id, "email": user.email}

    @app.post(
        "/v1/cases",
        response_model=CaseResponse,
        status_code=status.HTTP_201_CREATED,
        tags=["cases"],
    )
    def create_case(
        body: CaseCreate,
        request: Request,
        user: Annotated[AuthenticatedUser, Depends(current_user)],
    ):
        database_service = require_service(request, "database")
        return database_service.create_case(user.id, body.tender_title, body.description)

    @app.get("/v1/cases/{case_id}", response_model=CaseResponse, tags=["cases"])
    def get_case(
        case_id: UUID,
        request: Request,
        user: Annotated[AuthenticatedUser, Depends(current_user)],
    ):
        database_service = require_service(request, "database")
        case = database_service.get_case(case_id, user.id)
        if case is None:
            raise HTTPException(status_code=404, detail="Case not found")
        return case

    @app.post(
        "/v1/cases/{case_id}/documents",
        response_model=DocumentResponse,
        status_code=status.HTTP_201_CREATED,
        tags=["documents"],
    )
    async def upload_document(
        case_id: UUID,
        request: Request,
        user: Annotated[AuthenticatedUser, Depends(current_user)],
        kind: Annotated[DocumentKind, Form()],
        file: Annotated[UploadFile, File(description="Tender or bidder PDF")],
    ):
        database_service = require_service(request, "database")
        storage_service = require_service(request, "storage")
        if database_service.get_case(case_id, user.id) is None:
            raise HTTPException(status_code=404, detail="Case not found")
        if file.content_type != "application/pdf":
            raise HTTPException(status_code=415, detail="Only PDF uploads are supported currently")
        content = await file.read(request.app.state.settings.max_upload_bytes + 1)
        if not content:
            raise HTTPException(status_code=400, detail="Uploaded PDF is empty")
        if len(content) > request.app.state.settings.max_upload_bytes:
            raise HTTPException(status_code=413, detail="Uploaded PDF exceeds the size limit")
        if not content.startswith(b"%PDF-"):
            raise HTTPException(status_code=400, detail="Uploaded file is not a valid PDF header")
        original_filename = Path(file.filename or "document.pdf").name
        document_id = uuid4()
        object_path = f"{user.id}/{case_id}/{document_id}/{original_filename}"
        try:
            storage_service.upload(object_path, content, file.content_type)
        except StorageError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        record = {
            "id": document_id,
            "case_id": case_id,
            "created_by": UUID(user.id),
            "kind": kind.value,
            "bucket": request.app.state.settings.storage_bucket,
            "object_path": object_path,
            "original_filename": original_filename,
            "content_type": file.content_type,
            "size_bytes": len(content),
            "sha256": sha256(content).hexdigest(),
        }
        try:
            return database_service.create_document(record)
        except Exception:
            try:
                storage_service.remove([object_path])
            except StorageError:
                pass
            raise

    @app.get(
        "/v1/cases/{case_id}/documents",
        response_model=list[DocumentResponse],
        tags=["documents"],
    )
    def list_documents(
        case_id: UUID,
        request: Request,
        user: Annotated[AuthenticatedUser, Depends(current_user)],
    ):
        database_service = require_service(request, "database")
        if database_service.get_case(case_id, user.id) is None:
            raise HTTPException(status_code=404, detail="Case not found")
        return database_service.list_documents(case_id, user.id)

    return app


def require_service(request: Request, name: str):
    service = getattr(request.app.state, name, None)
    if service is None:
        raise HTTPException(status_code=503, detail=f"{name.title()} is not configured")
    return service


def current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> AuthenticatedUser:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Bearer token required")
    verifier = require_service(request, "verifier")
    try:
        return verifier.verify(credentials.credentials)
    except AuthenticationError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


app = create_app()
