"""Contact matching, spreadsheet import, and CSV / Excel / VCF export."""

import csv
import io
import re
from decimal import Decimal, InvalidOperation
from urllib.parse import quote

from django.utils import timezone
from openpyxl import Workbook, load_workbook

from apps.crm.models import Contact, Tag, TimelineEvent

PHONE_RE = re.compile(r"\d+")

SYSTEM_FIELDS = [
    ("name", "Full name"),
    ("email", "Email"),
    ("mobile", "Contact number"),
    ("currently_studying", "Currently studying"),
    ("year_of_study", "Current year of study"),
    ("college", "College name with location"),
    ("follows_instagram", "Following on Instagram"),
    ("whatsapp", "WhatsApp"),
    ("branch", "Branch"),
    ("location", "Location"),
    ("source", "Source"),
    ("contact_type", "Contact type"),
    ("notes", "Notes"),
    ("tags", "Tags"),
]

FIELD_ALIASES = {
    "name": {"name", "full name", "student name", "student", "contact name"},
    "mobile": {"mobile", "phone", "phone no", "phone number", "mobile number", "contact", "contact number", "mob"},
    "email": {"email", "e-mail", "mail", "email id"},
    "currently_studying": {"currently studying", "currently studying?", "studying", "is studying"},
    "year_of_study": {
        "current year of study",
        "year of study",
        "year",
        "study year",
        "current year",
    },
    "college": {
        "college",
        "college name",
        "college name with location",
        "collegename with location",
        "institute",
        "university",
    },
    "follows_instagram": {
        "following on inst",
        "following on inst?",
        "following on instagram",
        "following on instagram?",
        "are you following us on insta",
        "are you following us on insta?",
        "are you following us on instagram",
        "instagram follow",
        "insta follow",
    },
    "whatsapp": {"whatsapp", "whatsapp number", "wa", "whatsapp no"},
    "branch": {"branch", "department", "dept", "stream"},
    "location": {"location", "city", "place"},
    "source": {"source", "lead from", "lead source", "from"},
    "contact_type": {"type", "contact type", "role"},
    "notes": {"notes", "note", "remarks", "comment"},
    "tags": {"tags", "tag", "group", "groups"},
}


def digits_only(value):
    return "".join(PHONE_RE.findall(str(value or "")))


def mobile_key(value):
    raw = str(value or "").strip()
    if raw.endswith(".0"):
        raw = raw[:-2]
    digits = digits_only(raw)
    if len(digits) >= 10:
        return digits[-10:]
    return ""


def find_by_mobile(value, exclude_pk=None):
    key = mobile_key(value)
    if not key:
        return None
    qs = Contact.objects.filter(mobile_key=key)
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    return qs.first()


def find_by_name(value, exclude_pk=None):
    name = re.sub(r"\s+", " ", str(value or "").strip())
    if not name:
        return None
    qs = Contact.objects.filter(name__iexact=name)
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    return qs.order_by("-updated_at").first()


def find_existing_contact(data, exclude_pk=None):
    """Same mobile, or the same name from an earlier sheet."""
    found = find_by_mobile(data.get("mobile") or data.get("whatsapp"), exclude_pk=exclude_pk)
    if found:
        return found
    return find_by_name(data.get("name"), exclude_pk=exclude_pk)


def log_event(contact, kind, title, detail=""):
    TimelineEvent.objects.create(contact=contact, kind=kind, title=title, detail=detail or "")
    contact.touch()


def parse_instagram_reply(value):
    """Sheet answers: 'Yes I follow' or 'I will follow now'."""
    text = re.sub(r"[^a-z0-9 ]+", " ", str(value or "").strip().lower())
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return ""
    if text in {"will", "i will follow now", "will follow now", "i will follow", "i ll follow now", "ill follow now"} or "will follow" in text or "follow now" in text:
        return "will"
    if (
        text in {"yes", "y", "yes i follow", "i follow", "following"}
        or "yes i follow" in text
        or "already following" in text
        or text.startswith("yes")
    ):
        return "yes"
    if text in {"no", "n", "not following"}:
        return "no"
    return ""


