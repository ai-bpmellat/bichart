"""Reporting HTTP routes: PDF / Excel export."""

from __future__ import annotations

import os
import time
from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from modules.identity.session import is_authenticated
from modules.reporting.excel import generate_llm_excel
from modules.reporting.pdf import generate_llm_pdf
from shared.paths import EXPORTS_DIR

router = APIRouter(tags=["reporting"])


class PDFExportRequest(BaseModel):
    title: str
    explanation: str
    data: Optional[list] = None
    analysis: Optional[str] = None
    chart_image: Optional[str] = None
    chart_images: Optional[list] = None  # list of {image, title, icon} for all 4 charts


class ExcelExportRequest(BaseModel):
    title: str
    explanation: str
    data: Optional[list] = None
    analysis: Optional[str] = None


@router.post("/api/export_pdf")
def export_pdf(req: PDFExportRequest, request: Request):
    if not is_authenticated(request.session):
        return JSONResponse(status_code=401, content={"error": "Authentication required."})

    try:
        stamp = time.strftime("%Y%m%d%H%M%S")
        filename = f"report{stamp}.pdf"
        filepath = os.path.join(EXPORTS_DIR, filename)

        generate_llm_pdf(
            output_path=filepath,
            title=req.title,
            explanation=req.explanation,
            data=req.data,
            analysis=req.analysis,
            chart_image=req.chart_image,
            chart_images=req.chart_images,
        )

        return FileResponse(
            path=filepath,
            filename=filename,
            media_type="application/pdf",
        )
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"PDF generation failed: {e}"})


@router.post("/api/export_excel")
def export_excel(req: ExcelExportRequest, request: Request):
    if not is_authenticated(request.session):
        return JSONResponse(status_code=401, content={"error": "Authentication required."})

    try:
        stamp = time.strftime("%Y%m%d%H%M%S")
        filename = f"report{stamp}.xlsx"
        filepath = os.path.join(EXPORTS_DIR, filename)

        generate_llm_excel(
            output_path=filepath,
            title=req.title,
            explanation=req.explanation,
            data=req.data,
            analysis=req.analysis,
        )

        return FileResponse(
            path=filepath,
            filename=filename,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"Excel generation failed: {e}"})
