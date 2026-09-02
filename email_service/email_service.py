import os
import smtplib
import ssl
import sys
from email.message import EmailMessage
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("Email Service")

# CONFIGURATION - set via env vars in claude_desktop_config.json
SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "465"))
SENDER_EMAIL = os.environ.get("EMAIL_SENDER")
APP_PASSWORD = os.environ.get("EMAIL_PASSWORD")

@mcp.tool()
def send_email(
    recipient: str,
    subject: str,
    body: str,
    is_html: bool = False
) -> str:
    """
    A generic tool to send emails. Use this to send reports, summaries,
    notifications, or any text-based communication to a user.

    Args:
        recipient: The email address of the receiver.
        subject: The subject line of the email.
        body: The main content of the email.
        is_html: Set to True if the body contains HTML formatting.
    """
    if not SENDER_EMAIL or not APP_PASSWORD:
        return "Error: EMAIL_SENDER / EMAIL_PASSWORD are not configured on the server."

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = SENDER_EMAIL
    msg["To"] = recipient

    # Set the content type (Plain text vs HTML)
    if is_html:
        msg.set_content("Please use an HTML compatible email client to view this message.")
        msg.add_alternative(body, subtype='html')
    else:
        msg.set_content(body)

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, context=context) as server:
            server.login(SENDER_EMAIL, APP_PASSWORD)
            server.send_message(msg)
        return f"Email successfully sent to {recipient}"
    except Exception as e:
        # Logging to stderr ensures errors show up in MCP logs without breaking the JSON-RPC pipe
        print(f"SMTP Error: {str(e)}", file=sys.stderr)
        return f"Error: {str(e)}"

if __name__ == "__main__":
    mcp.run()