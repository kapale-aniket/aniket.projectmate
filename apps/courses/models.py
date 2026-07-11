"""Paid course models — payment integration future-ready."""
from django.conf import settings
from django.db import models
from django.urls import reverse
from apps.core.basemodels import BaseModel
from apps.core.models import CourseCategory


class PaidCourse(BaseModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        ARCHIVED = "archived", "Archived"

    TECHNOLOGY_CHOICES = [
        ("python", "Python"),
        ("django", "Django"),
        ("sql", "SQL"),
        ("java", "Java"),
        ("c", "C"),
        ("cpp", "C++"),
        ("html", "HTML"),
        ("css", "CSS"),
        ("javascript", "JavaScript"),
        ("other", "Other"),
    ]

    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    technology = models.CharField(max_length=30, choices=TECHNOLOGY_CHOICES)
    category = models.ForeignKey(
        CourseCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name="paid_courses"
    )
    short_description = models.CharField(max_length=300)
    description = models.TextField()
    curriculum = models.TextField(help_text="Markdown or plain text curriculum")
    features = models.TextField(blank=True, help_text="One feature per line")
    benefits = models.TextField(blank=True, help_text="One benefit per line")
    prerequisites = models.TextField(blank=True)
    faqs = models.TextField(blank=True, help_text="Q: ... / A: ... pairs, one per line or blank-line separated")
    price = models.DecimalField(max_digits=10, decimal_places=2)
    discount_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    duration_weeks = models.PositiveIntegerField(default=4)
    duration_hours = models.PositiveIntegerField(default=20)
    image = models.ImageField(upload_to="courses/", blank=True, null=True)
    instructor_name = models.CharField(max_length=120, default="Aniket")
    max_students = models.PositiveIntegerField(default=50)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PUBLISHED)
    is_featured = models.BooleanField(default=False)
    start_date = models.DateField(null=True, blank=True)
    # Payment future-ready
    payment_provider = models.CharField(max_length=50, blank=True, default="razorpay")
    payment_product_id = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ["technology", "title"]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("courses:detail", kwargs={"slug": self.slug})

    @property
    def effective_price(self):
        return self.discount_price if self.discount_price is not None else self.price

    def feature_list(self):
        return [f.strip() for f in self.features.splitlines() if f.strip()]

    def benefit_list(self):
        return [b.strip() for b in self.benefits.splitlines() if b.strip()]


class CourseEnrollment(BaseModel):
    class Status(models.TextChoices):
        INTERESTED = "interested", "Interested"
        PENDING_PAYMENT = "pending_payment", "Pending Payment"
        PAID = "paid", "Paid"
        ACTIVE = "active", "Active"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="enrollments"
    )
    course = models.ForeignKey(PaidCourse, on_delete=models.CASCADE, related_name="enrollments")
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.INTERESTED)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    payment_reference = models.CharField(max_length=120, blank=True)
    payment_meta = models.JSONField(default=dict, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = ("student", "course")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.student.email} → {self.course.title}"


class CourseMaterial(BaseModel):
    class MaterialType(models.TextChoices):
        PDF = "pdf", "PDF"
        WORD = "word", "Word Document"
        ASSIGNMENT = "assignment", "Assignment"
        OTHER = "other", "Other"

    course = models.ForeignKey(
        PaidCourse, on_delete=models.CASCADE, related_name="materials", null=True, blank=True
    )
    free_class = models.ForeignKey(
        "classes.FreeClass",
        on_delete=models.CASCADE,
        related_name="materials",
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=200)
    material_type = models.CharField(
        max_length=20, choices=MaterialType.choices, default=MaterialType.PDF
    )
    file = models.FileField(upload_to="materials/")
    description = models.TextField(blank=True)
    is_public = models.BooleanField(
        default=False, help_text="If false, only enrolled/registered students can access"
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="uploaded_materials",
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title
