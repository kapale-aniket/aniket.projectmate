"""Seed rich demo data for Aniket.ProjectMate testing."""
from datetime import timedelta, time, datetime
from decimal import Decimal
import random

from django.core.management.base import BaseCommand
from django.db.models.signals import post_save
from django.utils import timezone
from django.utils.text import slugify


FIRST_NAMES = [
    "Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Sai", "Reyansh", "Ayaan",
    "Krishna", "Ishaan", "Ananya", "Aadhya", "Diya", "Myra", "Anika", "Sara",
    "Ira", "Pari", "Riya", "Kiara", "Rohan", "Kabir", "Dev", "Neha", "Priya",
    "Sneha", "Amit", "Pooja", "Rahul", "Meera",
]
LAST_NAMES = [
    "Sharma", "Patel", "Singh", "Kumar", "Gupta", "Reddy", "Nair", "Iyer",
    "Joshi", "Mehta", "Shah", "Verma", "Rao", "Das", "Chopra",
]
COLLEGES = [
    "COEP Pune", "VIT Pune", "PICT Pune", "MIT WPU", "Sinhgad College",
    "DY Patil", "PCCOE", "JSPM", "BVCOE", "IIT Bombay",
]
BRANCHES = ["CSE", "IT", "ENTC", "AIDS", "Mechanical", "Civil"]
CITIES = ["Pune", "Mumbai", "Nagpur", "Nashik", "Aurangabad", "Kolhapur"]
SKILLS = ["Python", "Django", "SQL", "JavaScript", "React", "Java", "HTML", "CSS", "Git"]

COURSE_DEFS = [
    ("Python Mastery", "python", 2999),
    ("Django Full Stack", "django", 4999),
    ("SQL for Interviews", "sql", 1999),
    ("JavaScript Essentials", "javascript", 3999),
    ("Java Foundations", "java", 3499),
    ("C Programming Lab", "c", 1499),
    ("C++ OOP Bootcamp", "cpp", 2499),
    ("HTML & CSS Pro", "html", 999),
    ("Modern CSS Layouts", "css", 1299),
    ("JavaScript Deep Dive", "javascript", 2799),
    ("Python for Data", "python", 3599),
    ("Django REST APIs", "django", 4499),
    ("Advanced SQL", "sql", 2299),
    ("DOM & Events Project", "javascript", 3799),
    ("Java Spring Intro", "java", 4299),
    ("Full Stack Starter", "javascript", 5499),
    ("Web Design Basics", "html", 1199),
    ("Backend with Django", "django", 3999),
    ("Interview Prep Pack", "python", 2599),
    ("Frontend Accelerator", "javascript", 4199),
]

CLASS_DEFS = [
    ("Intro to Python for Beginners", "Python"),
    ("Django Crash Course", "Django"),
    ("SQL Essentials", "SQL"),
    ("JavaScript Fundamentals", "JavaScript"),
    ("Git & GitHub Workshop", "Git"),
    ("HTML5 Quickstart", "HTML"),
    ("CSS Flexbox Live", "CSS"),
    ("React Components 101", "React"),
    ("Java Basics Live", "Java"),
    ("REST API Concepts", "Django"),
    ("Database Design Night", "SQL"),
    ("Python OOP Session", "Python"),
]


