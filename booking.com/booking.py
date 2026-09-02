import os
import httpx
from typing import Any, Dict, List, Optional
from mcp.server.fastmcp import FastMCP

# CONFIGURATION - set via env vars in claude_desktop_config.json
RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY")
RAPIDAPI_HOST = os.environ.get("RAPIDAPI_HOST", "booking-com15.p.rapidapi.com")

# Initialize MCP Server
mcp = FastMCP("Booking Hotels")

BASE_URL = f"https://{RAPIDAPI_HOST}/api/v1/hotels"
HEADERS = {
    "X-RapidAPI-Key": RAPIDAPI_KEY,
    "X-RapidAPI-Host": RAPIDAPI_HOST
}

@mcp.tool()
async def search_destinations(query: str) -> List[Dict[str, Any]]:
    """
    Search for destination IDs based on a city or location name (e.g., 'London').
    Returns a list of destinations with their IDs.
    """
    async with httpx.AsyncClient() as client:
        params = {"query": query}
        try:
            response = await client.get(
                f"{BASE_URL}/searchDestination",
                headers=HEADERS,
                params=params,
                timeout=30.0
            )
            response.raise_for_status()
            data = response.json()
            # Return the results list found in the 'data' key
            return data.get("data", [])
        except Exception as e:
            return [{"error": f"Failed to fetch destinations: {str(e)}"}]

@mcp.tool()
async def get_hotels(
    destination_id: str,
    checkin_date: str,
    checkout_date: str,
    adults: int = 2,
    room_number: int = 1,
    page_number: int = 1
) -> Dict[str, Any]:
    """
    Get hotel listings. 
    Dates must be YYYY-MM-DD. 
    Use search_destinations first to get the destination_id.
    """
    async with httpx.AsyncClient() as client:
        params = {
            "dest_id": destination_id,
            "search_type": "CITY",
            "arrival_date": checkin_date,
            "departure_date": checkout_date,
            "adults": adults,
            "room_qty": room_number,
            "page_number": page_number,
            "units": "metric",
            "temperature_unit": "c"
        }
        
        try:
            response = await client.get(
                f"{BASE_URL}/searchHotels",
                headers=HEADERS,
                params=params,
                timeout=60.0
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": f"Failed to fetch hotels: {str(e)}"}

if __name__ == "__main__":
    # Runs the server using the standard input/output (stdio) transport
    mcp.run()