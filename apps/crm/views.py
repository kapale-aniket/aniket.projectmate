from datetime import date, timedelta

from django.contrib import messages
from django.db.models import Count, Q, Sum
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from apps.adminpanel.mixins import AdminRequiredMixin
from apps.crm.models import (
    Contact,
    Document,
    Enquiry,
    FollowUp,
    ImportBatch,
    Payment,
    Tag,
    TestItem,
    WhatsAppTemplate,
)
from apps.crm.services import (
    SYSTEM_FIELDS,
    commit_preview,
    contacts_to_csv,
    contacts_to_vcf,
    contacts_to_xlsx,
    fill_contact,
    find_by_mobile,
    log_event,
    mobile_key,
    money,
    preview_rows,
    read_tabular,
    render_whatsapp,
    suggest_mapping,
    whatsapp_link,
)


def staff_only(view):
    def wrapped(request, *args, **kwargs):
        user = request.user
        allowed = user.is_authenticated and (
            user.is_staff or user.is_superuser or getattr(user, "role", "") == "admin"
        )
        if not allowed:
            return _deny(request)
        return view(request, *args, **kwargs)

    return wrapped


def _deny(request):
    mixin = AdminRequiredMixin()
    mixin.request = request
    return mixin.handle_no_permission()


def _parse_date(value):
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        return None


def _params(request):
    return request.POST if request.method == "POST" else request.GET


def _filtered_contacts(request):
    src = _params(request)
    qs = Contact.objects.prefetch_related("tags").all()
    q = (src.get("q") or "").strip()
    contact_type = (src.get("type") or "").strip()
    college_names = [item.strip() for item in src.getlist("college") if str(item).strip()]
    year = (src.get("year") or "").strip()
    studying = (src.get("studying") or "").strip()
    instagram = (src.get("instagram") or "").strip()
    branch = (src.get("branch") or "").strip()
    source = (src.get("source") or "").strip()
    tag = (src.get("tag") or "").strip()
    added = (src.get("added") or "").strip()
    ids = src.getlist("ids")
    if ids:
        qs = qs.filter(pk__in=ids)
    if q:
        qs = qs.filter(
            Q(name__icontains=q)
            | Q(mobile__icontains=q)
            | Q(whatsapp__icontains=q)
            | Q(email__icontains=q)
            | Q(college__icontains=q)
            | Q(mobile_key__icontains=mobile_key(q) or q)
        )
    if contact_type:
        qs = qs.filter(contact_type=contact_type)
    if college_names:
        college_filter = Q()
        for name in college_names:
            college_filter |= Q(college__iexact=name)
        qs = qs.filter(college_filter)
    if year:
        qs = qs.filter(year_of_study__icontains=year)
    if studying == "yes":
        qs = qs.filter(currently_studying=True)
    elif studying == "no":
        qs = qs.filter(currently_studying=False)
    if instagram == "yes":
        qs = qs.filter(follows_instagram=True)
    elif instagram == "no":
        qs = qs.filter(follows_instagram=False)
    if branch:
        qs = qs.filter(branch__icontains=branch)
    if source:
        qs = qs.filter(source__icontains=source)
    if tag:
        qs = qs.filter(tags__name__iexact=tag)
    if added == "month":
        start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        qs = qs.filter(created_at__gte=start)
    return qs.distinct()


SORT_FIELDS = {
    "stars": "star_count",
    "name": "name",
    "email": "email",
    "mobile": "mobile",
    "year": "year_of_study",
    "college": "college",
    "instagram": "instagram_reply",
}


def _sort_contacts(request, qs):
    sort_by = (request.GET.get("sort_by") or "").strip()
    if not sort_by:
        sort = (request.GET.get("sort") or "stars").strip()
        order = (request.GET.get("order") or "desc").strip().lower()
        sort_by = f"{sort}-{order}"
    if "-" not in sort_by:
        sort_by = "stars-desc"
    sort, _, order = sort_by.partition("-")
    if sort not in SORT_FIELDS:
        sort = "stars"
    if order not in {"asc", "desc"}:
        order = "desc"
    field = SORT_FIELDS[sort]
    prefix = "-" if order == "desc" else ""
    ordered = qs.order_by(f"{prefix}{field}", "name")
    return ordered, sort, order, f"{sort}-{order}"


