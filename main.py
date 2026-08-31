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
from sqlalchemy.exc import SQLAlchemyError

from database import Base, engine
from extract_text import TextExtractionError, extract_text
from llm_extractor import LLMExtractionError, extract_with_gemini
from merge import merge_resume_data
from regex_extractor import extract_contact_data

app = FastAPI(title="Resume Parser & User Management API", version="2.0.0")


class ResumeProcessingError(Exception):
    """Application-level error returned in a stable, readable JSON format."""

    def __init__(self, message: str, status_code: int = 422) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


@app.exception_handler(ResumeProcessingError)
async def processing_error_handler(_: Request, exc: ResumeProcessingError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"error": {"message": exc.message}})


@app.exception_handler(HTTPException)
async def http_error_handler(_: Request, exc: HTTPException) -> JSONResponse:
    """Keep router errors in one predictable JSON envelope."""
    return JSONResponse(status_code=exc.status_code, content={"error": {"message": exc.detail}})


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"error": {"message": "Invalid request data.", "details": exc.errors()}},
    )


@app.on_event("startup")
def create_database_tables() -> None:
    """Create SQLite tables automatically on the first application start."""
    try:
        # Importing models registers all table classes with SQLAlchemy metadata.
        import models  # noqa: F401

        Base.metadata.create_all(bind=engine)
    except SQLAlchemyError as exc:
        raise RuntimeError("Database initialization failed.") from exc


def parse_resume(file_bytes: bytes, filename: str) -> dict:
    """Run extraction, regex parsing, Gemini parsing, and merge in one reusable pipeline."""
    extension = Path(filename).suffix.lower()
    if extension not in {".pdf", ".docx"}:
        raise ResumeProcessingError("Unsupported file type. Upload a .pdf or .docx file.", 415)
    try:
        text = extract_text(file_bytes, extension)
        contact = extract_contact_data(text)
        llm_data = extract_with_gemini(text)
        return merge_resume_data(contact, llm_data).model_dump(mode="json")
    except TextExtractionError as exc:
        raise ResumeProcessingError(str(exc), 422) from exc
    except LLMExtractionError as exc:
        raise ResumeProcessingError(str(exc), 502) from exc


# Routers are imported after parse_resume so resume_routes can reuse this exact function.
from routers.auth_routes import router as auth_router  # noqa: E402
from routers.profile_routes import router as profile_router  # noqa: E402
from routers.resume_routes import router as resume_router  # noqa: E402
from routers.internship_routes import router as internship_router  # noqa: E402

app.include_router(auth_router)
app.include_router(profile_router)
app.include_router(resume_router)
app.include_router(internship_router)

WEB_DIRECTORY = Path("web")
app.mount("/web", StaticFiles(directory=WEB_DIRECTORY), name="web")


@app.get("/", include_in_schema=False)
def web_dashboard() -> FileResponse:
    return FileResponse(WEB_DIRECTORY / "index.html")


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
