"""One contact, many enquiries, full history."""

from django.conf import settings
from django.db import models
from django.utils import timezone


class Tag(models.Model):
    name = models.CharField(max_length=80, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Contact(models.Model):
    class Type(models.TextChoices):
        STUDENT = "student", "Student"
        MEDIATOR = "mediator", "Mediator"
        REFERRAL = "referral_partner", "Referral partner"
        COLLEGE = "college", "College contact"
        CLIENT = "client", "Client"
        TRAINER = "trainer", "Trainer"
        TESTER = "tester", "Tester"
        OTHER = "other", "Other"

    contact_type = models.CharField(max_length=32, choices=Type.choices, default=Type.STUDENT)
    name = models.CharField(max_length=160)
    mobile = models.CharField(max_length=32, blank=True)
    mobile_key = models.CharField(max_length=20, blank=True, db_index=True)
    whatsapp = models.CharField(max_length=32, blank=True)
    email = models.EmailField(blank=True)
    currently_studying = models.BooleanField(null=True, blank=True)
    year_of_study = models.CharField(max_length=80, blank=True)
    college = models.CharField(max_length=255, blank=True)
    follows_instagram = models.BooleanField(null=True, blank=True)
    instagram_reply = models.CharField(
        max_length=16,
        blank=True,
        default="",
        help_text="yes = already follows, will = will follow now",
    )
    branch = models.CharField(max_length=80, blank=True)
    location = models.CharField(max_length=120, blank=True)
    source = models.CharField(max_length=80, blank=True)
    notes = models.TextField(blank=True)
    star_count = models.PositiveIntegerField(default=0)
    tags = models.ManyToManyField(Tag, blank=True, related_name="contacts")
    referred_by = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="referrals"
    )
    last_interaction = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="crm_contacts"
    )

    class Meta:
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["mobile_key"],
                condition=~models.Q(mobile_key=""),
                name="crm_unique_mobile_key",
            )
        ]

    def __str__(self):
        return self.name

    @property
    def star_icons(self):
        return range(self.star_count or 0)

    @property
    def mobile_display(self):
        raw = (self.mobile or self.whatsapp or "").strip()
        if raw.endswith(".0"):
            raw = raw[:-2]
        return raw

    def touch(self, when=None):
        self.last_interaction = when or timezone.now()
        self.save(update_fields=["last_interaction", "updated_at"])


class TimelineEvent(models.Model):
    contact = models.ForeignKey(Contact, on_delete=models.CASCADE, related_name="timeline")
    kind = models.CharField(max_length=40)
    title = models.CharField(max_length=200)
    detail = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class Enquiry(models.Model):
    class Business(models.TextChoices):
        PROJECT = "project", "Project"
        CLASSES = "classes", "Online classes"
        TESTING = "testing", "Project testing"

    class Source(models.TextChoices):
        INSTAGRAM = "instagram", "Instagram"
        WHATSAPP = "whatsapp", "WhatsApp"
        REFERRAL = "referral", "Referral"
        MEDIATOR = "mediator", "Mediator"
        DIRECT = "direct", "Direct"
        LINKEDIN = "linkedin", "LinkedIn"
        COLLEGE = "college", "College"
        WEBSITE = "website", "Website"
        STUDENT = "existing_student", "Existing student"

    class Status(models.TextChoices):
        NEW = "new", "New"
        CONTACTED = "contacted", "Contacted"
        INTERESTED = "interested", "Interested"
        REQUIREMENT = "requirement_collected", "Requirement collected"
        PRICE = "price_shared", "Price shared"
        FOLLOW_UP = "follow_up", "Follow-up"
        CONFIRMED = "confirmed", "Confirmed"
        IN_PROGRESS = "in_progress", "In progress"
        COMPLETED = "completed", "Completed"
        LOST = "lost", "Lost"
        NOT_INTERESTED = "not_interested", "Not interested"

    contact = models.ForeignKey(Contact, on_delete=models.CASCADE, related_name="enquiries")
    business = models.CharField(max_length=20, choices=Business.choices, default=Business.PROJECT)
    source = models.CharField(max_length=32, choices=Source.choices, default=Source.WHATSAPP)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.NEW)
    title = models.CharField(max_length=200)
    technology = models.CharField(max_length=160, blank=True)
    requirements = models.TextField(blank=True)
    price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    deadline = models.DateField(null=True, blank=True)
    github_url = models.URLField(blank=True)
    delivery_notes = models.TextField(blank=True)
    testing_status = models.CharField(max_length=80, blank=True)
    course_name = models.CharField(max_length=160, blank=True)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="crm_enquiries"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "enquiries"

    def __str__(self):
        return self.title


class FollowUp(models.Model):
    class Channel(models.TextChoices):
        WHATSAPP = "whatsapp", "WhatsApp"
        CALL = "call", "Call"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        DONE = "done", "Done"
        SKIPPED = "skipped", "Skipped"

    contact = models.ForeignKey(Contact, on_delete=models.CASCADE, related_name="followups")
    enquiry = models.ForeignKey(Enquiry, null=True, blank=True, on_delete=models.SET_NULL, related_name="followups")
    channel = models.CharField(max_length=20, choices=Channel.choices, default=Channel.WHATSAPP)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    notes = models.TextField(blank=True)
    followed_at = models.DateTimeField(null=True, blank=True)
    next_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["next_date", "-created_at"]


class WhatsAppTemplate(models.Model):
    name = models.CharField(max_length=120)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Payment(models.Model):
    class Kind(models.TextChoices):
        PROJECT = "project", "Project payment"
        CLASS = "class", "Class fee"
        TESTING = "testing", "Testing payment"
        COMMISSION = "commission", "Mediator commission"

    contact = models.ForeignKey(Contact, on_delete=models.CASCADE, related_name="payments")
    enquiry = models.ForeignKey(Enquiry, null=True, blank=True, on_delete=models.SET_NULL, related_name="payments")
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.PROJECT)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    advance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    received = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    method = models.CharField(max_length=40, blank=True)
    paid_on = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def pending(self):
        return self.total_amount - self.received


class Document(models.Model):
    contact = models.ForeignKey(Contact, on_delete=models.CASCADE, related_name="documents")
    enquiry = models.ForeignKey(Enquiry, null=True, blank=True, on_delete=models.SET_NULL, related_name="documents")
    title = models.CharField(max_length=200)
    kind = models.CharField(max_length=80, blank=True)
    link = models.URLField(blank=True)
    file = models.FileField(upload_to="crm/documents/", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class TestItem(models.Model):
    class Severity(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        RETEST = "retest", "Retesting"
        CLOSED = "closed", "Closed"

    enquiry = models.ForeignKey(Enquiry, on_delete=models.CASCADE, related_name="tests")
    title = models.CharField(max_length=200)
    severity = models.CharField(max_length=20, choices=Severity.choices, default=Severity.MEDIUM)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class ImportBatch(models.Model):
    class Status(models.TextChoices):
        UPLOADED = "uploaded", "Uploaded"
        MAPPED = "mapped", "Mapped"
        DONE = "done", "Done"

    original_name = models.CharField(max_length=255)
    upload = models.FileField(upload_to="crm/imports/")
    headers = models.JSONField(default=list)
    mapping = models.JSONField(default=dict)
    preview = models.JSONField(default=list)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.UPLOADED)
    total_rows = models.PositiveIntegerField(default=0)
    imported_count = models.PositiveIntegerField(default=0)
    duplicate_count = models.PositiveIntegerField(default=0)
    invalid_count = models.PositiveIntegerField(default=0)
    updated_count = models.PositiveIntegerField(default=0)
    error_csv = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