def _sort_query(request, field):
    current = request.GET.get("sort_by") or "stars-desc"
    sort, _, direction = current.partition("-")
    if sort == field and direction == "desc":
        nxt = "asc"
    elif sort == field and direction == "asc":
        nxt = "desc"
    else:
        nxt = "desc" if field == "stars" else "asc"
    params = request.GET.copy()
    params["sort_by"] = f"{field}-{nxt}"
    params.pop("sort", None)
    params.pop("order", None)
    return params.urlencode()


def _college_choices():
    """Every distinct college name already saved on a contact."""
    seen = set()
    names = []
    for raw in Contact.objects.exclude(college="").values_list("college", flat=True):
        cleaned = " ".join(str(raw).split())
        if not cleaned or cleaned.casefold() in seen:
            continue
        seen.add(cleaned.casefold())
        names.append(cleaned)
    names.sort(key=str.casefold)
    return names


def _filters(request):
    return {
        "q": request.GET.get("q", ""),
        "type": request.GET.get("type", ""),
        "college_selected": [item.strip() for item in request.GET.getlist("college") if item.strip()],
        "colleges": _college_choices(),
        "year": request.GET.get("year", ""),
        "studying": request.GET.get("studying", ""),
        "instagram": request.GET.get("instagram", ""),
        "source": request.GET.get("source", ""),
        "tag": request.GET.get("tag", ""),
        "added": request.GET.get("added", ""),
        "types": Contact.Type.choices,
        "tags": Tag.objects.all(),
    }


@staff_only
def dashboard(request):
    today = timezone.localdate()
    enquiries = Enquiry.objects.all()
    payments = Payment.objects.aggregate(received=Sum("received"), total=Sum("total_amount"))
    received = payments["received"] or 0
    total = payments["total"] or 0
    context = {
        "crm_nav": "dashboard",
        "contacts": Contact.objects.count(),
        "new_contacts": Contact.objects.filter(created_at__date=today).count(),
        "imported": Contact.objects.filter(timeline__kind="import").distinct().count(),
        "enquiry_counts": {
            "new": enquiries.filter(status=Enquiry.Status.NEW).count(),
            "interested": enquiries.filter(status=Enquiry.Status.INTERESTED).count(),
            "follow_up": enquiries.filter(status=Enquiry.Status.FOLLOW_UP).count(),
            "confirmed": enquiries.filter(status__in=[Enquiry.Status.CONFIRMED, Enquiry.Status.IN_PROGRESS]).count(),
            "lost": enquiries.filter(status__in=[Enquiry.Status.LOST, Enquiry.Status.NOT_INTERESTED]).count(),
        },
        "projects_active": enquiries.filter(business=Enquiry.Business.PROJECT, status=Enquiry.Status.IN_PROGRESS).count(),
        "testing_active": enquiries.filter(business=Enquiry.Business.TESTING).exclude(
            status__in=[Enquiry.Status.COMPLETED, Enquiry.Status.LOST]
        ).count(),
        "bugs_open": TestItem.objects.exclude(status=TestItem.Status.CLOSED).count(),
        "class_students": enquiries.filter(business=Enquiry.Business.CLASSES, status=Enquiry.Status.IN_PROGRESS).count(),
        "revenue": received,
        "pending_payments": total - received,
        "commission_pending": (
            Payment.objects.filter(kind=Payment.Kind.COMMISSION).aggregate(
                pending=Sum("total_amount")
            )["pending"]
            or 0
        )
        - (
            Payment.objects.filter(kind=Payment.Kind.COMMISSION).aggregate(got=Sum("received"))["got"]
            or 0
        ),
        "today_followups": FollowUp.objects.filter(next_date=today, status=FollowUp.Status.PENDING).select_related("contact")[:12],
        "overdue": FollowUp.objects.filter(next_date__lt=today, status=FollowUp.Status.PENDING).count(),
        "deadlines": Enquiry.objects.filter(deadline=today).count(),
    }
    return render(request, "adminpanel/crm/dashboard.html", context)


