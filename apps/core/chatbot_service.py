"""ProjectMateBot — knowledge-base only (no paid API / no random answers)."""
from __future__ import annotations

import re
from typing import Any

from apps.core.chatbot_kb import KNOWLEDGE_BASE, SUGGESTED_QUESTIONS
from apps.core.models import SiteSettings

# Common typos / Hinglish -> English tokens for matching
_TYPO_MAP = {
    "regster": "register",
    "registation": "registration",
    "registr": "register",
    "logn": "login",
    "logiin": "login",
    "pasword": "password",
    "passowrd": "password",
    "fogot": "forgot",
    "forgt": "forgot",
    "refferal": "referral",
    "referal": "referral",
    "referrel": "referral",
    "atendance": "attendance",
    "attendence": "attendance",
    "cource": "course",
    "corse": "course",
    "cours": "course",
    "proyect": "project",
    "projet": "project",
    "dasboard": "dashboard",
    "dashbord": "dashboard",
    "suport": "support",
    "helpp": "help",
    "whatsap": "whatsapp",
    "watsapp": "whatsapp",
    "anouncment": "announcement",
    "announcment": "announcement",
    "testimonal": "testimonial",
    "resum": "resume",
    "enrole": "enroll",
    "enrol": "enroll",
    "sinup": "signup",
    "singup": "signup",
    "acount": "account",
    "accunt": "account",
    "notifcation": "notification",
    "notfication": "notification",
    "leedrboard": "leaderboard",
    "leaderbord": "leaderboard",
    "acheivement": "achievement",
    "meetlink": "meet link",
    "googmeet": "google meet",
    "kaise": "how",
    "kya": "what",
    "hai": "",
    "please": "",
    "pls": "",
    "plz": "",
}


def _site_contact_block() -> str:
    site = SiteSettings.load()
    lines = []
    name = getattr(site, "site_name", None) or "Aniket.ProjectMate"
    lines.append(f"Site: **{name}**")
    if getattr(site, "contact_email", None):
        lines.append(f"Email: `{site.contact_email}`")
    if getattr(site, "contact_phone", None):
        lines.append(f"Phone: `{site.contact_phone}`")
    if getattr(site, "contact_address", None):
        lines.append(f"Address: {site.contact_address}")
    if getattr(site, "whatsapp_url", None) and getattr(site, "show_whatsapp_icon", True):
        lines.append("WhatsApp: use the green floating icon on the site")
    return "\n".join(lines) if lines else "See `/contact/` for current email and phone."


def normalize(text: str) -> str:
    text = (text or "").lower()
    text = text.replace("'", "'").replace("'", "'")
    text = re.sub(r"[^a-z0-9\s+/]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    parts: list[str] = []
    for w in text.split():
        mapped = _TYPO_MAP.get(w, w)
        if mapped:
            parts.extend(mapped.split())
    return " ".join(parts)


def _score_entry(norm: str, entry: dict[str, Any]) -> int:
    """Higher score = better match. Longer / phrase keys weigh more."""
    score = 0
    hits = 0
    for key in entry.get("keys") or []:
        k = normalize(key)
        if not k:
            continue
        if " " in k:
            if k in norm:
                score += 8 + min(6, len(k.split()) * 2)
                hits += 1
        else:
            if re.search(rf"(^|\s){re.escape(k)}(\s|$)", norm):
                # Longer distinctive words beat short noise words
                if len(k) >= 7:
                    score += 6
                elif len(k) >= 5:
                    score += 5
                elif len(k) >= 4:
                    score += 3
                else:
                    score += 2
                hits += 1
    if hits >= 2:
        score += 3
    return score


def _format_body(entry: dict[str, Any]) -> str:
    body = entry.get("body") or ""
    if entry.get("dynamic") == "contact":
        body = body.replace("{contact_block}", _site_contact_block())
    return body


def _unknown_reply(raw: str, corrected: str) -> dict:
    tips = "\n".join(f"• {q}" for q in SUGGESTED_QUESTIONS[:6])
    spell_note = ""
    if corrected and corrected.lower() != (raw or "").strip().lower():
        spell_note = f'I tried reading it as: "{corrected}"\n\n'

    return {
        "reply": (
            "I could not find a clear match in the ProjectMate help guide.\n\n"
            f"{spell_note}"
            "**Please check your spelling** and ask only about ProjectMate topics "
            "(account, classes, courses, dashboard, rewards, referrals, resume, "
            "projects, feedback, announcements, or contact).\n\n"
            "I do **not** give random answers outside this knowledge base.\n\n"
            "Try asking like this:\n"
            f"{tips}"
        ),
        "mode": "kb",
        "matched": False,
        "understood": "",
    }


def ask_matebot(message: str, history: list[dict] | None = None) -> dict:
    """
    Answer from the project knowledge base only.
    No external API. Unmatched -> ask to check spelling / related questions.
    """
    del history  # reserved for future context; KB answers are self-contained
    raw = (message or "").strip()
    if not raw:
        return {
            "reply": "Please type a ProjectMate question (for example: How do I register?).",
            "mode": "kb",
            "matched": False,
            "understood": "",
        }

    if len(raw) > 4000:
        raw = raw[:4000]

    norm = normalize(raw)
    corrected = raw[:1].upper() + raw[1:] if raw else raw

    best: dict[str, Any] | None = None
    best_score = 0
    second_score = 0
    for entry in KNOWLEDGE_BASE:
        score = _score_entry(norm, entry)
        if score > best_score:
            second_score = best_score
            best_score = score
            best = entry
        elif score > second_score:
            second_score = score

    # Greetings / thanks / bye can match on short tokens
    if best and best.get("id") in {"greet", "thanks", "bye"}:
        min_score = 2
    else:
        # Need a solid keyword (e.g. rewards, register, meet)
        min_score = 5

    # Ambiguous: two topics nearly tied and both weak -> refuse
    if best and best_score >= min_score and (best_score - second_score) < 2 and second_score >= min_score:
        # Still allow if clearly same family; otherwise ask to be more specific
        if best_score < 10:
            return {
                "reply": (
                    "Your question matches more than one ProjectMate topic.\n\n"
                    "**Please check your spelling** and ask one clear question, for example:\n"
                    + "\n".join(f"• {q}" for q in SUGGESTED_QUESTIONS[:6])
                ),
                "mode": "kb",
                "matched": False,
                "understood": "",
            }

    if not best or best_score < min_score:
        return _unknown_reply(raw, corrected)

    preface = ""
    if best_score < 10 and len(norm.split()) >= 2:
        preface = f"I understood: **{best['title']}**.\n\n"

    return {
        "reply": preface + _format_body(best),
        "mode": "kb",
        "matched": True,
        "understood": best.get("title", ""),
        "topic_id": best.get("id", ""),
    }


def llm_enabled() -> bool:
    """Kept for API compatibility - always False (no paid AI)."""
    return False
