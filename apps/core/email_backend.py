"""Project mail uses aniketkapale02@gmail.com, sent through Cloudflare when configured."""
import smtplib

from django.conf import settings
from django.core.mail.backends.smtp import EmailBackend


class ProjectEmailBackend(EmailBackend):
    """Send via Cloudflare Email Service SMTP when an API token is set.

    Username is the literal ``api_token``. The From address stays the project
    mailbox (aniketkapale02@gmail.com). Without a token, Gmail SMTP is used.
    """

    def __init__(self, *args, **kwargs):
        token = (getattr(settings, "CLOUDFLARE_API_TOKEN", "") or "").strip()
        if token:
            kwargs["host"] = "smtp.mx.cloudflare.net"
            kwargs["port"] = 465
            kwargs["username"] = "api_token"
            kwargs["password"] = token
            kwargs["use_tls"] = False
            kwargs["use_ssl"] = True
        super().__init__(*args, **kwargs)

    def open(self):
        if self.connection:
            return False
        if self.use_ssl:
            self.connection = smtplib.SMTP_SSL(self.host, self.port, timeout=self.timeout)
        else:
            self.connection = smtplib.SMTP(self.host, self.port, timeout=self.timeout)
            if self.use_tls:
                self.connection.starttls()
        if self.username and self.password:
            self.connection.login(self.username, self.password)
        return True