class Command(BaseCommand):
    help = "Seed 30 students, 20 courses, free classes, enrollments, attendance, feedback, and more"

    def add_arguments(self, parser):
        parser.add_argument(
            "--fresh-demo",
            action="store_true",
            help="Remove previously seeded demo students/courses/classes before recreating",
        )

    def handle(self, *args, **options):
        from django.contrib.sites.models import Site
        from apps.core.models import SiteSettings, FAQ, CourseCategory
        from apps.accounts.models import User, StudentProfile, ActivityLog
        from apps.accounts.signals import create_student_profile
        from apps.classes.models import FreeClass, Registration
        from apps.courses.models import PaidCourse, CourseEnrollment
        from apps.announcements.models import Announcement
        from apps.rewards.models import Achievement, RewardRule, Reward
        from apps.notifications.models import EmailTemplate, EmailLog, Notification
        from apps.feedback.models import Feedback
        from apps.attendance.models import Attendance
        from apps.referrals.models import Referral

        random.seed(42)
        today = timezone.localdate()
        now = timezone.now()

        site = Site.objects.get_or_create(pk=1)[0]
        site.domain = "127.0.0.1:8000"
        site.name = "Aniket.ProjectMate"
        site.save()

        # ---- Email templates ----
        templates = [
            ("registration_confirm", "You're registered for {{ class_title }}!",
             "<h2>Thank you, {{ student_name }}!</h2><p>You're confirmed for <strong>{{ class_title }}</strong>.</p>"
             "<p>Date: {{ class_date }} · Time: {{ class_time }} · Duration: {{ duration }} min</p>"
             "<p><a href='{{ meet_link }}'>Join Google Meet</a></p>"),
            ("class_reminder", "Reminder: {{ class_title }} starts soon",
             "<p>Hi {{ student_name }}, reminder for <strong>{{ class_title }}</strong>.</p>"),
            ("session_live", "🔴 LIVE now: {{ class_title }} — join the session!",
             "Hi {{ student_name }},\n\n"
             "{{ class_title }} is live right now.\n\n"
             "Join the session: {{ meet_link }}\n\n"
             "Date: {{ class_date }} · Time: {{ class_time }}\n\n"
             "See you in class!\n— {{ site_name }}"),
            ("feedback_reminder", "Share feedback for {{ class_title }}",
             "Hi {{ student_name }},\n\n"
             "Thanks for attending {{ class_title }}.\n\n"
             "Please share your feedback — it helps us improve.\n\n"
             "Submit feedback: {{ feedback_url }}\n\n"
             "— {{ site_name }}"),
            ("joining_instructions", "Joining instructions — {{ class_title }}",
             "<p>Hi {{ student_name }}, joining instructions for {{ class_title }}.</p>"),
            ("consistency_reward", "Consistency reward unlocked!",
             "<p>Congrats {{ student_name }}! Consistency reward unlocked.</p>"),
            ("welcome", "Welcome to {{ site_name }}!",
             "<p>Hi {{ student_name }}, welcome to Aniket.ProjectMate.</p>"),
            ("referral_approved", "Referral approved — +{{ points }} points!",
             "<p>Hi {{ student_name }}, referral approved. +{{ points }} points!</p>"),
            ("resume_feedback", "Your resume feedback is ready",
             "<p>Hi {{ student_name }}, your resume review is ready.</p>"),
            ("password_changed", "Your ProjectMate password was changed",
             "<p>Hi {{ student_name }}, password changed on {{ changed_at }}.</p>"),
        ]
        for code, subject, body in templates:
            defaults = {"subject": subject, "is_active": True}
            if body.lstrip().startswith("<"):
                defaults["body_html"] = body
                defaults["body_text"] = ""
            else:
                from apps.notifications.services import EmailHtmlBuilder

                defaults["body_text"] = body
                defaults["body_html"] = EmailHtmlBuilder.wrap(subject, body)
            EmailTemplate.objects.update_or_create(code=code, defaults=defaults)
        self.stdout.write("OK Email templates")

        settings_obj, _ = SiteSettings.objects.get_or_create(pk=1)
        settings_obj.site_name = "Aniket.ProjectMate"
        settings_obj.tagline = "Learn. Build. Grow. - Practical classes for ambitious students."
        settings_obj.instagram_url = "https://instagram.com/"
        settings_obj.whatsapp_url = "https://chat.whatsapp.com/"
        settings_obj.youtube_url = "https://youtube.com/"
        settings_obj.linkedin_url = "https://linkedin.com/"
        settings_obj.show_whatsapp_icon = True
        settings_obj.show_instagram_icon = True
        settings_obj.show_linkedin_icon = True
        settings_obj.show_youtube_icon = True
        settings_obj.contact_email = "aniketkapale02@gmail.com"
        settings_obj.students_count = 500
        settings_obj.workshops_count = 48
        settings_obj.mentor_name = "Aniket"
        settings_obj.mentor_title = "Founder & Mentor - Aniket.ProjectMate"
        settings_obj.about_mentor = (
            "Aniket helps students learn by building real projects and growing with community."
        )
        settings_obj.why_learn_with_us = (
            "Live free classes, structured paid paths, attendance tracking, and rewards."
        )
        settings_obj.save()
        self.stdout.write("OK Site settings")

        faqs = [
            ("Are free classes really free?", "Yes. Register, get a Meet link by email, and join."),
            ("Do I need an account?", "Browsing is open. Sign in to register or open your dashboard."),
            ("How do rewards work?", "Attend classes, complete profile, submit feedback, refer friends."),
            ("What is the consistency reward?", "Attend six consecutive sessions to unlock resume review."),
            ("How do paid courses work?", "Browse courses and express interest. Payment coming soon."),
            ("Can I change my password?", "Yes — Dashboard → Password. You stay logged in after changing."),
        ]
        for i, (q, a) in enumerate(faqs):
            FAQ.objects.update_or_create(question=q, defaults={"answer": a, "order": i, "is_published": True})
        self.stdout.write("OK FAQs")

        cats = [
            ("Python", "fa-python", "#3776ab"),
            ("Web Development", "fa-globe", "#1a365d"),
            ("Databases", "fa-database", "#f59e0b"),
            ("Java", "fa-coffee", "#ea580c"),
            ("Frontend", "fa-paint-brush", "#8b5cf6"),
        ]
        cat_map = {}
        for i, (name, icon, color) in enumerate(cats):
            obj, _ = CourseCategory.objects.update_or_create(
                slug=slugify(name),
                defaults={"name": name, "icon": icon, "color": color, "order": i, "is_active": True},
            )
            cat_map[name.lower()] = obj
        self.stdout.write("OK Categories")

        # ---- Admin ----
        admin_email = "aniketkapale02@gmail.com"
        # Prefer existing seeded admin (old local email) so re-seed updates in place
        admin_user = (
            User.objects.filter(email__iexact=admin_email).first()
            or User.objects.filter(email__iexact="admin@projectmate.local").first()
        )
        if admin_user is None:
            admin_user = User(
                email=admin_email,
                username=admin_email,
                first_name="Aniket",
                is_staff=True,
                is_superuser=True,
                role="admin",
            )
        admin_user.email = admin_email
        admin_user.username = admin_email
        admin_user.first_name = admin_user.first_name or "Aniket"
        admin_user.is_staff = True
        admin_user.is_superuser = True
        admin_user.role = "admin"
        admin_user.set_password("Aniket@9096")
        admin_user.save()
        self.stdout.write(f"OK Admin  {admin_email} / Aniket@9096")

        # ---- Reward rules & achievements ----
        for code, label, pts in [
            ("attend_class", "Attend class (Present)", 10),
            ("attend_class_active", "Active in session", 15),
            ("feedback_submitted", "Submit feedback", 5),
            ("referral_approved", "Referral approved", 20),
            ("profile_completed", "Profile completed", 100),
            ("daily_login", "Daily login", 2),
            ("resume_uploaded", "Resume uploaded", 15),
        ]:
            RewardRule.objects.update_or_create(
                code=code,
                defaults={"label": label, "points": pts, "is_active": True},
            )
        for code, title, pts, icon in [
            ("first_steps", "First Steps", 0, "fa-shoe-prints"),
            ("consistent_learner", "Consistent Learner", 300, "fa-fire"),
            ("profile_pro", "Profile Pro", 100, "fa-id-card"),
            ("community_champion", "Community Champion", 500, "fa-users"),
            ("point_collector", "Point Collector", 1000, "fa-medal"),
        ]:
            Achievement.objects.update_or_create(
                code=code,
                defaults={
                    "title": title,
                    "points_required": pts,
                    "icon": icon,
                    "is_active": True,
                    "description": f"Unlock at {pts} points" if pts else "Welcome badge",
                },
            )
        self.stdout.write("OK Rewards & achievements")

        if options.get("fresh_demo"):
            demo_emails = [f"student{i:02d}@projectmate.local" for i in range(1, 31)]
            demo_emails.append("student@projectmate.local")
            User.objects.filter(email__in=demo_emails, role="student").delete()
            PaidCourse.objects.filter(slug__startswith="demo-").delete()
            FreeClass.objects.filter(slug__startswith="demo-").delete()
            self.stdout.write("OK Cleared previous demo students/courses/classes")

        # ---- 30 students (no welcome emails during bulk create) ----
        post_save.disconnect(create_student_profile, sender=User)
        students = []
        try:
            for i in range(1, 31):
                email = f"student{i:02d}@projectmate.local"
                first = FIRST_NAMES[(i - 1) % len(FIRST_NAMES)]
                last = LAST_NAMES[(i - 1) % len(LAST_NAMES)]
                user, created = User.objects.get_or_create(
                    email=email,
                    defaults={
                        "username": email,
                        "first_name": first,
                        "last_name": last,
                        "role": "student",
                        "is_active": i % 10 != 0,  # a few inactive
                    },
                )
                if created or options.get("fresh_demo"):
                    user.set_password("student12345")
                    user.first_name = first
                    user.last_name = last
                    user.role = "student"
                    user.is_active = i % 10 != 0
                    user.save()
                profile, _ = StudentProfile.objects.get_or_create(user=user)
                profile.phone = f"98{10000000 + i:08d}"[:10]
                profile.college = COLLEGES[(i - 1) % len(COLLEGES)]
                profile.college_location = CITIES[(i - 1) % len(CITIES)]
                profile.branch = BRANCHES[(i - 1) % len(BRANCHES)]
                profile.year = ["1", "2", "3", "4", "pg"][(i - 1) % 5]
                profile.city = CITIES[(i - 1) % len(CITIES)]
                profile.bio = f"Aspiring developer from {profile.city}."
                profile.skills = ", ".join(random.sample(SKILLS, k=4))
                profile.reward_points = random.randint(20, 850)
                profile.attendance_percentage = Decimal(str(round(random.uniform(55, 98), 2)))
                profile.consecutive_attendance = random.randint(0, 8)
                profile.linkedin_url = f"https://linkedin.com/in/{slugify(first)}-{i}"
                profile.github_url = f"https://github.com/{slugify(first)}{i}"
                profile.save()
                students.append(user)
        finally:
            post_save.connect(create_student_profile, sender=User)

        # Keep classic demo student alias
        demo, _ = User.objects.get_or_create(
            email="student@projectmate.local",
            defaults={
                "username": "student@projectmate.local",
                "first_name": "Demo",
                "last_name": "Student",
                "role": "student",
            },
        )
        demo.set_password("student12345")
        demo.first_name = "Demo"
        demo.last_name = "Student"
        demo.role = "student"
        demo.is_active = True
        demo.save()
        demo_profile, _ = StudentProfile.objects.get_or_create(user=demo)
        demo_profile.phone = "9876543210"
        demo_profile.college = "COEP Pune"
        demo_profile.college_location = "Pune"
        demo_profile.branch = "CSE"
        demo_profile.year = "3"
        demo_profile.city = "Pune"
        demo_profile.skills = "Python, Django, SQL"
        demo_profile.reward_points = 220
        demo_profile.attendance_percentage = Decimal("88.50")
        demo_profile.consecutive_attendance = 3
        demo_profile.save()
        if demo not in students:
            students.insert(0, demo)

        self.stdout.write("OK 30 students  (password for all: student12345)")
        self.stdout.write("   student01@projectmate.local … student30@projectmate.local")
        self.stdout.write("   + student@projectmate.local / student12345")

        # ---- 20 paid courses ----
        courses = []
        tech_cat = {
            "python": "python",
            "django": "web development",
            "sql": "databases",
            "java": "java",
            "javascript": "frontend",
            "html": "frontend",
            "css": "frontend",
            "c": "python",
            "cpp": "java",
        }
        for idx, (title, tech, price) in enumerate(COURSE_DEFS, start=1):
            slug = f"demo-{slugify(title)}"
            cat_key = tech_cat.get(tech, "web development")
            course, _ = PaidCourse.objects.update_or_create(
                slug=slug,
                defaults={
                    "title": title,
                    "technology": tech,
                    "category": cat_map.get(cat_key),
                    "short_description": f"Hands-on {title} with projects and mentor support.",
                    "description": (
                        f"A structured path to master {title}. Weekly live sessions, "
                        f"assignments, and portfolio-ready projects."
                    ),
                    "curriculum": (
                        "Week 1: Foundations\nWeek 2: Core concepts\n"
                        "Week 3: Projects\nWeek 4: Capstone & review"
                    ),
                    "features": "Live sessions\nRecordings\nDoubt support\nCertificate",
                    "benefits": "Interview ready\nPortfolio projects\nCommunity access",
                    "prerequisites": "Basic computer literacy",
                    "faqs": "Q: Are recordings included?\nA: Yes, for enrolled students.\n\nQ: Certificate?\nA: Yes on completion.",
                    "price": price,
                    "discount_price": price - 500 if price > 1500 else None,
                    "duration_weeks": 4 + (idx % 3),
                    "duration_hours": 16 + idx,
                    "status": "published" if idx % 7 else "draft",
                    "is_featured": idx <= 8,
                    "start_date": today + timedelta(days=7 + idx),
                    "instructor_name": "Aniket",
                    "max_students": 40 + idx,
                },
            )
            courses.append(course)
        self.stdout.write(f"OK {len(courses)} paid courses")

        # ---- Free classes ----
        free_classes = []
        for i, (title, tech) in enumerate(CLASS_DEFS):
            slug = f"demo-{slugify(title)}"
            status = "upcoming"
            class_date = today + timedelta(days=2 + i)
            if i < 3:
                status = "completed"
                class_date = today - timedelta(days=10 - i)
            elif i == 3:
                status = "live"
                class_date = today
            fc, _ = FreeClass.objects.update_or_create(
                slug=slug,
                defaults={
                    "title": title,
                    "technology": tech,
                    "description": f"Join this free live session on {tech}. Bring curiosity!",
                    "preparation_guide": "Install VS Code. Join 5 minutes early.",
                    "date": class_date,
                    "start_time": time(18, 0) if i % 2 == 0 else time(19, 30),
                    "duration_minutes": 90,
                    "google_meet_link": "https://meet.google.com/lookup/projectmate",
                    "zoom_link": "https://zoom.us/j/1234567890",
                    "meeting_password": "learn123",
                    "instructor_name": "Aniket",
                    "max_seats": 80 + i,
                    "status": status,
                    "is_featured": i < 4,
                    "tags": tech,
                    "registration_enabled": status in ("upcoming", "live"),
                    "important_instructions": "Be respectful. Questions welcome in chat.",
                },
            )
            free_classes.append(fc)
        self.stdout.write(f"OK {len(free_classes)} free classes")

        # ---- Registrations + attendance ----
        reg_count = 0
        att_count = 0
        for fc in free_classes:
            sample = random.sample(students, k=min(12, len(students)))
            for user in sample:
                reg, created = Registration.objects.get_or_create(
                    student=user,
                    free_class=fc,
                    defaults={"status": "confirmed", "confirmation_sent": True},
                )
                if created:
                    reg_count += 1
                    # Spread created_at for reports charts
                    Registration.objects.filter(pk=reg.pk).update(
                        created_at=now - timedelta(days=random.randint(0, 20), hours=random.randint(0, 20))
                    )
                if fc.status == "completed":
                    status = random.choice(["present", "present", "present", "late", "absent"])
                    att, created = Attendance.objects.get_or_create(
                        student=user,
                        free_class=fc,
                        defaults={
                            "status": status,
                            "marked_by": admin_user,
                            "points_awarded": status in ("present", "late"),
                        },
                    )
                    if created:
                        att_count += 1
        self.stdout.write(f"OK Registrations ~{reg_count}, attendance ~{att_count}")

        # ---- Course enrollments ----
        enroll_count = 0
        for course in courses:
            if course.status != "published":
                continue
            sample = random.sample(students, k=min(8, len(students)))
            for user in sample:
                st = random.choice(["interested", "paid", "active", "completed", "pending_payment"])
                amount = course.effective_price if st in ("paid", "active", "completed") else 0
                obj, created = CourseEnrollment.objects.get_or_create(
                    student=user,
                    course=course,
                    defaults={
                        "status": st,
                        "amount_paid": amount,
                        "payment_reference": f"PAY{random.randint(10000, 99999)}" if amount else "",
                    },
                )
                if created:
                    enroll_count += 1
        self.stdout.write(f"OK Enrollments ~{enroll_count}")

        # ---- Feedback ----
        reviews = [
            "Clear teaching and practical examples.",
            "Loved the live sessions and community vibe.",
            "Helped me prepare for interviews.",
            "Great mentor support and notes.",
            "Would recommend to every engineering student.",
        ]
        fb_count = 0
        for i, user in enumerate(students[:18]):
            if Feedback.objects.filter(student=user).exists():
                continue
            Feedback.objects.create(
                student=user,
                rating=random.randint(3, 5),
                review=reviews[i % len(reviews)],
                suggestions="More weekend batches please." if i % 3 == 0 else "",
                status="approved",
                show_on_landing=True,
                is_featured=i < 3,
                free_class=free_classes[i % len(free_classes)] if free_classes else None,
            )
            fb_count += 1
        self.stdout.write(f"OK Feedback {fb_count}")

        # ---- Referrals ----
        ref_count = 0
        for i in range(0, min(10, len(students) - 1)):
            referrer = students[i]
            referred = students[i + 1]
            code = referrer.profile.referral_code
            obj, created = Referral.objects.get_or_create(
                referrer=referrer,
                referred_user=referred,
                defaults={
                    "referral_code": code,
                    "status": random.choice(["pending", "approved", "rejected"]),
                },
            )
            if created:
                ref_count += 1
        self.stdout.write(f"OK Referrals {ref_count}")

        # ---- Announcements ----
        announcements = [
            ("welcome-to-projectmate", "Welcome to Aniket.ProjectMate!", "general", True),
            ("demo-python-week", "Python Week starts Monday", "workshop", False),
            ("demo-placement-drive", "Placement prep workshop announced", "placement", False),
            ("demo-holiday-notice", "Holiday notice — Independence Day", "holiday", False),
            ("demo-latest-update", "Dashboard password change is live", "update", False),
        ]
        for slug, title, category, pinned in announcements:
            Announcement.objects.update_or_create(
                slug=slug,
                defaults={
                    "title": title,
                    "category": category,
                    "content": f"{title}\n\nDetails and schedule will be shared on WhatsApp and email.",
                    "summary": title,
                    "is_pinned": pinned,
                    "is_published": True,
                    "published_at": now - timedelta(days=random.randint(0, 10)),
                    "author": admin_user,
                },
            )
        self.stdout.write("OK Announcements")

        # ---- Sample rewards / activity / notifications / email logs ----
        for user in students[:15]:
            Reward.objects.get_or_create(
                student=user,
                reason="attend_class",
                description="Seeded attendance points",
                defaults={"points": 10},
            )
            Notification.objects.get_or_create(
                user=user,
                title="Welcome to ProjectMate",
                defaults={
                    "message": "Explore free classes and start earning rewards.",
                    "level": "info",
                    "link": "/dashboard/",
                },
            )
            ActivityLog.objects.create(
                user=user,
                action="seed_login",
                description="Seeded activity for testing reports",
            )
            EmailLog.objects.create(
                recipient=user,
                to_email=user.email,
                subject="Welcome to Aniket.ProjectMate",
                body_html="<p>Welcome!</p>",
                status=random.choice(["sent", "sent", "queued", "failed"]),
            )
        self.stdout.write("OK Sample rewards, notifications, activity, email logs")

        settings_obj.students_count = User.objects.filter(role="student").count()
        settings_obj.workshops_count = FreeClass.objects.count()
        settings_obj.save(update_fields=["students_count", "workshops_count", "updated_at"])

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Seed complete — ready to test"))
        self.stdout.write("Admin:   aniketkapale02@gmail.com / Aniket@9096")
        self.stdout.write("Student: student01@projectmate.local / student12345  (… student30)")
        self.stdout.write("Alias:   student@projectmate.local / student12345")