@staff_only
def contact_list(request):
    filtered = _filtered_contacts(request)
    contacts, sort, order, sort_by = _sort_contacts(request, filtered)
    ctx = _filters(request)
    ctx.update({
        "crm_nav": "contacts",
        "contacts": contacts[:500],
        "count": filtered.count(),
        "sort": sort,
        "order": order,
        "sort_by": sort_by,
        "sort_name": _sort_query(request, "name"),
        "sort_email": _sort_query(request, "email"),
        "sort_mobile": _sort_query(request, "mobile"),
        "sort_year": _sort_query(request, "year"),
        "sort_college": _sort_query(request, "college"),
        "sort_instagram": _sort_query(request, "instagram"),
        "sort_stars": _sort_query(request, "stars"),
    })
    return render(request, "adminpanel/crm/contacts.html", ctx)


@staff_only
@require_http_methods(["GET", "POST"])
def contact_edit(request, pk=None):
    contact = get_object_or_404(Contact, pk=pk) if pk else None
    duplicate = None
    if request.method == "POST":
        data = {key: request.POST.get(key, "") for key, _label in SYSTEM_FIELDS}
        data["contact_type"] = request.POST.get("contact_type") or Contact.Type.STUDENT
        data["name"] = request.POST.get("name", "")
        data["mobile"] = request.POST.get("mobile", "")
        data["whatsapp"] = request.POST.get("whatsapp", "")
        data["email"] = request.POST.get("email", "")
        data["college"] = request.POST.get("college", "")
        data["branch"] = request.POST.get("branch", "")
        data["location"] = request.POST.get("location", "")
        data["source"] = request.POST.get("source", "")
        data["notes"] = request.POST.get("notes", "")
        data["tags"] = request.POST.get("tags", "")
        action = request.POST.get("duplicate_action") or ""
        existing = find_by_mobile(data["mobile"] or data["whatsapp"], exclude_pk=contact.pk if contact else None)
        if existing and action not in {"update", "merge", "skip"}:
            return render(
                request,
                "adminpanel/crm/contact_form.html",
                {"crm_nav": "contacts", "contact": contact, "data": data, "duplicate": existing, "types": Contact.Type.choices},
            )
        if existing and action == "skip":
            messages.info(request, "Kept the existing contact. Nothing was changed.")
            return redirect("crm:contact_detail", pk=existing.pk)
        target = existing if existing and action in {"update", "merge"} else contact
        mode = action if action in {"update", "merge"} else ("update" if target else "create")
        if target is None:
            target = Contact(created_by=request.user, contact_type=data["contact_type"] or Contact.Type.STUDENT)
            mode = "create"
        fill_contact(target, data, "create" if mode == "create" else mode)
        referred = request.POST.get("referred_by") or ""
        if referred.isdigit():
            target.referred_by_id = int(referred)
            target.save(update_fields=["referred_by"])
        log_event(target, "contact", "Contact saved", mode)
        messages.success(request, "Contact saved.")
        return redirect("crm:contact_detail", pk=target.pk)
    data = {}
    if contact:
        data = {
            "name": contact.name,
            "mobile": contact.mobile,
            "email": contact.email,
            "college": contact.college,
            "year_of_study": contact.year_of_study,
            "currently_studying": "yes" if contact.currently_studying is True else ("no" if contact.currently_studying is False else ""),
            "follows_instagram": contact.instagram_reply or ("yes" if contact.follows_instagram else ""),
        }
    return render(
        request,
        "adminpanel/crm/contact_form.html",
        {
            "crm_nav": "contacts",
            "contact": contact,
            "data": data,
            "duplicate": duplicate,
            "types": Contact.Type.choices,
            "mediators": Contact.objects.filter(contact_type=Contact.Type.MEDIATOR).order_by("name"),
        },
    )


