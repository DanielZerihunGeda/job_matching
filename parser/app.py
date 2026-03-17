from __future__ import annotations

import asyncio
import logging
import os
import re
import tempfile

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from langchain_community.document_loaders import PyPDFium2Loader, Docx2txtLoader

MAX_BYTES = 5 * 1024 * 1024
ALLOWED_EXT = {".pdf", ".docx", ".doc"}

app = FastAPI()
logger = logging.getLogger("parser")


def _extract_text(filename: str, data: bytes) -> str | None:
    suffix = (os.path.splitext(filename)[1] or ".pdf").lower()
    if suffix not in ALLOWED_EXT:
        return None

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp:
        temp.write(data)
        path = temp.name

    try:
        if suffix == ".pdf":
            loader = PyPDFium2Loader(path)
            docs = loader.load()
            text = "\n".join(d.page_content for d in docs) if docs else None
        else:
            loader = Docx2txtLoader(path)
            docs = loader.load()
            text = "\n".join(d.page_content for d in docs) if docs else None
    finally:
        if path and os.path.exists(path):
            os.unlink(path)

    if text:
        text = re.sub(r"\n{2,}", "\n", text)
        text = re.sub(r"\t{2,}", "\t", text)
        return text
    return None


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})


@app.post("/parse")
async def parse(file: UploadFile):
    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="Missing file")

    data = await file.read()
    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="File too large")

    try:
        text = await asyncio.to_thread(_extract_text, file.filename, data)
    except Exception:
        logger.exception("Document extraction failed")
        raise HTTPException(status_code=500, detail="Document parsing failed")

    if not text:
        raise HTTPException(status_code=422, detail="Unsupported or empty document")

    return JSONResponse({"text": text})
