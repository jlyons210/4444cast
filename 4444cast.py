#!/usr/bin/env python3
""" Get the weather forecast for a given zip code """

import os
import sys
import argparse
import datetime

from openai import OpenAI
import requests
from requests.exceptions import RequestException
from requests.adapters import HTTPAdapter, Retry


# Constants
API_MAX_RETRIES = 5
API_BACKOFF_FACTOR = 0.3


def cache_coordinates(zip_code, lat, lng, zip_cache_filename) -> None:
    """ Cache the coordinates for a given zip code """

    with open(zip_cache_filename, "a", encoding="utf-8") as zip_cache:
        zip_cache.write(f"{zip_code},{lat},{lng}\n")


def call_retriable_api(url) -> dict:
    """ Call an API with retries """

    session = requests.Session()
    retry = Retry(
        total=API_MAX_RETRIES,
        backoff_factor=API_BACKOFF_FACTOR,
        status_forcelist=[
            429,  # Too Many Requests
            500,  # Internal Server Error
            502,  # Bad Gateway
            503,  # Service Unavailable
            504,  # Gateway Timeout
        ])
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


def construct_forecast_text(location, forecast, limit, markdown) -> str:
    """ Print the forecast for a given period """

    if markdown:
        output = f"**__Weather forecast for {location[0]}, {location[1]} ({location[2]}):__**\n\n"
    else:
        output = f"Weather forecast for {location[0]}, {location[1]} ({location[2]}):\n\n"

    for i in range(limit):
        period = forecast['properties']['periods'][i]
        short_forecast = period['shortForecast']
        weather_icon = get_weather_icon(short_forecast)

        if markdown:
            output += f"**{period['name']}:**\n" \
                f"> {weather_icon} {period['temperature']}°F {short_forecast}\n" \
                f"> {period['detailedForecast']}\n\n"

        else:
            output += f"{period['name']}:\n" \
                f"  {weather_icon} {period['temperature']}°F {short_forecast}\n" \
                f"  {period['detailedForecast']}\n\n"

    return output


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


def get_command_line_args() -> tuple[str, int, bool, str, str]:
    """ Get the command line arguments """

    parser = argparse.ArgumentParser(description="Get the weather forecast for a given zip code")

    parser.add_argument("zip_code",
                        type=str,
                        help="The zip code to get the weather forecast for")

    parser.add_argument("--limit", "-l",
                        type=int,
                        default=14,
                        help="The number of periods to display. There are two periods per day.")

    parser.add_argument("--markdown", "-m",
                        action="store_true",
                        help="Output in markdown format")

    parser.add_argument("--openai-api-key", "-o",
                        type=str,
                        help="The OpenAI API key")

    parser.add_argument("--discord-webhook-url", "-d",
                        type=str,
                        help="The Discord webhook URL")

    args = parser.parse_args()

    if args.limit < 1:
        print("Error: Limit must be a positive integer.", file=sys.stderr)
        sys.exit(1)

    if bool(args.openai_api_key) ^ bool(args.discord_webhook_url):
        print("Error: OpenAI API key and Discord webhook URL must be provided together.",
              file=sys.stderr)
        sys.exit(1)

    return args.zip_code, args.limit, args.markdown, args.openai_api_key, args.discord_webhook_url


def get_coordinates_from_geo_api(zip_code) -> tuple[float, float]:
    """ Get the coordinates from the geocode API """

    print("Getting coordinates from geocode API.", file=sys.stderr)
    geo_api = f"https://api.zippopotam.us/us/{zip_code}"
    geo_response = call_retriable_api(geo_api)

    lat = geo_response["places"][0]["latitude"]
    lng = geo_response["places"][0]["longitude"]

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
        "snow": "❄️",
    }

    forecast = short_forecast.lower()

    for keyword, icon in icon_mapping.items():
        if keyword in forecast:
            return icon

    return "❓"


def get_zip_coordinates(zip_code) -> tuple[float, float]:
    """ Get the coordinates for a given zip code """

    zip_cache_filename = ".zip_cache"

    # Check local cache
    coords = get_cached_coordinates(zip_code, zip_cache_filename)
    if coords:
        return coords

    lat, lng = get_coordinates_from_geo_api(zip_code)

    # Cache coordinates
    cache_coordinates(zip_code, lat, lng, zip_cache_filename)

    return lat, lng


def output_forecast(forecast_text, openai_api_key, discord_webhook_url) -> None:
    """ Output the forecast to the console or send to Discord """

    if openai_api_key:
        client = OpenAI(api_key=openai_api_key)

        # Summarize forecast_text using gpt-3.5-turbo model
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content":
                        "You will be provided with a weather forecast. Summarize the weather " \
                        "report in the voice of a grumpy old man doing his very best to play " \
                        "a weatherman. His grammar isn't that great, and he clears his throat " \
                        "nervously sometimes. Conclude your report with 'And this was Barthur, " \
                        "with the weather.' Do not include any scripted actions, as this will " \
                        "be used to create an audio recording."
                },
                {
                    "role": "user",
                    "content": forecast_text
                },
            ],
        )
        forecast_audio_script = response.choices[0].message.content

        # Send to OpenAI Whisper API, using 'nova' voice
        response = client.audio.speech.create(
            input=forecast_audio_script,
            model="tts-1-hd",
            response_format="mp3",
            speed=0.8,
            voice="onyx",
        )

        # Save to file
        today = datetime.date.today().strftime("%Y-%m-%d")
        audio_filename = f"{today} Weather Forecast.mp3"
        response.stream_to_file(audio_filename)

        # Send to Discord, using multipart/form-data
        message_payload = { "content": forecast_text }
        file_payload = { "file": open(audio_filename, "rb") }

        discord_response = requests.post(
            discord_webhook_url,
            data=message_payload,
            files=file_payload,
            timeout=5,
        )
        print(f"Discord response:\n{discord_response}", file=sys.stderr)

        # Clean up
        os.remove(audio_filename)

    else:
        print(forecast_text)


def print_usage() -> None:
    """ Print script usage """

    print("Usage:", file=sys.stderr)
    print(f"  {sys.argv[0]} zip_code [limit]", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    """ Main function """

    zip_code, limit, markdown, openai_api_key, discord_webook_url = get_command_line_args()
    lat, lng = get_zip_coordinates(zip_code)
    location, forecast = get_forecast_from_nws_api(lat, lng)
    forecast_text = construct_forecast_text(location, forecast, limit, markdown)
    output_forecast(forecast_text, openai_api_key, discord_webook_url)


if __name__ == "__main__":
    main()
