"""Notification and email service layer."""
import logging
import re
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template import Template, Context
from django.utils.html import escape, strip_tags

logger = logging.getLogger(__name__)

_TEMPLATE_VAR_RE = re.compile(r"(\{\{[^}]+\}\})")


class EmailHtmlBuilder:
    """Turn admin plain text into a branded HTML email."""

    @staticmethod
    def plain_text_to_inner_html(text: str) -> str:
        """Escape HTML, keep {{placeholders}}, convert paragraphs/newlines."""
        text = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
        if not text:
            return "<p style=\"margin:0 0 14px;color:#334155;\">&nbsp;</p>"

        paragraphs = re.split(r"\n\s*\n", text)
        blocks = []
        for para in paragraphs:
            lines = []
            for line in para.split("\n"):
                chunks = []
                for part in _TEMPLATE_VAR_RE.split(line):
                    if _TEMPLATE_VAR_RE.fullmatch(part):
                        chunks.append(part)
                    else:
                        chunks.append(escape(part))
                lines.append("".join(chunks))
            blocks.append(
                '<p style="margin:0 0 14px;color:#334155;font-size:15px;line-height:1.6;">'
                + "<br>".join(lines)
                + "</p>"
            )
        return "\n".join(blocks)

    @staticmethod
    def wrap(subject: str, body_text: str, *, site_name: str | None = None, footer_note: str = "") -> str:
        """Build full branded HTML from subject + plain text body."""
        try:
            from apps.core.models import SiteSettings

            site = SiteSettings.load()
            site_name = site_name or site.site_name
            contact = getattr(site, "contact_email", "") or ""
        except Exception:
            site_name = site_name or "Aniket.ProjectMate"
            contact = ""

        inner = EmailHtmlBuilder.plain_text_to_inner_html(body_text)
        safe_subject = escape(subject or "Message")
        safe_site = escape(site_name)
        footer = footer_note or f"You’re receiving this because you’re part of {site_name}."
        safe_footer = escape(footer)
        contact_html = (
            f'<a href="mailto:{escape(contact)}" style="color:#1a365d;text-decoration:none;">{escape(contact)}</a>'
            if contact
            else ""
        )

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{safe_subject}</title>
</head>
<body style="margin:0;padding:0;background:#f8fafc;font-family:'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
  <div style="display:none;max-height:0;overflow:hidden;opacity:0;">{safe_subject}</div>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f8fafc;padding:28px 12px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;background:#ffffff;border-radius:16px;overflow:hidden;border:1px solid rgba(15,23,42,0.08);box-shadow:0 10px 40px rgba(15,23,42,0.08);">
          <tr>
            <td style="background:linear-gradient(135deg,#1a365d,#0b1929);padding:22px 28px;">
              <div style="font-size:20px;font-weight:700;color:#ffffff;letter-spacing:-0.02em;">{safe_site}</div>
              <div style="font-size:13px;color:rgba(255,255,255,0.85);margin-top:4px;">Learn. Build. Grow.</div>
            </td>
          </tr>
          <tr>
            <td style="padding:28px 28px 8px;">
              <h1 style="margin:0 0 18px;font-size:20px;line-height:1.35;color:#0f172a;font-weight:700;">{safe_subject}</h1>
              {inner}
            </td>
          </tr>
          <tr>
            <td style="padding:8px 28px 28px;">
              <div style="height:1px;background:rgba(15,23,42,0.08);margin:8px 0 18px;"></div>
              <p style="margin:0;font-size:12px;line-height:1.5;color:#64748b;">{safe_footer}</p>
              {"<p style='margin:8px 0 0;font-size:12px;color:#64748b;'>" + contact_html + "</p>" if contact_html else ""}
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""

    @staticmethod
    def build(subject: str, body_text: str, **kwargs) -> tuple[str, str]:
        """Return (body_html, body_text) ready to send."""
        plain = (body_text or "").strip()
        html = EmailHtmlBuilder.wrap(subject, plain, **kwargs)
        return html, plain


class NotificationService:
    @staticmethod
    def notify(user, title, message, level="info", link=""):
        from apps.notifications.models import Notification

        return Notification.objects.create(
            user=user,
            title=title,
            message=message,
            level=level,
            link=link,
        )

    @staticmethod
    def mark_all_read(user):
        from apps.notifications.models import Notification

        return Notification.objects.filter(user=user, is_read=False).update(is_read=True)