@staff_only
def contact_detail(request, pk):
    contact = get_object_or_404(
        Contact.objects.prefetch_related("tags", "timeline", "enquiries", "followups", "payments", "documents"),
        pk=pk,
    )
    message = ""
    template_id = request.GET.get("template")
    if template_id and template_id.isdigit():
        tmpl = WhatsAppTemplate.objects.filter(pk=int(template_id)).first()
        if tmpl:
            message = render_whatsapp(tmpl.body, contact, contact.enquiries.first())
    return render(
        request,
        "adminpanel/crm/contact_detail.html",
        {
            "crm_nav": "contacts",
            "contact": contact,
            "templates": WhatsAppTemplate.objects.all(),
            "message": message,
            "wa_link": whatsapp_link(contact, message),
            "enquiries": contact.enquiries.all(),
            "followups": contact.followups.select_related("enquiry").all()[:30],
            "payments": contact.payments.all(),
            "documents": contact.documents.all(),
            "businesses": Enquiry.Business.choices,
            "statuses": Enquiry.Status.choices,
            "sources": Enquiry.Source.choices,
            "channels": FollowUp.Channel.choices,
            "pay_kinds": Payment.Kind.choices,
        },
    )


@staff_only
@require_http_methods(["POST"])
def enquiry_save(request, contact_pk):
    contact = get_object_or_404(Contact, pk=contact_pk)
    enquiry = Enquiry.objects.create(
        contact=contact,
        business=request.POST.get("business") or Enquiry.Business.PROJECT,
        source=request.POST.get("source") or Enquiry.Source.WHATSAPP,
        status=request.POST.get("status") or Enquiry.Status.NEW,
        title=request.POST.get("title") or "Enquiry",
        technology=request.POST.get("technology", ""),
        requirements=request.POST.get("requirements", ""),
        price=money(request.POST.get("price")),
        course_name=request.POST.get("course_name", ""),
        assigned_to=request.user,
    )
    deadline = _parse_date(request.POST.get("deadline"))
    if deadline:
        enquiry.deadline = deadline
        enquiry.save(update_fields=["deadline"])
    log_event(contact, "enquiry", f"{enquiry.get_business_display()} enquiry", enquiry.title)
    messages.success(request, "Enquiry added to this contact.")
    return redirect("crm:contact_detail", pk=contact.pk)


@staff_only
@require_http_methods(["POST"])
def followup_save(request, contact_pk):
    contact = get_object_or_404(Contact, pk=contact_pk)
    enquiry_id = request.POST.get("enquiry") or ""
    follow = FollowUp.objects.create(
        contact=contact,
        enquiry_id=int(enquiry_id) if enquiry_id.isdigit() else None,
        channel=request.POST.get("channel") or FollowUp.Channel.WHATSAPP,
        notes=request.POST.get("notes", ""),
        next_date=_parse_date(request.POST.get("next_date")),
        followed_at=timezone.now(),
        status=FollowUp.Status.DONE if request.POST.get("done") else FollowUp.Status.PENDING,
    )
    log_event(contact, "followup", f"{follow.get_channel_display()} follow-up", follow.notes)
    messages.success(request, "Follow-up saved.")
    return redirect("crm:contact_detail", pk=contact.pk)


