import requests
from dotenv import load_dotenv
import os

load_dotenv()

def get_coordinates(address: str) -> dict:
    """Get the latitude and longitude of a given address using the OpenCage Geocoding API.

    Args:
        address (str): The address.

    Returns:
        dict: The latitude and longitude.
    """

    LOCATIONIQ_API_KEY = os.getenv("LOCATIONIQ_API_KEY")
    res = requests.get(f"https://us1.locationiq.com/v1/search?key={LOCATIONIQ_API_KEY}&q={address}&format=json&limit=1")

    if res.status_code != 200:
        raise Exception(f"Error: {res.status_code}")

    data = res.json()
    if not data:
        raise Exception(f"No results found for address: {address}")

    data = data[0]

    return {
        "latitude": float(data["lat"]),
        "longitude": float(data["lon"]),
        "display_name": data["display_name"],
    }