class EmailService:
    @staticmethod
    def build_html_from_text(subject, body_text, **kwargs):
        """Public helper: plain text → branded HTML."""
        return EmailHtmlBuilder.build(subject, body_text, **kwargs)

    @staticmethod
    def render_template(template_code, context_dict):
        from apps.notifications.models import EmailTemplate

        try:
            tpl = EmailTemplate.objects.get(code=template_code, is_active=True)
        except EmailTemplate.DoesNotExist:
            return None, None, None

        ctx = Context(context_dict)
        subject = Template(tpl.subject).render(ctx)
        # Prefer stored HTML; if missing, generate from plain text
        if tpl.body_html.strip():
            body_html = Template(tpl.body_html).render(ctx)
        else:
            raw_text = Template(tpl.body_text or "").render(ctx)
            body_html, _ = EmailHtmlBuilder.build(subject, raw_text)
        body_text = Template(tpl.body_text or strip_tags(tpl.body_html)).render(ctx)
        return subject, body_html, body_text

    @staticmethod
    def send(
        to_email,
        subject,
        body_html,
        body_text="",
        recipient=None,
        template=None,
        meta=None,
        ics_content=None,
    ):
        from apps.notifications.models import EmailLog

        log = EmailLog.objects.create(
            recipient=recipient,
            to_email=to_email,
            subject=subject,
            body_html=body_html,
            template=template,
            status=EmailLog.Status.QUEUED,
            meta=meta or {},
        )
        try:
            msg = EmailMultiAlternatives(
                subject=subject,
                body=body_text or strip_tags(body_html),
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[to_email],
                reply_to=[getattr(settings, "PROJECT_MAIL", "") or settings.DEFAULT_FROM_EMAIL],
            )
            msg.attach_alternative(body_html, "text/html")
            if ics_content:
                msg.attach("invite.ics", ics_content, "text/calendar")
            msg.send(fail_silently=False)
            log.status = EmailLog.Status.SENT
            log.save(update_fields=["status"])
            logger.info("Email sent to %s: %s", to_email, subject)
            return log
        except Exception as exc:
            log.status = EmailLog.Status.FAILED
            log.error_message = str(exc)
            log.save(update_fields=["status", "error_message"])
            logger.exception("Failed to send email to %s", to_email)
            return log

    @staticmethod
    def send_plain(to_email, subject, body_text, recipient=None, template=None, meta=None):
        """Compose branded HTML from plain text and send."""
        body_html, plain = EmailHtmlBuilder.build(subject, body_text)
        return EmailService.send(
            to_email=to_email,
            subject=subject,
            body_html=body_html,
            body_text=plain,
            recipient=recipient,
            template=template,
            meta=meta,
        )

    @staticmethod
    def send_from_template(template_code, to_email, context_dict, recipient=None, ics_content=None):
        from apps.notifications.models import EmailTemplate

        subject, body_html, body_text = EmailService.render_template(template_code, context_dict)
        if not subject:
            # Fallback: wrap plain/HTML context into branded layout
            subject = context_dict.get("subject", "Aniket.ProjectMate")
            if context_dict.get("body_text"):
                body_html, body_text = EmailHtmlBuilder.build(subject, context_dict["body_text"])
            else:
                body_html = context_dict.get("body_html", "<p>Hello from ProjectMate!</p>")
                body_text = strip_tags(body_html)
            template = None
        else:
            template = EmailTemplate.objects.filter(code=template_code).first()

        return EmailService.send(
            to_email=to_email,
            subject=subject,
            body_html=body_html,
            body_text=body_text,
            recipient=recipient,
            template=template,
            meta={"template_code": template_code},
            ics_content=ics_content,
        )

    @staticmethod
    def build_ics(title, description, start_dt, duration_minutes, location=""):
        """Build a simple calendar invite string."""
        from datetime import timedelta

        end_dt = start_dt + timedelta(minutes=duration_minutes)
        fmt = "%Y%m%dT%H%M%S"
        return (
            "BEGIN:VCALENDAR\n"
            "VERSION:2.0\n"
            "PRODID:-//Aniket.ProjectMate//EN\n"
            "BEGIN:VEVENT\n"
            f"DTSTART:{start_dt.strftime(fmt)}\n"
            f"DTEND:{end_dt.strftime(fmt)}\n"
            f"SUMMARY:{title}\n"
            f"DESCRIPTION:{description.replace(chr(10), ' ')}\n"
            f"LOCATION:{location}\n"
            "END:VEVENT\n"
            "END:VCALENDAR\n"
        )