@staff_only
@require_http_methods(["POST"])
def payment_save(request, contact_pk):
    contact = get_object_or_404(Contact, pk=contact_pk)
    payment = Payment.objects.create(
        contact=contact,
        kind=request.POST.get("kind") or Payment.Kind.PROJECT,
        total_amount=money(request.POST.get("total_amount")) or 0,
        advance=money(request.POST.get("advance")) or 0,
        received=money(request.POST.get("received")) or 0,
        method=request.POST.get("method", ""),
        notes=request.POST.get("notes", ""),
        paid_on=_parse_date(request.POST.get("paid_on")),
    )
    log_event(contact, "payment", payment.get_kind_display(), f"Received {payment.received}")
    messages.success(request, "Payment saved.")
    return redirect("crm:contact_detail", pk=contact.pk)


@staff_only
@require_http_methods(["POST"])
def document_save(request, contact_pk):
    contact = get_object_or_404(Contact, pk=contact_pk)
    doc = Document.objects.create(
        contact=contact,
        title=request.POST.get("title") or "Document",
        kind=request.POST.get("kind", ""),
        link=request.POST.get("link", ""),
        file=request.FILES.get("file"),
    )
    log_event(contact, "document", doc.title, doc.link)
    messages.success(request, "Document saved.")
    return redirect("crm:contact_detail", pk=contact.pk)


@staff_only
def enquiry_list(request):
    qs = Enquiry.objects.select_related("contact")
    business = request.GET.get("business") or ""
    status = request.GET.get("status") or ""
    if business:
        qs = qs.filter(business=business)
    if status:
        qs = qs.filter(status=status)
    return render(
        request,
        "adminpanel/crm/enquiries.html",
        {
            "crm_nav": "enquiries",
            "enquiries": qs[:300],
            "business": business,
            "status": status,
            "businesses": Enquiry.Business.choices,
            "statuses": Enquiry.Status.choices,
        },
    )


@staff_only
@require_http_methods(["POST"])
def enquiry_status(request, pk):
    enquiry = get_object_or_404(Enquiry, pk=pk)
    enquiry.status = request.POST.get("status") or enquiry.status
    enquiry.save(update_fields=["status", "updated_at"])
    log_event(enquiry.contact, "enquiry", "Enquiry status updated", enquiry.get_status_display())
    return redirect(request.POST.get("next") or "crm:enquiries")


@staff_only
def followup_list(request):
    today = timezone.localdate()
    bucket = request.GET.get("bucket") or "today"
    qs = FollowUp.objects.select_related("contact", "enquiry")
    if bucket == "overdue":
        qs = qs.filter(next_date__lt=today, status=FollowUp.Status.PENDING)
    elif bucket == "upcoming":
        qs = qs.filter(next_date__gt=today, next_date__lte=today + timedelta(days=14))
    elif bucket == "all":
        pass
    else:
        bucket = "today"
        qs = qs.filter(next_date=today)
    return render(
        request,
        "adminpanel/crm/followups.html",
        {"crm_nav": "followups", "followups": qs[:300], "bucket": bucket},
    )


@staff_only
def whatsapp_templates(request):
    if not WhatsAppTemplate.objects.exists():
        _seed_templates()
    if request.method == "POST":
        WhatsAppTemplate.objects.create(name=request.POST.get("name") or "Template", body=request.POST.get("body") or "")
        messages.success(request, "Template saved.")
        return redirect("crm:whatsapp")
    return render(
        request,
        "adminpanel/crm/whatsapp.html",
        {"crm_nav": "whatsapp", "templates": WhatsAppTemplate.objects.all()},
    )


def _seed_templates():
    samples = [
        ("New enquiry", "Hi {name}, thanks for contacting Project Mate. How can we help you today?"),
        ("Project enquiry", "Hi {name}, we received your project enquiry ({project}). I will share the next steps shortly."),
        ("Class enquiry", "Hi {name}, the next {course} batch details are ready. Shall I share the schedule?"),
        ("Testing enquiry", "Hi {name}, we can start testing for {project}. Please share the latest build."),
        ("Follow-up", "Hi {name}, just following up on our last conversation. Are you free today?"),
        ("Payment reminder", "Hi {name}, a reminder that {amount} is pending. Let me know a convenient way to pay."),
        ("Mediator", "Hi {name}, sharing the latest update on the student you referred."),
    ]
    for name, body in samples:
        WhatsAppTemplate.objects.get_or_create(name=name, defaults={"body": body})


