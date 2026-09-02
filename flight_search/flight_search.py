import sys
import re
from datetime import datetime
from typing import List, Optional
from mcp.server.fastmcp import FastMCP
from fast_flights import FlightData, Passengers, get_flights

# Initialize FastMCP server
mcp = FastMCP("Google Flights")

def validate_iata(code: str) -> bool:
    """Validates if the code is a 3-letter IATA airport code."""
    return bool(re.match(r"^[A-Z]{3}$", code.upper()))

def validate_date(date_str: str) -> bool:
    """Validates if the date is in YYYY-MM-DD format and not in the past."""
    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        return date_obj.date() >= datetime.now().date()
    except ValueError:
        return False

@mcp.tool()
def search_flights(origin: str, destination: str, date: str) -> str:
    """
    Search for real-time flight prices and details on Google Flights.
    
    Args:
        origin: 3-letter IATA airport code (e.g., 'SFO', 'LHR')
        destination: 3-letter IATA airport code (e.g., 'LAX', 'JFK')
        date: Departure date in YYYY-MM-DD format
    """
    # 1. Input Validation
    if not validate_iata(origin) or not validate_iata(destination):
        return "Error: Invalid airport code. Please use 3-letter IATA codes (e.g., SFO)."
    
    if not validate_date(date):
        return "Error: Invalid date format. Use YYYY-MM-DD and ensure the date is not in the past."

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

        # 3. Handle Empty Results
        if not result or not result.flights:
            return f"No flights found for {origin} to {destination} on {date}. Try a different date or nearby airports."

        # 4. Format Successful Output
        output = [f"### Flights from {origin} to {destination} ({date})",
                  f"**Current Price Level:** {result.current_price or 'Unknown'}\n"]
        
        output.append("| Airline | Departure | Arrival | Duration | Stops | Price |")
        output.append("|---------|-----------|---------|----------|-------|-------|")
        
        # Limit to top 10 results for context efficiency
        for f in result.flights[:10]:
            stops = "Nonstop" if f.stops == 0 else f"{f.stops} stop(s)"
            price = f.price if f.price else "N/A"
            output.append(f"| {f.name} | {f.departure} | {f.arrival} | {f.duration} | {stops} | {price} |")

        return "\n".join(output)

    except Exception as e:
        # 5. Robust Error Logging
        print(f"CRITICAL ERROR: {str(e)}", file=sys.stderr)
        return f"An error occurred while fetching flights: {str(e)}. Please try again in a few minutes."

if __name__ == "__main__":
    mcp.run()