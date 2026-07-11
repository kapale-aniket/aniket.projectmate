"""Admin export helpers (Excel / PDF)."""
from io import BytesIO
from django.http import HttpResponse


def export_queryset_xlsx(queryset, filename, columns):
    """
    columns: list of (header, attr_path) e.g. [("Email", "email"), ("Points", "profile.reward_points")]
    """
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append([c[0] for c in columns])
    for obj in queryset:
        row = []
        for _, path in columns:
            val = obj
            for part in path.split("."):
                val = getattr(val, part, "") if val is not None else ""
                if callable(val):
                    val = val()
            row.append(str(val) if val is not None else "")
        ws.append(row)
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    response = HttpResponse(
        buf.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def export_simple_pdf(title, lines, filename="report.pdf"):
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    y = height - 50
    c.setFont("Helvetica-Bold", 14)
    c.drawString(40, y, title)
    y -= 30
    c.setFont("Helvetica", 10)
    for line in lines:
        if y < 50:
            c.showPage()
            y = height - 50
            c.setFont("Helvetica", 10)
        c.drawString(40, y, str(line)[:110])
        y -= 16
    c.save()
    buf.seek(0)
    response = HttpResponse(buf.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
