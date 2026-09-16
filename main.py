"""FastAPI application and command-line entry point for hybrid resume parsing."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import uvicorn
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from fastapi.encoders import jsonable_encoder

from sqlalchemy.exc import SQLAlchemyError

from database import Base, apply_safe_schema_updates, engine
from services.resume_service import ResumeProcessingError, parse_resume

app = FastAPI(title="Resume Parser & User Management API", version="2.0.0")


@app.exception_handler(ResumeProcessingError)
async def processing_error_handler(_: Request, exc: ResumeProcessingError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"error": {"message": exc.message}})


@app.exception_handler(HTTPException)
async def http_error_handler(_: Request, exc: HTTPException) -> JSONResponse:
    """Keep router errors in one predictable JSON envelope."""
    return JSONResponse(status_code=exc.status_code, content={"error": {"message": exc.detail}})


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    errors = exc.errors()
    # Check if any validation error is on a password field
    is_password_error = any(
        any("password" in str(loc).lower() for loc in err.get("loc", ()))
        or "password" in str(err.get("msg", "")).lower()
        or "password" in str(err.get("type", "")).lower()
        for err in errors
    )
    message = "Invalid password" if is_password_error else "Invalid request data."
    return JSONResponse(
        status_code=422,
        # Multipart validation errors can contain raw bytes. Encode them before
        # returning JSON so invalid uploads never trigger a serialization error.
        content={"error": {"message": message, "details": jsonable_encoder(errors)}},
    )


@app.on_event("startup")
def create_database_tables() -> None:
    """Create SQLite tables automatically on the first application start."""
    try:
        # Importing models registers all table classes with SQLAlchemy metadata.
        import models  # noqa: F401

        Base.metadata.create_all(bind=engine)
        apply_safe_schema_updates()
    except SQLAlchemyError as exc:
        raise RuntimeError("Database initialization failed.") from exc


# Routers are imported after parse_resume so resume_routes can reuse this exact function.
from routers.auth_routes import router as auth_router  # noqa: E402
from routers.profile_routes import router as profile_router  # noqa: E402
from routers.resume_routes import router as resume_router  # noqa: E402
from routers.internship_routes import router as internship_router  # noqa: E402
from routers.applications_routes import router as applications_router  # noqa: E402
from routers.assistant_routes import router as assistant_router  # noqa: E402
from routers.cover_letter_routes import router as cover_letter_router  # noqa: E402
from routers.interview_prep_routes import router as interview_prep_router  # noqa: E402

app.include_router(auth_router)
app.include_router(profile_router)
app.include_router(resume_router)
app.include_router(internship_router)
app.include_router(applications_router)
app.include_router(assistant_router)
app.include_router(cover_letter_router)
app.include_router(interview_prep_router)

WEB_DIRECTORY = Path("web")
UPLOADS_DIRECTORY = Path("uploads")
UPLOADS_DIRECTORY.mkdir(parents=True, exist_ok=True)

app.mount("/web", StaticFiles(directory=WEB_DIRECTORY), name="web")
app.mount("/uploads", StaticFiles(directory=UPLOADS_DIRECTORY), name="uploads")

@app.middleware("http")
async def spa_page_refresh_middleware(request: Request, call_next):
    """Serve index.html directly whenever a browser refreshes any top-level page."""
    if request.method == "GET" and "text/html" in request.headers.get("accept", ""):
        segments = [s for s in request.url.path.strip("/").split("/") if s]
        frontend_pages = {
            "login", "register", "dashboard", "profile", "resumes", "internships",
            "matches", "skill-gap", "applications", "cover-letter", "cover-letters",
            "ai-assistant", "assistant", "interview-prep", "interview-preparation",
        }
        if len(segments) == 1 and segments[0] in frontend_pages:
            return FileResponse(
                WEB_DIRECTORY / "index.html",
                headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache", "Expires": "0"},
            )
    return await call_next(request)


@app.get("/", include_in_schema=False)
def web_dashboard() -> FileResponse:
    return FileResponse(
        WEB_DIRECTORY / "index.html",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache", "Expires": "0"},
    )


@app.get("/{frontend_path:path}", include_in_schema=False)
def frontend_routes(frontend_path: str) -> FileResponse:
    """Serve the SPA entry point for client-side InternSphere routes."""
    allowed = {
        "login", "register", "dashboard", "profile", "resumes", "internships",
        "matches", "skill-gap", "applications", "cover-letter", "cover-letters",
        "ai-assistant", "assistant", "interview-prep", "interview-preparation",
    }
    if frontend_path.strip("/").split("/")[0] in allowed:
        return FileResponse(
            WEB_DIRECTORY / "index.html",
            headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache", "Expires": "0"},
        )
    raise HTTPException(status_code=404, detail="Not found.")


@app.post("/parse-resume", summary="Upload a PDF or DOCX resume and receive normalized JSON")
async def parse_resume_endpoint(file: UploadFile = File(...)) -> dict:
    """FastAPI upload endpoint; test it in Swagger at /docs or with curl."""
    return parse_resume(await file.read(), file.filename or "uploaded_resume")


def run_cli(path_string: str) -> None:
    """CLI mode reads a local resume path and pretty-prints the same JSON as the API."""
    path = Path(path_string)
    if not path.is_file():
        raise ResumeProcessingError(f"File not found: {path}", 404)
    result = parse_resume(path.read_bytes(), path.name)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Hybrid Resume Parser")
    parser.add_argument("resume_path", nargs="?", help="Local .pdf or .docx resume path")
    parser.add_argument("--serve", action="store_true", help="Start the FastAPI server")
    parser.add_argument("--host", default="127.0.0.1", help="Server host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Server port (default: 8000)")
    args = parser.parse_args()

    try:
        if args.serve:
            uvicorn.run(app, host=args.host, port=args.port)
        elif args.resume_path:
            run_cli(args.resume_path)
        else:
            parser.error("provide a resume path or use --serve")
    except ResumeProcessingError as exc:
        print(json.dumps({"error": {"message": exc.message}}, indent=2))
        raise SystemExit(1)