def as_yes_no(value):
    text = str(value or "").strip().lower()
    if text in {"yes", "y", "true", "1"}:
        return True
    if text in {"no", "n", "false", "0"}:
        return False
    return None


def apply_tags(contact, raw):
    if not raw:
        return
    parts = re.split(r"[,;|]", str(raw))
    for part in parts:
        name = part.strip()
        if not name:
            continue
        tag, _ = Tag.objects.get_or_create(name=name[:80])
        contact.tags.add(tag)


def fill_contact(contact, data, mode):
    """mode is create, update (overwrite non-empty), or merge (fill blanks only)."""
    text_fields = [
        "name",
        "mobile",
        "whatsapp",
        "email",
        "college",
        "year_of_study",
        "branch",
        "location",
        "source",
        "notes",
        "contact_type",
    ]
    for field in text_fields:
        incoming = (data.get(field) or "").strip()
        if field == "contact_type":
            valid = {c[0] for c in Contact.Type.choices}
            incoming = incoming.lower().replace(" ", "_")
            if incoming not in valid:
                incoming = ""
        if field == "email":
            incoming = incoming.lower()
            if "@" not in incoming or incoming in {"n/a", "na", "none", "null", "-"}:
                continue
        if not incoming:
            continue
        current = getattr(contact, field) or ""
        if mode == "merge" and current and field != "notes":
            continue
        if field == "notes" and mode == "merge" and current:
            if incoming not in current:
                setattr(contact, field, current.rstrip() + "\n" + incoming)
            continue
        if field == "email":
            incoming = incoming.lower()
        setattr(contact, field, incoming)
    if "currently_studying" in data:
        parsed = as_yes_no(data.get("currently_studying"))
        if not (parsed is None and (mode == "merge" or not str(data.get("currently_studying") or "").strip())):
            contact.currently_studying = parsed
    raw_instagram = data.get("instagram_reply", data.get("follows_instagram"))
    if raw_instagram is not None and str(raw_instagram).strip():
        reply = parse_instagram_reply(raw_instagram)
        if reply or mode != "merge":
            if reply:
                contact.instagram_reply = reply
                contact.follows_instagram = reply == "yes"
    key = mobile_key(contact.mobile or contact.whatsapp)
    if key:
        contact.mobile_key = key
    contact.save()
    apply_tags(contact, data.get("tags"))
    return contact


def read_tabular(path):
    name = str(path).lower()
    if name.endswith(".csv"):
        return _read_csv(path)
    if name.endswith(".xls") and not name.endswith(".xlsx"):
        return _read_xls(path)
    return _read_xlsx(path)


def _read_csv(path):
    raw = open(path, "rb").read()
    text = raw.decode("utf-8-sig", errors="replace")
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.reader(io.StringIO(text), dialect)
    rows = [list(row) for row in reader if any(str(c).strip() for c in row)]
    if not rows:
        return [], []
    return _split_header(rows)


def _read_xlsx(path):
    wb = load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    rows = []
    for row in ws.iter_rows(values_only=True):
        values = ["" if cell is None else str(cell).strip() for cell in row]
        if any(values):
            rows.append(values)
    wb.close()
    return _split_header(rows)


def _read_xls(path):
    try:
        import xlrd
    except ImportError as exc:
        raise ValueError("Save the file as .xlsx or .csv. .xls support needs the xlrd package.") from exc
    book = xlrd.open_workbook(path)
    sheet = book.sheet_by_index(0)
    rows = []
    for idx in range(sheet.nrows):
        values = [str(sheet.cell_value(idx, col)).strip() for col in range(sheet.ncols)]
        if any(values):
            rows.append(values)
    return _split_header(rows)


def _split_header(rows):
    if not rows:
        return [], []
    headers = [str(cell).strip() or f"Column {i + 1}" for i, cell in enumerate(rows[0])]
    body = []
    for row in rows[1:]:
        padded = list(row) + [""] * (len(headers) - len(row))
        body.append([str(cell).strip() for cell in padded[: len(headers)]])
    return headers, body


