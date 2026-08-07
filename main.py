"""FastAPI application and command-line entry point for hybrid resume parsing."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import uvicorn
from fastapi import FastAPI, File, Request, UploadFile
from fastapi.responses import JSONResponse

from extract_text import TextExtractionError, extract_text
from llm_extractor import LLMExtractionError, extract_with_gemini
from merge import merge_resume_data
from regex_extractor import extract_contact_data

app = FastAPI(title="Hybrid Resume Parser", version="1.0.0")


class ResumeProcessingError(Exception):
    """Application-level error returned in a stable, readable JSON format."""

    def __init__(self, message: str, status_code: int = 422) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


@app.exception_handler(ResumeProcessingError)
async def processing_error_handler(_: Request, exc: ResumeProcessingError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"error": {"message": exc.message}})


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
