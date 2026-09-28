import sys
import re
from datetime import datetime
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from fast_flights import FlightData, Passengers, get_flights

# Shared security controls, tagged [SC-xx]; see the control table in SECURITY.md
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))
import agent_guard as guard  # noqa: E402
from agent_guard import GuardError  # noqa: E402

SERVER = "flight_search"

# Initialize FastMCP server
mcp = FastMCP("Google Flights")

# [SC-05] Tool risk annotations: read-only, safe for clients to auto-approve (SC-07)
READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False,
                            idempotentHint=True, openWorldHint=True)


# [SC-04] Input validation helpers
def validate_iata(code: str) -> bool:
    """Validates if the code is a 3-letter IATA airport code."""
    return bool(re.fullmatch(r"[A-Z]{3}", code.upper()))

def validate_date(date_str: str) -> bool:
    """Validates if the date is in YYYY-MM-DD format and not in the past."""
    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        return date_obj.date() >= datetime.now().date()
    except ValueError:
        return False

@mcp.tool(annotations=READ_ONLY)
def search_flights(origin: str, destination: str, date: str) -> str:
    """
    Search for real-time flight prices and details on Google Flights.

    Args:
        origin: 3-letter IATA airport code (e.g., 'SFO', 'LHR')
        destination: 3-letter IATA airport code (e.g., 'LAX', 'JFK')
        date: Departure date in YYYY-MM-DD format
    """
    args = {"origin": origin, "destination": destination, "date": date}

    # 1. Security pre-checks and input validation
    try:
        # [SC-18] kill switch, [SC-19] rate limit
        rl = guard.load_policy().get("rate_limits", {}).get(SERVER, {})
        guard.guarded(SERVER, "search_flights", args,
                      (rl.get("max_calls", 10), rl.get("per_seconds", 60)))
        # [SC-04] Input validation
        if not validate_iata(origin) or not validate_iata(destination):
            raise GuardError("Invalid airport code. Please use 3-letter IATA codes (e.g., SFO).")
        if not validate_date(date):
            raise GuardError("Invalid date format. Use YYYY-MM-DD and ensure the date is not in the past.")
    except GuardError as e:
        guard.audit(SERVER, "search_flights", args, "blocked", str(e))  # [SC-15]
        return f"Blocked: {e}"

    print(f"Fetching flights from {origin} to {destination} on {date}...", file=sys.stderr)

    try:
        # 2. Fetch Data
        # Note: fast-flights v2.x uses get_flights
        result = get_flights(
            flight_data=[FlightData(date=date, from_airport=origin.upper(), to_airport=destination.upper())],
            trip="one-way",
            seat="economy",
            passengers=Passengers(adults=1, children=0, infants_in_seat=0, infants_on_lap=0),
            fetch_mode="fallback"  # Helps bypass some scraping blocks
        )
    except Exception as e:
        return guard.safe_error(SERVER, "search_flights", args, e)  # [SC-14]

    # 3. Handle Empty Results
    if not result or not result.flights:
        guard.audit(SERVER, "search_flights", args, "ok", "0 results")  # [SC-15]
        return f"No flights found for {origin} to {destination} on {date}. Try a different date or nearby airports."

    # 4. Format output. [SC-09] scraped fields are truncated and stripped of
    #    hidden characters; [SC-10] each is filtered for prompt injection
    src = "google_flights"
    output = [f"### Flights from {origin.upper()} to {destination.upper()} ({date})",
              f"**Current Price Level:** {guard.clean_field(result.current_price or 'Unknown', src, 20)}\n",
              "| Airline | Departure | Arrival | Duration | Stops | Price |",
              "|---------|-----------|---------|----------|-------|-------|"]

    # [SC-09] Limit to top 10 results
    for f in result.flights[:10]:
        stops = "Nonstop" if f.stops == 0 else f"{f.stops} stop(s)"
        output.append("| {} | {} | {} | {} | {} | {} |".format(
            guard.clean_field(f.name, src, 80),
            guard.clean_field(f.departure, src, 40),
            guard.clean_field(f.arrival, src, 40),
            guard.clean_field(f.duration, src, 20),
            stops,
            guard.clean_field(f.price or "N/A", src, 20),
        ))

    guard.audit(SERVER, "search_flights", args, "ok", f"{min(len(result.flights), 10)} results")  # [SC-15]
    return guard.wrap_untrusted("\n".join(output), src)  # [SC-11] fenced as untrusted data

if __name__ == "__main__":
    mcp.run()