def suggest_mapping(headers):
    mapping = {}
    used = set()
    normalized = [(idx, re.sub(r"\s+", " ", header.strip().lower())) for idx, header in enumerate(headers)]
    for field, aliases in FIELD_ALIASES.items():
        for idx, header in normalized:
            if idx in used:
                continue
            if header in aliases:
                mapping[field] = idx
                used.add(idx)
                break
    return mapping


def row_to_data(row, mapping):
    data = {}
    for field, idx in mapping.items():
        if idx is None or idx == "" or int(idx) >= len(row):
            continue
        data[field] = row[int(idx)]
    return data


def preview_rows(body, mapping):
    seen = set()
    preview = []
    for index, row in enumerate(body, start=2):
        data = row_to_data(row, mapping)
        phone = (data.get("mobile") or data.get("whatsapp") or "").strip()
        key = mobile_key(data.get("mobile") or data.get("whatsapp"))
        name = (data.get("name") or "").strip()
        reasons = []
        if not name:
            reasons.append("Name is required")
        if not key:
            reasons.append("A valid 10-digit mobile or WhatsApp number is required")
        existing = find_existing_contact(data)
        if key and key in seen and not existing:
            reasons.append("Duplicate mobile inside this file")
        if key:
            seen.add(key)
        if reasons and not existing:
            status = "invalid"
            action = "skip"
        elif existing:
            status = "duplicate"
            action = "merge"
        else:
            status = "new"
            action = "create"
        preview.append(
            {
                "row": index,
                "status": status,
                "action": action,
                "reasons": reasons,
                "phone": phone,
                "existing_id": existing.pk if existing else None,
                "existing_name": existing.name if existing else "",
                "data": data,
            }
        )
    return preview


def note_sheet_star(contact, seen_ids):
    """One star for each spreadsheet that contains this contact. Counted once per sheet."""
    if not contact or not contact.pk or contact.pk in seen_ids:
        return
    contact.star_count = (contact.star_count or 0) + 1
    contact.save(update_fields=["star_count", "updated_at"])
    seen_ids.add(contact.pk)


def commit_preview(preview, actor=None):
    imported = duplicates = invalid = updated = 0
    errors = ["row,status,reason,name,mobile"]
    seen_ids = set()
    for item in preview:
        data = item.get("data") or {}
        action = item.get("action") or "skip"
        status = item.get("status")
        existing = None
        if item.get("existing_id"):
            existing = Contact.objects.filter(pk=item.get("existing_id")).first()
        if existing is None and status != "invalid":
            existing = find_existing_contact(data)
        if status == "invalid" or (action == "skip" and status != "duplicate"):
            if status == "invalid":
                invalid += 1
            else:
                invalid += 1
            reasons = "; ".join(item.get("reasons") or []) or "Skipped"
            errors.append(
                _csv_line(item.get("row"), status, reasons, data.get("name"), data.get("mobile"))
            )
            continue
        if existing and (status == "duplicate" or action in {"merge", "skip", "update"}):
            mode = "update" if action == "update" else "merge"
            before_email = existing.email or ""
            fill_contact(existing, data, mode)
            note_sheet_star(existing, seen_ids)
            if (existing.email or "") != before_email:
                log_event(existing, "import", "Email added from another sheet", existing.email)
            else:
                log_event(existing, "import", f"Import {mode}", f"Row {item.get('row')}")
            if status == "duplicate" and mode == "merge" and action == "skip":
                duplicates += 1
            else:
                updated += 1
            continue
        contact = Contact(created_by=actor, contact_type=Contact.Type.STUDENT)
        try:
            fill_contact(contact, data, "create")
        except Exception as exc:
            invalid += 1
            errors.append(_csv_line(item.get("row"), "invalid", str(exc), data.get("name"), data.get("mobile")))
            continue
        if not contact.source:
            contact.source = "Import"
            contact.save(update_fields=["source"])
        note_sheet_star(contact, seen_ids)
        log_event(contact, "import", "Imported contact", f"Row {item.get('row')}")
        imported += 1
    return {
        "imported": imported,
        "duplicates": duplicates,
        "invalid": invalid,
        "updated": updated,
        "total": len(preview),
        "error_csv": "\n".join(errors) + "\n",
    }


