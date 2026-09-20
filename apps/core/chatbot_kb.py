"""ProjectMateBot knowledge base - all ProjectMate student features (no external AI).

CTA buttons in replies use: [[Click Label|/path/]]
The chat UI turns these into clickable buttons (not raw URLs).
"""
from __future__ import annotations

from typing import Any

KNOWLEDGE_BASE: list[dict[str, Any]] = [
    {
        "id": "greet",
        "title": "Greeting",
        "keys": [
            "hi", "hello", "hey", "hii", "helo", "namaste", "good morning",
            "good evening", "good afternoon", "yo", "hola",
        ],
        "body": (
            "Hi! I am **ProjectMateBot**, your ProjectMate helper.\n\n"
            "Ask me about accounts, free classes, paid courses, dashboard, rewards, "
            "referrals, attendance, resume, projects, feedback, announcements, or contact.\n\n"
            "If I do not understand, I will ask you to check spelling and stay on related topics."
        ),
    },
    {
        "id": "thanks",
        "title": "Thanks",
        "keys": ["thanks", "thank you", "thx", "ty", "thanku", "thankyou", "dhanyavad"],
        "body": (
            "You are welcome! Ask anytime about ProjectMate features.\n\n"
            "For human help, use Contact or the WhatsApp icon.\n\n"
            "[[Open Contact|/contact/]]"
        ),
    },
    {
        "id": "bye",
        "title": "Goodbye",
        "keys": ["bye", "goodbye", "see you", "cya", "later", "good night"],
        "body": "Bye! Open ProjectMateBot anytime from the chat button. Keep learning!",
    },
    {
        "id": "what_can_ask",
        "title": "What I can help with",
        "keys": [
            "what can you do", "how can you help", "what can i ask", "help me",
            "options", "menu", "topics", "features list", "how to use chatbot",
        ],
        "body": (
            "I answer **only ProjectMate-related** questions from our knowledge base:\n\n"
            "1. Register / login / password / Google login\n"
            "2. Free classes and Meet links (via email)\n"
            "3. Paid courses and enroll\n"
            "4. Student dashboard (classes, attendance, notifications)\n"
            "5. Rewards, points, achievements, leaderboard\n"
            "6. Referrals\n"
            "7. Resume review\n"
            "8. Projects and project requests\n"
            "9. Feedback and testimonials\n"
            "10. Announcements, search, dark mode, contact\n\n"
            "Ask one clear question, for example: How do I join a free class?"
        ),
    },
    {
        "id": "about_site",
        "title": "About ProjectMate",
        "keys": [
            "what is projectmate", "about projectmate", "what do you offer",
            "tell me about", "who are you", "what is projectmatebot", "about this website",
            "what is this site", "aniket projectmate",
        ],
        "body": (
            "**Aniket.ProjectMate** helps students learn, build projects, and grow.\n\n"
            "• Free live classes\n"
            "• Paid courses\n"
            "• Custom projects\n"
            "• Rewards, referrals, resume review, feedback\n"
            "• Student dashboard after login\n\n"
            "[[Browse Free Classes|/classes/]]\n"
            "[[Browse Courses|/courses/]]\n"
            "[[About Us|/about/]]\n"
            "[[Open Dashboard|/dashboard/]]"
        ),
    },
    {
        "id": "register",
        "title": "Create an account",
        "keys": [
            "register", "sign up", "signup", "create account", "registration",
            "new account", "make account", "how to register", "create an account",
            "join projectmate", "student signup",
        ],
        "body": (
            "Here is how to create your student account:\n\n"
            "1. Click **Register** below\n"
            "2. Enter your email, name, and password (confirm password)\n"
            "3. Optional: enter a referral code from a friend\n"
            "4. Submit - you are signed in as a student\n\n"
            "Already have an account? Click **Login** instead.\n\n"
            "[[Click Register|/accounts/register/]]\n"
            "[[Click Login|/accounts/login/]]"
        ),
    },
    {
        "id": "login",
        "title": "Log in",
        "keys": [
            "login", "log in", "sign in", "signin", "cannot login", "cant login",
            "unable to login", "how to login", "student login",
        ],
        "body": (
            "To sign in as a student:\n\n"
            "1. Click **Login** below\n"
            "2. Enter your registered email and password\n"
            "3. Optional: turn on **Remember me**\n\n"
            "After login you go to your Dashboard (or back to the page you came from).\n"
            "Staff/mentors use the Admin panel - students should not use that.\n\n"
            "[[Click Login|/accounts/login/]]\n"
            "[[Open Dashboard|/dashboard/]]"
        ),
    },
    {
        "id": "logout",
        "title": "Log out",
        "keys": ["logout", "log out", "sign out", "signout"],
        "body": (
            "To log out, open Dashboard and choose **Logout**, or click the button below.\n\n"
            "You will return to the home page.\n\n"
            "[[Click Logout|/accounts/logout/]]"
        ),
    },
    {
        "id": "password_forgot",
        "title": "Forgot / reset password",
        "keys": [
            "forgot password", "reset password", "password reset", "forgot my password",
            "recover password", "cant remember password", "lost password",
        ],
        "body": (
            "If you forgot your password:\n\n"
            "1. Click **Reset Password** below\n"
            "2. Enter your registered email\n"
            "3. Open the email we send (check spam)\n"
            "4. Set a new password on that page\n\n"
            "Already logged in? Change password from Dashboard -> Profile.\n\n"
            "[[Reset Password|/accounts/password-reset/]]\n"
            "[[Open Profile|/dashboard/profile/]]"
        ),
    },
    {
        "id": "password_change",
        "title": "Change password while logged in",
        "keys": [
            "change password", "update password", "new password", "password change",
        ],
        "body": (
            "While logged in:\n\n"
            "1. Open **Profile**\n"
            "2. Use **Change password**\n"
            "3. Enter current and new password\n\n"
            "You stay signed in after a successful change.\n\n"
            "[[Open Profile|/dashboard/profile/]]"
        ),
    },
    {
        "id": "google_login",
        "title": "Google login",
        "keys": [
            "google login", "continue with google", "sign in with google",
            "google signup", "oauth", "gmail login",
        ],
        "body": (
            "If **Continue with Google** is shown on Login/Register, you can sign in "
            "with your Google account.\n\n"
            "• You are created as a **student** automatically\n"
            "• The Google button appears only when the site owner enabled Google login\n\n"
            "If the button is missing, use email/password Register instead.\n\n"
            "[[Click Login|/accounts/login/]]\n"
            "[[Click Register|/accounts/register/]]"
        ),
    },
    {
        "id": "trust_gate",
        "title": "Why login is required",
        "keys": [
            "why login", "need to login", "trust page", "login required",
            "must login", "why register first",
        ],
        "body": (
            "Some actions need a student account so we can track classes, attendance, "
            "rewards, and emails:\n\n"
            "• Register for a free class\n"
            "• Enroll interest in a paid course\n"
            "• Submit public feedback\n\n"
            "You may see a short trust message first, then Login or Register.\n\n"
            "[[Click Login|/accounts/login/]]\n"
            "[[Click Register|/accounts/register/]]"
        ),
    },
    {
        "id": "roles_admin",
        "title": "Student vs admin login",
        "keys": [
            "admin login", "admin panel", "staff login", "mentor login",
            "difference admin student", "cannot access admin",
        ],
        "body": (
            "**Students** use Login and then Dashboard.\n\n"
            "**Mentors / staff** use the Admin panel.\n\n"
            "If you are a student and see permission denied on Admin, use student Login instead.\n\n"
            "[[Student Login|/accounts/login/]]\n"
            "[[Open Dashboard|/dashboard/]]"
        ),
    },
    {
        "id": "free_classes_browse",
        "title": "Browse free classes",
        "keys": [
            "free class", "free classes", "live class", "workshop", "workshops",
            "class list", "upcoming class", "browse classes",
        ],
        "body": (
            "Browse free live classes on the Classes page.\n\n"
            "You can filter by technology, status, or search.\n"
            "Open a class to see date, time, duration, seats, preparation guide, "
            "and instructor details.\n\n"
            "[[Browse Free Classes|/classes/]]"
        ),
    },
    {
        "id": "free_class_register",
        "title": "Register for a free class",
        "keys": [
            "join class", "register class", "register for class", "how to join class",
            "class registration", "book class", "seat", "register workshop",
        ],
        "body": (
            "To join a free class:\n\n"
            "1. Click **Browse Free Classes**\n"
            "2. Open the class you want\n"
            "3. Log in if asked\n"
            "4. Tick the community checkbox\n"
            "5. Click **Register** on that class page\n\n"
            "Registration is free and usually auto-confirmed if seats are open.\n"
            "See your registrations in Dashboard -> My Classes.\n\n"
            "[[Browse Free Classes|/classes/]]\n"
            "[[My Classes|/dashboard/classes/]]"
        ),
    },
    {
        "id": "meet_link",
        "title": "Google Meet / joining link",
        "keys": [
            "meet link", "google meet", "joining link", "zoom", "class link",
            "where is meet", "session link", "join link", "meeting link",
            "how to join live", "live link",
        ],
        "body": (
            "**Where is my Meet link?**\n\n"
            "After you register, the Meet / joining link is sent by **email** "
            "(confirmation, reminders, and session-live emails).\n\n"
            "• Check inbox and spam/junk\n"
            "• The link is not shown as a big button on My Classes\n"
            "• Still missing? Contact support with the class name and your email\n\n"
            "[[My Classes|/dashboard/classes/]]\n"
            "[[Contact Support|/contact/]]"
        ),
    },
    {
        "id": "class_full_closed",
        "title": "Class full or registration closed",
        "keys": [
            "class full", "no seats", "registration closed", "cannot register class",
            "registration disabled", "class ended", "missed class",
        ],
        "body": (
            "You cannot register when:\n\n"
            "• Seats are full\n"
            "• Registration is disabled or the deadline passed\n"
            "• Class status is completed / cancelled\n\n"
            "Watch Announcements and Free Classes for the next session.\n\n"
            "[[Browse Free Classes|/classes/]]\n"
            "[[Announcements|/announcements/]]"
        ),
    },
    {
        "id": "courses_browse",
        "title": "Browse paid courses",
        "keys": [
            "paid course", "paid courses", "course", "courses", "paid class",
            "paid classes", "syllabus", "curriculum",
        ],
        "body": (
            "Browse published paid courses on the Courses page.\n\n"
            "Open a course to see price, duration, curriculum, features, benefits, and FAQs.\n"
            "Only published courses appear publicly.\n\n"
            "[[Browse Courses|/courses/]]"
        ),
    },
    {
        "id": "course_enroll",
        "title": "Enroll in a paid course",
        "keys": [
            "enroll", "enrol", "buy course", "join course", "course registration",
            "how to enroll", "pending payment", "payment", "razorpay", "fees", "price",
            "course fee", "how much",
        ],
        "body": (
            "To enroll interest in a paid course:\n\n"
            "1. Click **Browse Courses**\n"
            "2. Open a course\n"
            "3. Log in if asked\n"
            "4. Click **Enroll** on that page\n\n"
            "Enrollment is saved as interest / pending payment. "
            "Always check the course page for the real price - ProjectMateBot does not invent fees. "
            "For payment steps, Contact the mentor.\n\n"
            "[[Browse Courses|/courses/]]\n"
            "[[Contact Support|/contact/]]"
        ),
    },
    {
        "id": "dashboard_overview",
        "title": "Student dashboard",
        "keys": [
            "dashboard", "student dashboard", "my dashboard", "after login",
            "student panel", "overview",
        ],
        "body": (
            "After login, open your **Dashboard**.\n\n"
            "• Learn: Overview, My Classes, Attendance, Project requests\n"
            "• Grow: Rewards, Referrals, Resume Review, My feedbacks\n"
            "• Account: Profile, Notifications, Logout\n\n"
            "[[Open Dashboard|/dashboard/]]"
        ),
    },
    {
        "id": "my_classes",
        "title": "My Classes",
        "keys": [
            "my classes", "my class", "registered classes", "class registrations",
            "dashboard classes",
        ],
        "body": (
            "See free-class registrations in **Dashboard -> My Classes**.\n\n"
            "For the live joining link, check your email (Ask me: Where is my Meet link?).\n\n"
            "[[My Classes|/dashboard/classes/]]"
        ),
    },
    {
        "id": "profile",
        "title": "Edit profile",
        "keys": [
            "profile", "edit profile", "update profile", "change name", "phone number",
            "profile picture", "photo",
        ],
        "body": (
            "Update your profile in **Dashboard -> Profile**:\n\n"
            "• First name, last name\n"
            "• Phone\n"
            "• Profile picture\n"
            "• Change password\n\n"
            "[[Open Profile|/dashboard/profile/]]"
        ),
    },
    {
        "id": "notifications",
        "title": "Notifications",
        "keys": [
            "notification", "notifications", "inbox", "unread", "alerts",
        ],
        "body": (
            "Open **Dashboard -> Notifications** to see messages.\n\n"
            "Opening that page marks notifications as read.\n\n"
            "[[Open Notifications|/dashboard/notifications/]]"
        ),
    },
    {
        "id": "attendance",
        "title": "Attendance",
        "keys": [
            "attendance", "present", "absent", "late", "active attendance",
            "mark attendance", "my attendance",
        ],
        "body": (
            "View your attendance in **Dashboard -> Attendance**.\n\n"
            "• Only the mentor marks attendance after a class\n"
            "• Statuses: Present, Absent, Active (bonus), Excused\n"
            "• Present / Active can earn reward points\n"
            "• About 6 consecutive Present/Active sessions can unlock a consistency reward\n\n"
            "Students cannot mark their own attendance.\n\n"
            "[[My Attendance|/dashboard/attendance/]]"
        ),
    },
    {
        "id": "rewards",
        "title": "Rewards & points",
        "keys": [
            "reward", "rewards", "points", "leaderboard", "achievement", "achievements",
            "level", "how to earn points", "how do rewards work", "earn points",
            "reward points", "my points", "score",
        ],
        "body": (
            "Open **Dashboard -> Rewards** for points, achievements, and leaderboard.\n\n"
            "Common ways to earn points:\n"
            "• Daily login\n"
            "• Class attendance\n"
            "• Feedback submitted\n"
            "• Referral approved\n"
            "• Resume uploaded\n"
            "• Profile completed / consistency bonus\n\n"
            "Exact points can vary - check Rewards for your account.\n\n"
            "[[Open Rewards|/dashboard/rewards/]]"
        ),
    },
    {
        "id": "referrals",
        "title": "Referrals",
        "keys": [
            "referral", "referrals", "refer", "invite friend", "referral code",
            "referral link", "invite",
        ],
        "body": (
            "Share your referral from **Dashboard -> Referrals**:\n\n"
            "1. Copy your unique referral code\n"
            "2. Friend enters it while registering\n"
            "3. Mentor approves the referral\n"
            "4. Points can be credited after approval\n\n"
            "[[Open Referrals|/dashboard/referrals/]]\n"
            "[[Click Register|/accounts/register/]]"
        ),
    },
    {
        "id": "resume",
        "title": "Resume review",
        "keys": [
            "resume", "cv", "resume review", "upload resume", "resume feedback",
        ],
        "body": (
            "Upload your resume in **Dashboard -> Resume Review**.\n\n"
            "• Accepted types: PDF / DOC / DOCX\n"
            "• Status: pending -> in review -> completed / rejected\n"
            "• Mentor may add score and written feedback\n\n"
            "[[Upload Resume|/dashboard/resume/]]"
        ),
    },
    {
        "id": "projects",
        "title": "Custom projects",
        "keys": [
            "project", "projects", "project idea", "custom project", "project plan",
            "project request", "submit project",
        ],
        "body": (
            "Explore custom project plans on the **Project** page.\n\n"
            "• Compare plans and prices on that page\n"
            "• Submit a project idea form (login not required to submit)\n"
            "• Track later in Dashboard -> Project requests (same email)\n\n"
            "[[View Projects|/project/]]\n"
            "[[My Project Requests|/dashboard/project-requests/]]"
        ),
    },
    {
        "id": "feedback",
        "title": "Submit feedback",
        "keys": [
            "feedback", "review", "submit feedback", "write feedback", "rate class",
        ],
        "body": (
            "Submit feedback from the Feedback page or Dashboard -> My feedbacks.\n\n"
            "• Login is required\n"
            "• Feedback stays pending until mentor approval\n"
            "• Approval usually needs workshop + Present/Active attendance\n\n"
            "[[Submit Feedback|/feedback/]]\n"
            "[[My Feedbacks|/dashboard/feedbacks/]]"
        ),
    },
    {
        "id": "testimonials",
        "title": "Testimonials",
        "keys": [
            "testimonial", "testimonials", "student stories", "reviews public",
        ],
        "body": (
            "Public testimonials show approved reviews chosen for the landing page.\n\n"
            "[[View Testimonials|/feedback/testimonials/]]"
        ),
    },
    {
        "id": "announcements",
        "title": "Announcements",
        "keys": [
            "announcement", "announcements", "notice", "notices", "updates",
            "holiday", "placement news",
        ],
        "body": (
            "Read announcements for workshops, placements, holidays, and updates.\n\n"
            "[[Open Announcements|/announcements/]]"
        ),
    },
    {
        "id": "search",
        "title": "Search the site",
        "keys": ["search", "find class", "find course", "site search"],
        "body": (
            "Use site Search (also in the footer) to find classes, courses, and announcements.\n\n"
            "[[Open Search|/search/]]"
        ),
    },
    {
        "id": "about_page",
        "title": "About page",
        "keys": ["about page", "about mentor", "who is mentor", "aniket", "why learn"],
        "body": (
            "Learn about the mentor and why students learn with us on the About page.\n\n"
            "[[About Us|/about/]]"
        ),
    },
    {
        "id": "contact",
        "title": "Contact support",
        "keys": [
            "contact", "support", "help", "whatsapp", "email", "phone",
            "customer care", "talk to mentor", "message",
        ],
        "dynamic": "contact",
        "body": (
            "Reach ProjectMate support here:\n\n"
            "• Use the Contact form\n"
            "• Email / phone shown on Contact and footer\n"
            "• WhatsApp / Instagram / LinkedIn / YouTube icons when enabled\n\n"
            "{contact_block}\n\n"
            "[[Open Contact|/contact/]]"
        ),
    },
    {
        "id": "theme",
        "title": "Dark / light mode",
        "keys": [
            "dark mode", "night mode", "theme", "light mode", "moon", "sun icon",
        ],
        "body": (
            "Use the **moon / sun** icon in the top navbar to switch light and dark theme.\n\n"
            "Your choice is saved for later visits."
        ),
    },
    {
        "id": "mobile",
        "title": "Mobile app",
        "keys": [
            "mobile app", "android app", "ios app", "play store", "app store",
            "mobile", "phone browser",
        ],
        "body": (
            "There is **no separate mobile app**.\n\n"
            "Use ProjectMate in your phone browser - the site is responsive."
        ),
    },
    {
        "id": "materials",
        "title": "Class / course materials",
        "keys": [
            "material", "materials", "notes", "recording", "pdf", "resources",
            "study material",
        ],
        "body": (
            "Study materials may be attached to a class or course by the mentor.\n\n"
            "Check the class/course page, your email, and Announcements. "
            "If something is missing, Contact support.\n\n"
            "[[Browse Free Classes|/classes/]]\n"
            "[[Browse Courses|/courses/]]\n"
            "[[Contact Support|/contact/]]"
        ),
    },
    {
        "id": "certificates",
        "title": "Certificates",
        "keys": ["certificate", "certificates", "completion certificate"],
        "body": (
            "Certificates may be issued by the mentor when available.\n\n"
            "There is no automatic public download button for every student. "
            "Ask via Contact if certificates were announced for your batch.\n\n"
            "[[Contact Support|/contact/]]"
        ),
    },
    {
        "id": "deactivated",
        "title": "Account deactivated",
        "keys": [
            "deactivated", "account blocked", "account disabled", "inactive account",
        ],
        "body": (
            "If your student account was deactivated, you may still sign in with limited access. "
            "For full access, contact the mentor.\n\n"
            "[[Contact Support|/contact/]]"
        ),
    },
    {
        "id": "home_page",
        "title": "Home page",
        "keys": ["home", "homepage", "landing page", "main page"],
        "body": (
            "The home page shows upcoming classes/courses, announcements, FAQs, "
            "gallery, testimonials, and a contact form.\n\n"
            "[[Go to Home|/]]"
        ),
    },
    {
        "id": "faq_page",
        "title": "FAQs on the site",
        "keys": ["faq", "faqs", "frequently asked"],
        "body": (
            "Published FAQs appear on the home page.\n\n"
            "You can also ask ProjectMateBot how-to questions, or open Contact for personal cases.\n\n"
            "[[Go to Home|/]]\n"
            "[[Open Contact|/contact/]]"
        ),
    },
]

SUGGESTED_QUESTIONS = [
    "How do I create an account?",
    "How do I join a free class?",
    "Where is my Meet link?",
    "How do paid courses work?",
    "How do rewards work?",
    "How do referrals work?",
    "How do I upload my resume?",
    "How do I contact support?",
]