@staff_only
def payments(request):
    rows = Payment.objects.select_related("contact").order_by("-created_at")[:300]
    totals = Payment.objects.aggregate(received=Sum("received"), total=Sum("total_amount"))
    return render(
        request,
        "adminpanel/crm/payments.html",
        {
            "crm_nav": "payments",
            "payments": rows,
            "received": totals["received"] or 0,
            "pending": (totals["total"] or 0) - (totals["received"] or 0),
        },
    )


@staff_only
def reports(request):
    by_source = (
        Enquiry.objects.values("source").annotate(total=Count("id")).order_by("-total")
    )
    by_business = Enquiry.objects.values("business").annotate(total=Count("id")).order_by("-total")
    total = Enquiry.objects.count() or 1
    confirmed = Enquiry.objects.filter(
        status__in=[Enquiry.Status.CONFIRMED, Enquiry.Status.IN_PROGRESS, Enquiry.Status.COMPLETED]
    ).count()
    mediators = (
        Contact.objects.filter(contact_type=Contact.Type.MEDIATOR)
        .annotate(referral_count=Count("referrals"))
        .order_by("-referral_count")[:20]
    )
    return render(
        request,
        "adminpanel/crm/reports.html",
        {
            "crm_nav": "reports",
            "by_source": by_source,
            "by_business": by_business,
            "conversion": round(confirmed * 100 / total, 1),
            "mediators": mediators,
            "contacts_month": Contact.objects.filter(
                created_at__gte=timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            ).count(),
        },
    )