def _csv_line(*parts):
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["" if part is None else part for part in parts])
    return buf.getvalue().strip()


def contacts_to_csv(contacts):
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        ["Full name", "Email", "Contact number", "Currently studying", "Year of study", "College with location", "Following on Instagram"]
    )
    for contact in contacts:
        writer.writerow(
            [
                contact.name,
                contact.email,
                contact.mobile,
                "Yes" if contact.currently_studying else ("No" if contact.currently_studying is False else ""),
                contact.year_of_study,
                contact.college,
                "Yes" if contact.instagram_reply == "yes" or contact.follows_instagram else (
                    "I will follow now" if contact.instagram_reply == "will" else ""
                ),
            ]
        )
    return buf.getvalue()


def contacts_to_xlsx(contacts):
    wb = Workbook()
    ws = wb.active
    ws.title = "Contacts"
    ws.append(["Full name", "Email", "Contact number", "Currently studying", "Year of study", "College with location", "Following on Instagram"])
    for contact in contacts:
        ws.append(
            [
                contact.name,
                contact.email,
                contact.mobile,
                "Yes" if contact.currently_studying else ("No" if contact.currently_studying is False else ""),
                contact.year_of_study,
                contact.college,
                "Yes" if contact.instagram_reply == "yes" or contact.follows_instagram else (
                    "I will follow now" if contact.instagram_reply == "will" else ""
                ),
            ]
        )
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def contacts_to_vcf(contacts):
    cards = []
    for contact in contacts:
        tel = contact.mobile or contact.whatsapp
        if not tel:
            continue
        name = (contact.name or "Contact").replace("\n", " ").replace("\r", " ")
        lines = ["BEGIN:VCARD", "VERSION:3.0", f"FN:{name}", f"TEL:{tel}"]
        if contact.email:
            lines.append(f"EMAIL:{contact.email}")
        if contact.college:
            org = contact.college
            if contact.branch:
                org = f"{org} - {contact.branch}"
            lines.append(f"ORG:{org}")
        lines.append("END:VCARD")
        cards.append("\n".join(lines))
    return "\n".join(cards) + ("\n" if cards else "")


def render_whatsapp(body, contact, enquiry=None):
    amount = ""
    title = ""
    course = ""
    if enquiry:
        title = enquiry.title or ""
        course = enquiry.course_name or enquiry.title or ""
        if enquiry.price is not None:
            amount = str(enquiry.price)
    values = {
        "name": contact.name if contact else "",
        "college": contact.college if contact else "",
        "project": title,
        "course": course,
        "date": timezone.localdate().isoformat(),
        "amount": amount,
    }
    text = body or ""
    for key, value in values.items():
        text = text.replace("{" + key + "}", value)
    return text


def whatsapp_link(contact, message):
    key = mobile_key(contact.whatsapp or contact.mobile)
    if not key:
        return ""
    return f"https://wa.me/91{key}?text={quote(message or '')}"


def money(value):
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _clean_phone_text(value):
    raw = str(value or "").strip()
    if raw.endswith(".0"):
        raw = raw[:-2]
    return raw


def repair_contact_phones():
    """Drop Excel '.0' from numbers and rebuild the mobile match key."""
    fixed = 0
    for contact in Contact.objects.all().iterator():
        mobile = _clean_phone_text(contact.mobile)
        whatsapp = _clean_phone_text(contact.whatsapp)
        key = mobile_key(mobile or whatsapp)
        if mobile == (contact.mobile or "") and whatsapp == (contact.whatsapp or "") and key == (contact.mobile_key or ""):
            continue
        clash = Contact.objects.filter(mobile_key=key).exclude(pk=contact.pk).exists() if key else False
        if clash:
            continue
        contact.mobile = mobile
        contact.whatsapp = whatsapp
        contact.mobile_key = key
        contact.save(update_fields=["mobile", "whatsapp", "mobile_key", "updated_at"])
        fixed += 1
    return fixed


