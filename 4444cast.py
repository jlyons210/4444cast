#!/usr/bin/env python3

import sys, os
import requests

def get_command_line_args():
    """ Get the command line arguments """

    # Set defaults
    limit = 14

    if len(sys.argv) == 1:
        print_usage()

    if len(sys.argv) >= 2:
        zip_code = sys.argv[1]
    
    if len(sys.argv) >= 3:
        limit = int(sys.argv[2])
    
    return zip_code, limit

def print_usage():
    """ Print script usage """

    print("Usage:", file=sys.stderr)
    print(f"  {sys.argv[0]} zip_code [limit]", file=sys.stderr)
    sys.exit(1)

def get_zip_coordinates(zip_code):
    """ Get the coordinates for a given zip code """

    # Check local cache
    if os.path.exists(".zip_cache"):
        with open(".zip_cache", "r") as cache_file:
            for line in cache_file:
                if zip_code in line:
                    print("Using cached coordinates.", file=sys.stderr)
                    return float(line.split(",")[1]), float(line.split(",")[2])

    # Get coordinates from Google Maps API
    try:
        print("Using Google Maps API to get coordinates.", file=sys.stderr)
        with open(".google_api_key", "r") as api_key_file:
            api_key = api_key_file.read().strip()
    except FileNotFoundError:
        print("No Google Maps API key found.", file=sys.stderr)
        sys.exit(1)

    url = f"https://maps.googleapis.com/maps/api/geocode/json?address={zip_code}&key={api_key}"
    response_json = requests.get(url).json()

    lat = round(response_json["results"][0]["geometry"]["location"]["lat"], 4)
    lng = round(response_json["results"][0]["geometry"]["location"]["lng"], 4)

    # Cache coordinates
    with open(".zip_cache", "a") as cache_file:
        cache_file.write(f"{zip_code},{lat},{lng}\n")

    return lat, lng

# Query NWS API for forecast
def get_forecast(lat, lng, limit):
    """ Get the weather forecast for a given location """

    nws_location_endpoint = f"https://api.weather.gov/points/{lat},{lng}"
    nws_location_response = requests.get(nws_location_endpoint).json()
    location = f"{nws_location_response['properties']['relativeLocation']['properties']['city']}, {nws_location_response['properties']['relativeLocation']['properties']['state']}"

    nws_forecast_endpoint = nws_location_response['properties']['forecast']
    nws_forecast_response = requests.get(nws_forecast_endpoint).json()

    print(f"Weather forecast for {location}:")
    for i in range(limit):
        weather_icon = get_weather_icon(nws_forecast_response['properties']['periods'][i]['shortForecast'])
        print(f"{nws_forecast_response['properties']['periods'][i]['name']}: {weather_icon} {nws_forecast_response['properties']['periods'][i]['detailedForecast']}", file=sys.stdout)

def get_weather_icon(short_forecast):
    """ Get the weather icon for a given forecast """

    if "sunny" in short_forecast.lower():
        return "☀️"
    elif "clear" in short_forecast.lower():
        return "🌙"
    elif "cloudy" in short_forecast.lower():
        return "☁️"
    elif "rain" in short_forecast.lower():
        return "🌧️"
    elif "thunder" in short_forecast.lower():
        return "⛈️"
    elif "snow" in short_forecast.lower():
        return "❄️"
    else:
        return "❓"

def main():
    """ Main function """

    zip_code, limit = get_command_line_args()
    lat, lng = get_zip_coordinates(zip_code)
    get_forecast(lat, lng, limit)

if __name__ == "__main__":
    main()
