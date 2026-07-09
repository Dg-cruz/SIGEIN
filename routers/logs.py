import io
from typing import List

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse, StreamingResponse
from openpyxl import Workbook
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Table, TableStyle
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_user
from models import Log
from services.audit_logs_service import build_log_rows, fmt_dt, log_list_template_context, query_logs, tipo_label
from templating import templates

router = APIRouter(prefix="/logs", tags=["Logs"])


@router.get("/")
def listar_logs(
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    if not user:
        return RedirectResponse("/login")

    return templates.TemplateResponse(
        "logs_list.html",
        log_list_template_context(db, user, request),
    )


def export_log_list_context(db: Session, *, paiol_only: bool = False) -> List[list]:
    logs = query_logs(db, paiol_only=paiol_only)
    return [["Data/Hora", "Usuário", "Tipo", "IP", "Ação"]] + [
        [fmt_dt(l.data_hora), l.usuario or "", tipo_label(l.tipo), l.ip or "", l.acao or ""]
        for l in logs
    ]


@router.get("/export/pdf")
def export_logs_pdf(db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    if not user:
        return RedirectResponse("/login")

    data = export_log_list_context(db)
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    elements = []
    styles = getSampleStyleSheet()
    elements.append(Paragraph("Auditoria do Sistema — SIGEIN", styles["Title"]))
    elements.append(Paragraph(f"Exportado por: {user}", styles["Normal"]))
    elements.append(Paragraph("<br/>", styles["Normal"]))

    table = Table(data, colWidths=[110, 90, 70, 70, 200])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eef5")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 9),
                ("FONTSIZE", (0, 1), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    elements.append(table)
    doc.build(elements)
    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=auditoria_sigen.pdf"},
    )


@router.get("/export/xlsx")
def export_logs_xlsx(db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    if not user:
        return RedirectResponse("/login")

    data = export_log_list_context(db)
    wb = Workbook()
    ws = wb.active
    ws.title = "Auditoria"
    for row in data:
        ws.append(row)
    stream = io.BytesIO()
    wb.save(stream)
    stream.seek(0)
    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=auditoria_sigen.xlsx"},
    )
