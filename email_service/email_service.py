import os
import re
import smtplib
import ssl
import sys
from email.message import EmailMessage
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

# Shared security controls, tagged [SC-xx]; see the control table in SECURITY.md
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))
import agent_guard as guard  # noqa: E402
from agent_guard import GuardError  # noqa: E402

SERVER = "email_service"

# Initialize FastMCP server
mcp = FastMCP("Email Service")

# [SC-05] Tool risk annotations: sending email reaches the outside world and
# cannot be undone, so clients should always ask a human first (SC-07)
SENDS_EXTERNALLY = ToolAnnotations(readOnlyHint=False, destructiveHint=True,
                                   idempotentHint=False, openWorldHint=True)

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@([A-Za-z0-9\-]+\.)+[A-Za-z]{2,}")
_URL_RE = re.compile(r"https?://([^/\s\"'<>]+)", re.I)


def _check_recipient(recipient: str, policy: dict) -> None:
    # [SC-01] Recipient allowlist: breaks the exfiltration leg of the lethal
    # trifecta. Exactly one address; must match an approved address or domain.
    recipient = recipient.strip()
    if not _EMAIL_RE.fullmatch(recipient):
        raise GuardError("recipient must be exactly one valid email address.")
    domain = recipient.rsplit("@", 1)[1].lower()
    allowed_addrs = {a.lower() for a in policy.get("allowed_recipients", [])}
    allowed_domains = [d.lower() for d in policy.get("allowed_recipient_domains", [])]
    if recipient.lower() in allowed_addrs:
        return
    if any(domain == d or domain.endswith("." + d) for d in allowed_domains):
        return
    guard.alert("recipient_blocked", {"recipient": recipient})
    raise GuardError(f"Recipient '{recipient}' is not on the approved recipient list.")


def _check_content(subject: str, body: str, is_html: bool, policy: dict) -> None:
    # [SC-02] Email content limits: single-line subject (no header injection),
    # bounded size, and HTML off (no tracking pixels or disguised links)
    if "\r" in subject or "\n" in subject:
        raise GuardError("subject must be a single line.")
    if len(subject) > policy.get("max_subject_chars", 200):
        raise GuardError("subject is too long.")
    if len(body) > policy.get("max_body_chars", 5000):
        raise GuardError(f"body exceeds {policy.get('max_body_chars', 5000)} characters.")
    if is_html and not policy.get("allow_html", False):
        raise GuardError("HTML email is disabled by policy; send plain text.")
    # [SC-03] Outbound link allowlist: stops data being smuggled out in a URL
    if policy.get("block_external_links", True):
        allowed = [d.lower() for d in policy.get("allowed_link_domains", [])]
        for host in _URL_RE.findall(body):
            host = host.split(":")[0].lower()
            if not any(host == d or host.endswith("." + d) for d in allowed):
                guard.alert("external_link_blocked", {"host": host})
                raise GuardError(f"Links to '{host}' are not allowed in outgoing email.")
    # [SC-06] Grounding check: prices must match real search results
    mode = policy.get("grounding_check", "block")
    if mode != "off":
        missing = guard.ungrounded_prices(body)
        if missing:
            guard.alert("ungrounded_figures", {"figures": missing, "mode": mode})
            if mode == "block":
                raise GuardError(
                    "These prices do not match any recent flight or hotel search result: "
                    f"{', '.join(missing)}. Copy figures exactly from the tool results."
                )


@mcp.tool(annotations=SENDS_EXTERNALLY)
def send_email(
    recipient: str,
    subject: str,
    body: str,
    is_html: bool = False
) -> str:
    """
    Send one email to one approved recipient. Only use this when the user has
    explicitly asked for an email to be sent. Recipients must be on the
    organisation's approved list, and any prices in the body must be copied
    exactly from flight or hotel search results.

    Args:
        recipient: The email address of the receiver (one address only).
        subject: The subject line of the email (single line).
        body: The main content of the email (plain text).
        is_html: HTML is disabled unless the security policy allows it.
    """
    args = {"recipient": recipient, "subject": subject, "body": body, "is_html": is_html}
    try:
        guard.guarded(SERVER, "send_email", args)  # [SC-18] kill switch
        policy = guard.load_policy().get("email", {})
        _check_recipient(recipient, policy)
        _check_content(subject, body, is_html, policy)
        # [SC-19] Daily email cap
        guard.rate_limit("email_service.send_email.daily",
                         policy.get("max_emails_per_day", 10), 86400)

        # [SC-12] Secrets from the OS keychain, not the Claude config file
        sender = guard.get_secret("EMAIL_SENDER")
        password = guard.get_secret("EMAIL_PASSWORD")
        if not sender or not password:
            raise GuardError("EMAIL_SENDER / EMAIL_PASSWORD are not configured on the server.")
        smtp_server = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
        smtp_port = int(os.environ.get("SMTP_PORT", "465"))
        guard.check_egress(smtp_server)  # [SC-13] only approved SMTP hosts
    except GuardError as e:
        guard.audit(SERVER, "send_email", args, "blocked", str(e))  # [SC-15]
        return f"Blocked: {e}"

    user = guard.acting_user()
    footer = policy.get("disclosure_footer", "").format(user=user)

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient.strip()
    # [SC-17] Identity & attribution: the agent and the human it acted for are
    # traceable from the message itself, and the recipient is told AI sent it
    msg["X-AI-Agent"] = "power_user_demo/email_service"
    msg["X-Requested-By"] = user

    # Set the content type (Plain text vs HTML)
    if is_html:
        msg.set_content("Please use an HTML compatible email client to view this message.")
        msg.add_alternative(f"{body}<hr><p><small>{footer}</small></p>", subtype='html')
    else:
        msg.set_content(f"{body}\n\n--\n{footer}" if footer else body)

    try:
        # Encrypted SMTP with certificate verification
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(smtp_server, smtp_port, context=context) as server:
            server.login(sender, password)
            server.send_message(msg)
    except Exception as e:
        return guard.safe_error(SERVER, "send_email", args, e)  # [SC-14]

    guard.audit(SERVER, "send_email", args, "ok", f"sent to {recipient}")  # [SC-15]
    return f"Email successfully sent to {recipient}"


if __name__ == "__main__":
    mcp.run()
