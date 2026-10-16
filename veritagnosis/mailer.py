"""
Sending the verification code by email, through Gmail.

Gmail will not accept your normal password from a program. You create an
"App password" instead — a 16-character code Google generates for one app,
which you can revoke without changing your real password. It requires 2-Step
Verification to be on for your Google account.

  1. Google Account -> Security -> turn on 2-Step Verification
  2. Google Account -> Security -> App passwords
  3. Name it "Veritagnosis", copy the 16 characters
  4. Put it in .env as VG_SMTP_PASSWORD (spaces are fine, they get stripped)

With nothing configured the app still works: the code prints to the terminal,
exactly as before. Nothing breaks, you just do the copying yourself.
"""

from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage

from veritagnosis import config


class MailError(Exception):
    """Raised when sending fails for a reason the user should hear about."""


def is_configured() -> bool:
    return bool(config.smtp_user() and config.smtp_password())


def _plain(code: str, minutes: int) -> str:
    return (
        f"Your Veritagnosis code is {code}\n\n"
        f"Enter it in the app to sign in. It expires in {minutes} minutes and\n"
        f"only works once.\n\n"
        f"Didn't try to sign in? You can ignore this email. Someone probably\n"
        f"typed your address by mistake, and nobody can get in without the code.\n"
    )


def _html(code: str, minutes: int) -> str:
    """Deliberately plain. Email clients strip most CSS, and a code that is hard
    to read defeats the point — so: big, spaced, high contrast, one message."""
    spaced = " ".join(code)
    return f"""\
<!doctype html><html><body style="margin:0;padding:0;background:#F4F2F8;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"
       style="background:#F4F2F8;padding:32px 16px;">
 <tr><td align="center">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
         style="max-width:440px;background:#FFFFFF;border-radius:14px;
                border:1px solid #E5E2ED;padding:32px;
                font-family:-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
   <tr><td style="font-size:13px;letter-spacing:.12em;text-transform:uppercase;
                  color:#6D5BB8;font-weight:700;padding-bottom:14px;">Veritagnosis</td></tr>
   <tr><td style="font-size:22px;font-weight:600;color:#1F1B2E;padding-bottom:8px;">
     Here's your code</td></tr>
   <tr><td style="font-size:15px;color:#5D5873;line-height:1.55;padding-bottom:24px;">
     Enter this code in the app to sign in.</td></tr>
   <tr><td align="center" style="padding:20px 0 24px;">
     <div style="display:inline-block;background:#F1EEFA;border:1px solid #DDD6F2;
                 border-radius:12px;padding:18px 26px;font-size:34px;font-weight:700;
                 letter-spacing:10px;color:#3D3268;
                 font-family:'SFMono-Regular',Consolas,monospace;">{spaced}</div></td></tr>
   <tr><td style="font-size:14px;color:#5D5873;line-height:1.55;padding-bottom:6px;">
     It expires in {minutes} minutes and only works once.</td></tr>
   <tr><td style="font-size:13px;color:#8F8AA4;line-height:1.55;padding-top:18px;
                  border-top:1px solid #EFEDF4;">
     Didn't try to sign in? You can ignore this email. Someone probably mistyped
     their address, and nobody can get into your account without this code.</td></tr>
  </table>
 </td></tr>
</table>
</body></html>"""


def send_verification_code(to_email: str, code: str, minutes: int = 15) -> bool:
    """Send the code. Returns True if it was emailed, False if it was only
    printed to the terminal because email isn't set up.

    Raises MailError when email IS set up but the send failed — the student is
    waiting on a message that will never arrive, so that must not be silent.
    """
    if not is_configured():
        print(f"\n[veritagnosis] email not configured — code for {to_email}: {code}\n")
        return False

    msg = EmailMessage()
    msg["Subject"] = f"{code} is your Veritagnosis code"
    # The display name is always "Veritagnosis", whatever account is doing the
    # sending. A student receiving a code should see the app's name, not
    # whoever's mailbox it happens to be relayed through — and if
    # VG_MAIL_FROM_NAME is ever left blank or misconfigured, falling back to a
    # personal email address in the From line would be a small privacy leak
    # rather than a cosmetic bug.
    msg["From"] = f"{config.mail_from_name() or 'Veritagnosis'} <{config.smtp_user()}>"
    # Replies go to the sending account rather than nowhere, so a confused
    # student hitting reply reaches a human.
    msg["Reply-To"] = config.smtp_user()
    msg["To"] = to_email
    msg.set_content(_plain(code, minutes))
    msg.add_alternative(_html(code, minutes), subtype="html")

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(config.SMTP_HOST, config.SMTP_PORT,
                              context=context, timeout=20) as smtp:
            smtp.login(config.smtp_user(), config.smtp_password())
            smtp.send_message(msg)
    except smtplib.SMTPAuthenticationError as e:
        raise MailError(
            "Gmail refused the login. Check VG_SMTP_PASSWORD is a 16-character "
            "App password (not your normal Google password), and that 2-Step "
            "Verification is on for that account."
        ) from e
    except (smtplib.SMTPException, OSError) as e:
        raise MailError(f"Could not reach Gmail: {e}") from e

    print(f"[veritagnosis] code emailed to {to_email}")
    return True