@staff_only
def export_contacts(request):
    fmt = (request.GET.get("format") or request.POST.get("format") or "csv").lower()
    contacts = _filtered_contacts(request)
    stamp = timezone.localdate().isoformat()
    if fmt == "vcf":
        body = contacts_to_vcf(contacts)
        response = HttpResponse(body, content_type="text/vcard; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="contacts_{stamp}.vcf"'
        return response
    if fmt == "xlsx":
        body = contacts_to_xlsx(contacts)
        response = HttpResponse(
            body,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = f'attachment; filename="contacts_{stamp}.xlsx"'
        return response
    response = HttpResponse(contacts_to_csv(contacts), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="contacts_{stamp}.csv"'
    return response


def _start_import_batch(upload, user):
    """Save a spreadsheet and return the batch plus how many contact rows it holds."""
    batch = ImportBatch.objects.create(
        original_name=upload.name,
        upload=upload,
        created_by=user,
    )
    try:
        headers, body = read_tabular(batch.upload.path)
    except Exception as exc:
        batch.delete()
        raise ValueError(str(exc)) from exc
    if not headers:
        batch.delete()
        raise ValueError("The spreadsheet has no header row.")
    batch.headers = headers
    batch.total_rows = len(body)
    batch.mapping = {key: value for key, value in suggest_mapping(headers).items()}
    batch.save(update_fields=["headers", "total_rows", "mapping"])
    return batch


@staff_only
@require_http_methods(["POST"])
def import_count(request):
    upload = request.FILES.get("file")
    if not upload:
        return JsonResponse({"ok": False, "message": "Choose a spreadsheet first."}, status=400)
    replace_id = request.POST.get("replace_id") or ""
    if replace_id.isdigit():
        ImportBatch.objects.filter(
            pk=int(replace_id),
            created_by=request.user,
            status=ImportBatch.Status.UPLOADED,
        ).delete()
    try:
        batch = _start_import_batch(upload, request.user)
    except ValueError as exc:
        return JsonResponse({"ok": False, "message": str(exc)}, status=400)
    return JsonResponse(
        {
            "ok": True,
            "total": batch.total_rows,
            "batch_id": batch.pk,
            "name": batch.original_name,
            "map_url": f"/admin/crm/import/{batch.pk}/map/",
        }
    )


@staff_only
@require_http_methods(["GET", "POST"])
def import_contacts(request):
    if request.method == "POST" and request.FILES.get("file"):
        try:
            batch = _start_import_batch(request.FILES["file"], request.user)
        except ValueError as exc:
            messages.error(request, f"Could not read that file. {exc}")
            return redirect("crm:import")
        return redirect("crm:import_map", pk=batch.pk)
    return render(
        request,
        "adminpanel/crm/import_upload.html",
        {"crm_nav": "import", "batches": ImportBatch.objects.all()[:15]},
    )


@staff_only
@require_http_methods(["GET", "POST"])
def import_map(request, pk):
    batch = get_object_or_404(ImportBatch, pk=pk)
    if request.method == "POST":
        mapping = {}
        for field, _label in SYSTEM_FIELDS:
            raw = request.POST.get(f"map_{field}", "")
            if raw.isdigit():
                mapping[field] = int(raw)
        batch.mapping = mapping
        try:
            _headers, body = read_tabular(batch.upload.path)
        except Exception as exc:
            messages.error(request, str(exc))
            return redirect("crm:import_map", pk=batch.pk)
        batch.preview = preview_rows(body, mapping)
        batch.total_rows = len(batch.preview)
        batch.status = ImportBatch.Status.MAPPED
        batch.save(update_fields=["mapping", "preview", "total_rows", "status"])
        return redirect("crm:import_preview", pk=batch.pk)
    mapping = {key: str(value) for key, value in (batch.mapping or {}).items()}
    mapped_fields = [(field, label, mapping.get(field, "")) for field, label in SYSTEM_FIELDS]
    return render(
        request,
        "adminpanel/crm/import_map.html",
        {
            "crm_nav": "import",
            "batch": batch,
            "mapped_fields": mapped_fields,
            "columns": list(enumerate(batch.headers or [])),
        },
    )


@staff_only
@require_http_methods(["GET", "POST"])
def import_preview(request, pk):
    batch = get_object_or_404(ImportBatch, pk=pk)
    preview = list(batch.preview or [])
    for item in preview:
        data = item.get("data") or {}
        item["phone"] = data.get("mobile") or data.get("whatsapp") or ""
    if request.method == "POST":
        for item in preview:
            row = item["row"]
            chosen = request.POST.get(f"action_{row}") or item.get("action")
            item["action"] = chosen
        stats = commit_preview(preview, actor=request.user)
        batch.preview = preview
        batch.status = ImportBatch.Status.DONE
        batch.imported_count = stats["imported"]
        batch.duplicate_count = stats["duplicates"]
        batch.invalid_count = stats["invalid"]
        batch.updated_count = stats["updated"]
        batch.total_rows = stats["total"]
        batch.error_csv = stats["error_csv"]
        batch.save()
        messages.success(
            request,
            f"Imported {stats['imported']}, updated {stats['updated']}, "
            f"duplicates skipped {stats['duplicates']}, invalid {stats['invalid']}.",
        )
        return redirect("crm:import_result", pk=batch.pk)
    counts = {"new": 0, "duplicate": 0, "invalid": 0}
    for item in preview:
        counts[item["status"]] = counts.get(item["status"], 0) + 1
    return render(
        request,
        "adminpanel/crm/import_preview.html",
        {"crm_nav": "import", "batch": batch, "preview": preview[:400], "counts": counts},
    )


@staff_only
def import_result(request, pk):
    batch = get_object_or_404(ImportBatch, pk=pk)
    return render(request, "adminpanel/crm/import_result.html", {"crm_nav": "import", "batch": batch})


@staff_only
def import_errors(request, pk):
    batch = get_object_or_404(ImportBatch, pk=pk)
    response = HttpResponse(batch.error_csv or "row,status,reason\n", content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="import_errors_{batch.pk}.csv"'
    return response
