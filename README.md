# MCP Servers

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

## 2. Configure credentials

### `booking_hotels`

Requires two environment variables, set in Claude Desktop's config (see step 3):

- `RAPIDAPI_KEY` — your key from [RapidAPI](https://rapidapi.com/) (search "Booking.com" API)
- `RAPIDAPI_HOST` (default `booking-com15.p.rapidapi.com`)

### `email_service`

Requires two environment variables, set in Claude Desktop's config (see step 3):

- `EMAIL_SENDER` — the Gmail address to send from
- `EMAIL_PASSWORD` — a [Gmail App Password](https://myaccount.google.com/apppasswords) (not your regular password)

Optional, if not using Gmail's default SSL settings:

- `SMTP_SERVER` (default `smtp.gmail.com`)
- `SMTP_PORT` (default `465`, SSL)

### `flight_search`

No credentials required.

## 3. Register the servers with Claude Desktop

Open Claude Desktop's config file:

```
%APPDATA%\Claude\claude_desktop_config.json
```

Add the following inside `"mcpServers"` (adjust the path if this folder is located elsewhere), replacing `<...>` with your actual values:

```json
{
  "mcpServers": {
    "booking_hotels": {
      "command": "<path-to-this-folder>/booking.com/.venv/Scripts/python.exe",
      "args": [
        "<path-to-this-folder>/booking.com/booking.py"
      ],
      "env": {
        "RAPIDAPI_KEY": "<your-rapidapi-key>",
        "RAPIDAPI_HOST": "booking-com15.p.rapidapi.com"
      }
    },
    "email_service": {
      "command": "<path-to-this-folder>/email_service/.venv/Scripts/python.exe",
      "args": [
        "<path-to-this-folder>/email_service/email_service.py"
      ],
      "env": {
        "EMAIL_SENDER": "<your-gmail-address>",
        "EMAIL_PASSWORD": "<your-gmail-app-password>"
      }
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

## 4. Restart Claude Desktop

Fully quit and reopen Claude Desktop for the new servers to load.

## 5. Try it

```
Find flights from JFK to LHR on 2026-10-15, find hotels in London for the
same dates (checkout 2026-10-20), then email a summary of both to
alex@example.com.
```

This chains all three servers in one turn:

1. `flight_search.search_flights(origin, destination, date)`
2. `booking_hotels.search_destinations(query)` → `booking_hotels.get_hotels(destination_id, checkin_date, checkout_date)`
3. `email_service.send_email(recipient, subject, body)`