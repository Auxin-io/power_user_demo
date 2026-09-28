# MCP Servers

> **Security:** these servers run behind agentic security controls (approval
> for sending email, recipient allowlist, injection filtering, audit log, kill
> switch and more). See [SECURITY.md](SECURITY.md) for the control map, setup
> and test plan. Secrets now live in the OS keychain, not in the config below.

Three Model Context Protocol (MCP) servers for use with Claude Desktop:

| Folder | Server name | Purpose |
|---|---|---|
| [`booking.com/`](booking.com/booking.py) | `booking_hotels` | Search destinations and hotel listings via the RapidAPI Booking.com API |
| [`email_service/`](email_service/email_service.py) | `email_service` | Send emails via SMTP (Gmail by default) |
| [`flight_search/`](flight_search/flight_search.py) | `flight_search` | Search real-time flight prices via Google Flights (`fast-flights`) |

## Prerequisites

- Python 3.13
- [`uv`](https://docs.astral.sh/uv/) installed
- Claude Desktop

## 1. Install dependencies

Each server is its own `uv` project with its own `.venv`. From this directory, run:

```powershell
uv --directory booking.com sync
uv --directory email_service sync
uv --directory flight_search sync
```

This creates `.venv/` in each folder with all required packages (`mcp`, `httpx`, `fast-flights`, etc.).

## 2. Store credentials in the OS keychain

Secrets are **not** put in Claude's config file (it is plaintext and readable
by any process running as you). The servers read them from Windows Credential
Manager under the service name `power_user_demo` ([SC-12](SECURITY.md#security-control-table)).

| Server | Secret | Value |
|---|---|---|
| `booking_hotels` | `RAPIDAPI_KEY` | Your key from [RapidAPI](https://rapidapi.com/) (search "Booking.com" API) |
| `email_service` | `EMAIL_SENDER` | The Gmail address to send from |
| `email_service` | `EMAIL_PASSWORD` | A [Gmail App Password](https://myaccount.google.com/apppasswords) (not your regular password) |
| `flight_search` | — | No credentials required |

Store them with a hidden prompt (nothing is echoed or logged):

```powershell
uv run --directory email_service python ../scripts/store_secrets.py
```

Environment variables with the same names still work as a fallback, but each
use raises a `secret_from_env` security alert.

Optional, non-secret settings (set in `env` in step 3 if needed):

- `RAPIDAPI_HOST` (default `booking-com15.p.rapidapi.com`; must be on the egress allowlist)
- `SMTP_SERVER` (default `smtp.gmail.com`; must be on the egress allowlist)
- `SMTP_PORT` (default `465`, SSL)

## 3. Set the security policy

Edit [`security_policy.json`](security_policy.json). At minimum, set who email
may be sent to:

```json
"allowed_recipient_domains": ["ncdhhs.gov"],
"allowed_recipients": ["alex@example.com"]
```

Changes take effect on the next tool call; no restart needed. See
[SECURITY.md](SECURITY.md) for every setting and the control it drives.

## 4. Register the servers with Claude

### Claude Desktop

Open Claude Desktop's config file:

```
%APPDATA%\Claude\claude_desktop_config.json
```

Add the following inside `"mcpServers"`, replacing `<path-to-this-folder>`
with the full path to this folder (forward slashes). There is deliberately
**no** `EMAIL_PASSWORD` or `RAPIDAPI_KEY` here:

```json
{
  "mcpServers": {
    "booking_hotels": {
      "command": "<path-to-this-folder>/booking.com/.venv/Scripts/python.exe",
      "args": [
        "<path-to-this-folder>/booking.com/booking.py"
      ],
      "env": {
        "RAPIDAPI_HOST": "booking-com15.p.rapidapi.com"
      }
    },
    "email_service": {
      "command": "<path-to-this-folder>/email_service/.venv/Scripts/python.exe",
      "args": [
        "<path-to-this-folder>/email_service/email_service.py"
      ]
    },
    "flight_search": {
      "command": "<path-to-this-folder>/flight_search/.venv/Scripts/python.exe",
      "args": [
        "<path-to-this-folder>/flight_search/flight_search.py"
      ]
    }
  }
}
```

Then, in Claude Desktop's connector settings, set **`send_email`** to
**"Always ask"** so every email needs your approval ([SC-07](SECURITY.md#security-control-table)).
Desktop does not run Claude Code hooks, so the server-side controls are its
main protection.

Fully quit and reopen Claude Desktop for the servers to load.

### Claude Code

Open this folder in Claude Code. The servers are already defined in
[`.mcp.json`](.mcp.json) (no secrets), and [`.claude/settings.json`](.claude/settings.json)
adds approval rules, deny rules and security hooks. Run `/mcp` and approve the
three project servers the first time.

## 5. Try it

Use a recipient that is on your allowlist (step 3):

```
Find flights from JFK to Qatar on 2026-10-15, find hotels in Qatar for the
same dates (checkout 2026-10-20), then email a summary of both to
alex@example.com.
```

The two searches run without prompting; Claude asks you to approve the email
before it is sent. To see the controls block attacks, follow
[How to test](SECURITY.md#how-to-test).

This chains all three servers in one turn:

1. `flight_search.search_flights(origin, destination, date)`
2. `booking_hotels.search_destinations(query)` → `booking_hotels.get_hotels(destination_id, checkin_date, checkout_date)`
3. `email_service.send_email(recipient, subject, body)`
