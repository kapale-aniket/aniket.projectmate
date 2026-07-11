from decimal import Decimal

from django.db import migrations, models


def seed_plans(apps, schema_editor):
    ProjectPlan = apps.get_model("core", "ProjectPlan")
    ProjectPlanPerk = apps.get_model("core", "ProjectPlanPerk")

    plans = [
        {
            "name": "College Level Project",
            "slug": "college-level",
            "tagline": "Solid for semester & viva",
            "description": "A clean, explainable project shaped for college submission and viva.",
            "price": Decimal("1999.00"),
            "badge": "Student favourite",
            "is_highlighted": False,
            "order": 1,
            "features": "Auth & roles\nPolished UI modules\nDeploy-ready setup\nDemo + viva walkthrough",
        },
        {
            "name": "Interview Winning Project",
            "slug": "interview-winning",
            "tagline": "Built to impress in interviews",
            "description": "Stronger architecture and polish so you can explain and demo with interview confidence.",
            "price": Decimal("2499.00"),
            "badge": "Popular",
            "is_highlighted": True,
            "order": 2,
            "features": "Industry-style architecture\nAdvanced modules\nMentor review sessions\nInterview Q&A prep",
        },
        {
            "name": "Premium Industry Level",
            "slug": "premium-industry",
            "tagline": "Industry-grade depth",
            "description": "Premium scope with stronger architecture, polish, and mentor-led refinement.",
            "price": Decimal("5999.00"),
            "badge": "Premium",
            "is_highlighted": False,
            "order": 3,
            "features": "Industry-style architecture\nAdvanced modules\nMentor review sessions\nPresentation coaching",
        },
    ]
    for row in plans:
        ProjectPlan.objects.update_or_create(slug=row["slug"], defaults=row)

    perks = [
        ("DML / ER diagrams", "fas fa-project-diagram", 1),
        ("Viva support", "fas fa-comments", 2),
        ("Guide notes", "fas fa-book-open", 3),
        ("Project flow explanation guide in your language", "fas fa-language", 4),
    ]
    for title, icon, order in perks:
        ProjectPlanPerk.objects.update_or_create(
            title=title,
            defaults={"icon": icon, "order": order, "is_active": True},
        )


def unseed_plans(apps, schema_editor):
    ProjectPlan = apps.get_model("core", "ProjectPlan")
    ProjectPlanPerk = apps.get_model("core", "ProjectPlanPerk")
    ProjectPlan.objects.filter(
        slug__in=["college-level", "production-ready", "interview-winning", "premium-industry"]
    ).delete()
    ProjectPlanPerk.objects.filter(
        title__in=[
            "DML / ER diagrams",
            "Viva support",
            "Guide notes",
            "Project flow explanation guide in your language",
        ]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0004_projectidea"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProjectPlan",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=120)),
                ("slug", models.SlugField(blank=True, max_length=140, unique=True)),
                ("tagline", models.CharField(blank=True, max_length=200)),
                ("description", models.TextField(blank=True)),
                ("price", models.DecimalField(decimal_places=2, max_digits=10)),
                (
                    "price_label",
                    models.CharField(
                        blank=True,
                        help_text="Optional display override, e.g. ₹4,999 or From ₹3k",
                        max_length=40,
                    ),
                ),
                ("currency_prefix", models.CharField(default="₹", max_length=8)),
                (
                    "features",
                    models.TextField(
                        blank=True,
                        help_text="One feature per line (shown as bullets on the plan card).",
                    ),
                ),
                (
                    "badge",
                    models.CharField(
                        blank=True,
                        help_text="Optional badge, e.g. Popular or Best for viva",
                        max_length=60,
                    ),
                ),
                ("is_highlighted", models.BooleanField(default=False, help_text="Emphasize this plan on the page")),
                ("is_active", models.BooleanField(default=True)),
                ("order", models.PositiveIntegerField(default=0)),
            ],
            options={
                "verbose_name": "Project plan",
                "verbose_name_plural": "Project plans",
                "ordering": ["order", "price", "name"],
            },
        ),
        migrations.CreateModel(
            name="ProjectPlanPerk",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("title", models.CharField(max_length=160)),
                (
                    "icon",
                    models.CharField(
                        blank=True,
                        default="fas fa-check",
                        help_text="Font Awesome class, e.g. fas fa-diagram-project",
                        max_length=60,
                    ),
                ),
                ("order", models.PositiveIntegerField(default=0)),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={
                "verbose_name": "Project plan perk",
                "verbose_name_plural": "Project plan perks",
                "ordering": ["order", "id"],
            },
        ),
        migrations.RunPython(seed_plans, unseed_plans),
    ]
