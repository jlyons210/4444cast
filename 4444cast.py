#!/usr/bin/env python3
""" Get the weather forecast for a given zip code """

import os
import sys
import requests
from requests.exceptions import RequestException
from requests.adapters import HTTPAdapter, Retry


def cache_coordinates(zip_code, lat, lng, zip_cache_filename):
    """ Cache the coordinates for a given zip code """

    with open(zip_cache_filename, "a", encoding="utf-8") as zip_cache:
        zip_cache.write(f"{zip_code},{lat},{lng}\n")


def call_retriable_api(url, retries=3, backoff_factor=0.3):
    """ Call an API with retries """

    session = requests.Session()
    retry = Retry(total=retries, backoff_factor=backoff_factor)
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    try:
        response = session.get(url, timeout=5)
        response.raise_for_status()
        return response.json()

    except RequestException as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def get_cached_coordinates(zip_code, zip_cache_filename) -> tuple[float, float]:
    """ Get the coordinates from the local cache """

    if os.path.exists(zip_cache_filename):
        with open(zip_cache_filename, "r", encoding="utf-8") as zip_cache:
            for line in zip_cache:
                if zip_code in line:
                    print("Using cached coordinates.", file=sys.stderr)
                    coords = line.split(",")
                    return float(coords[1]), float(coords[2])

    # Coordinates not cached
    return None


def get_command_line_args() -> tuple[str, int]:
    """ Get the command line arguments """

    if len(sys.argv) == 1:
        print_usage()

    zip_code = sys.argv[1] if len(sys.argv) >= 2 else None
    limit = int(sys.argv[2]) if len(sys.argv) >= 3 else 14

    return zip_code, limit


def get_coordinates_from_maps_api(zip_code, api_key):
    """ Get the coordinates from the Google Maps API """

    # Get coordinates from Google Maps API
    maps_api = f"https://maps.googleapis.com/maps/api/geocode/json?address={zip_code}&key={api_key}"
    maps_response = requests.get(maps_api, timeout=5).json()

    if maps_response["status"] != "OK":
        handle_google_api_error(maps_response)

    lat = round(maps_response["results"][0]["geometry"]["location"]["lat"], 4)
    lng = round(maps_response["results"][0]["geometry"]["location"]["lng"], 4)

    return lat, lng


def get_forecast_from_nws_api(lat, lng) -> None:
    """ Get the weather forecast for a given location """

    # Get location from NWS API
    nws_location_api = f"https://api.weather.gov/points/{lat},{lng}"
    nws_location_response = call_retriable_api(nws_location_api)
    location = get_location(nws_location_response)

    # Get forecast from NWS API
    nws_forecast_api = nws_location_response['properties']['forecast']
    nws_forecast_response = call_retriable_api(nws_forecast_api)

    return location, nws_forecast_response


def get_google_api_key(google_api_key_filename):
    """ Get the Google Maps API key """

    try:
        with open(google_api_key_filename, "r", encoding="utf-8") as api_key_file:
            return api_key_file.read().strip()

    except FileNotFoundError:
        print("No Google Maps API key found.", file=sys.stderr)
        sys.exit(1)


def get_location(nws_location_response) -> tuple[str, str, str]:
    """ Get the location for a given response """

    location_data = nws_location_response['properties']['relativeLocation']['properties']
    city = location_data['city']
    state = location_data['state']
    radar_station = nws_location_response['properties']['radarStation']

    return city, state, radar_station


def get_weather_icon(short_forecast) -> str:
    """ Get the weather icon for a given forecast """

    icon_mapping = {
        "sunny": "☀️",
        "clear": "🌙",
        "cloudy": "☁️",
        "rain": "🌧️",
        "thunder": "⛈️",
        "snow": "❄️"
    }

    forecast = short_forecast.lower()

    for keyword, icon in icon_mapping.items():
        if keyword in forecast:
            return icon

    return "❓"


def get_zip_coordinates(zip_code) -> tuple[float, float]:
    """ Get the coordinates for a given zip code """

    google_api_key_filename = ".google_api_key"
    zip_cache_filename = ".zip_cache"

    # Check local cache
    coords = get_cached_coordinates(zip_code, zip_cache_filename)
    if coords:
        return coords

    # Get coordinates from Google Maps API
    api_key = get_google_api_key(google_api_key_filename)
    lat, lng = get_coordinates_from_maps_api(zip_code, api_key)

    # Cache coordinates
    cache_coordinates(zip_code, lat, lng, zip_cache_filename)

    return lat, lng


def handle_google_api_error(response_json):
    """ Handle API errors """

    print(f"Error: {response_json['status']}", file=sys.stderr)

    if response_json["status"] == "REQUEST_DENIED":
        print("Request denied. Check your API key.", file=sys.stderr)

    sys.exit(1)


def print_forecast(location, forecast, limit) -> None:
    """ Print the forecast for a given period """

    print(f"Weather forecast for {location[0]}, {location[1]} ({location[2]}):\n")

    for i in range(limit):
        period = forecast['properties']['periods'][i]
        short_forecast = period['shortForecast']
        weather_icon = get_weather_icon(short_forecast)

        print(f"**__{period['name']}:__**")
        print(f"{weather_icon} {short_forecast} {period['temperature']}°F")
        print(f">{period['detailedForecast']}\n")


def print_usage() -> None:
    """ Print script usage """

    print("Usage:", file=sys.stderr)
    print(f"  {sys.argv[0]} zip_code [limit]", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    """ Main function """

    zip_code, limit = get_command_line_args()
    lat, lng = get_zip_coordinates(zip_code)
    location, forecast = get_forecast_from_nws_api(lat, lng)
    print_forecast(location, forecast, limit)


if __name__ == "__main__":
    main()