def backfill_contacts_from_imports():
    """Apply saved spreadsheets onto contacts that were imported before reply parsing."""
    from apps.crm.models import ImportBatch

    phones = repair_contact_phones()
    updated = skipped = 0
    for batch in ImportBatch.objects.exclude(upload="").order_by("pk"):
        if not batch.upload:
            continue
        try:
            _headers, body = read_tabular(batch.upload.path)
        except Exception:
            continue
        mapping = batch.mapping or suggest_mapping(_headers)
        if "follows_instagram" not in mapping and "name" not in mapping:
            continue
        for row in body:
            data = row_to_data(row, mapping)
            phone = _clean_phone_text(data.get("mobile") or data.get("whatsapp"))
            contact = find_by_mobile(phone) or find_by_name(data.get("name"))
            if not contact:
                skipped += 1
                continue
            reply = parse_instagram_reply(data.get("follows_instagram"))
            changed = False
            if reply and contact.instagram_reply != reply:
                contact.instagram_reply = reply
                contact.follows_instagram = reply == "yes"
                changed = True
            year = (data.get("year_of_study") or "").strip()
            studying = (data.get("currently_studying") or "").strip()
            if not year and studying and as_yes_no(studying) is None:
                year = studying
            if year and not (contact.year_of_study or "").strip():
                contact.year_of_study = year[:80]
                changed = True
            college = (data.get("college") or "").strip()
            if college and not (contact.college or "").strip():
                contact.college = college[:255]
                changed = True
            yes_no = as_yes_no(studying)
            if yes_no is not None and contact.currently_studying is None:
                contact.currently_studying = yes_no
                changed = True
            if phone and (contact.mobile or "").endswith(".0"):
                contact.mobile = phone
                contact.mobile_key = mobile_key(phone)
                changed = True
            if changed:
                contact.save()
                updated += 1
    apply_sheet_stars()
    return {"phones": phones, "updated": updated, "unmatched": skipped}


def apply_sheet_stars():
    """Set each contact's stars to how many different spreadsheets include them."""
    from collections import defaultdict

    from apps.crm.models import ImportBatch

    sheets = defaultdict(set)
    for batch in ImportBatch.objects.exclude(upload="").order_by("pk"):
        if not batch.upload:
            continue
        sheet_name = (batch.original_name or str(batch.pk)).strip().lower()
        try:
            headers, body = read_tabular(batch.upload.path)
        except Exception:
            continue
        mapping = batch.mapping or suggest_mapping(headers)
        if not mapping:
            continue
        seen_here = set()
        for row in body:
            data = row_to_data(row, mapping)
            if not (data.get("name") or data.get("mobile") or data.get("whatsapp")):
                continue
            contact = find_by_mobile(data.get("mobile") or data.get("whatsapp")) or find_by_name(data.get("name"))
            if not contact or contact.pk in seen_here:
                continue
            seen_here.add(contact.pk)
            sheets[contact.pk].add(sheet_name)
    Contact.objects.update(star_count=0)
    for contact_id, names in sheets.items():
        Contact.objects.filter(pk=contact_id).update(star_count=len(names))
    return len(sheets)


def fill_missing_emails_from_imports():
    """Copy an email from a later sheet onto the same student instead of leaving it blank."""
    from apps.crm.models import ImportBatch

    filled = 0
    for batch in ImportBatch.objects.exclude(upload="").order_by("pk"):
        if not batch.upload:
            continue
        try:
            headers, body = read_tabular(batch.upload.path)
        except Exception:
            continue
        mapping = dict(batch.mapping or {})
        suggested = suggest_mapping(headers)
        if "email" in suggested:
            mapping["email"] = suggested["email"]
        if "email" not in mapping:
            continue
        for row in body:
            data = row_to_data(row, mapping)
            email = (data.get("email") or "").strip()
            if "@" not in email:
                continue
            contact = find_existing_contact(data)
            if not contact or (contact.email or "").strip():
                continue
            fill_contact(contact, {"email": email}, "merge")
            filled += 1
    return filled
