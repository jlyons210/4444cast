#!/usr/bin/env python3
"""Get a weather forecast for a given zip code. Optionally, output the forecast to Discord with
    audio.

Usage:
    4444cast.py zip_code [limit] [--markdown] [--openai-api-key=API_KEY] [--discord-webhook-url=URL]
    4444cast.py -h | --help

Arguments:
    zip_code            The zip code to get the weather forecast for
    limit               The number of periods to display (1-20). There are two periods per day.
                        Default value is 14.

Options:
    -h --help               Show this screen
    --markdown              Output in markdown format
    --openai-api-key        The OpenAI API key
    --discord-webhook-url   The Discord webhook URL
"""

import os
import sys
import argparse
import datetime

from openai import OpenAI, OpenAIError
import requests
from requests.exceptions import RequestException
from requests.adapters import HTTPAdapter, Retry


# Other Configuration
API_MAX_RETRIES = 5
API_BACKOFF_FACTOR = 0.3
WEBHOOK_NAME = 'Barthur'
TTS_VOICE = 'onyx'
TTS_SPEED = 1.0
FORECAST_SCRIPT_SYSTEM_PROMPT = (
    "You will be provided with a weather forecast. Summarize the weather report, "
    "conversationally, in the voice of a grumpy old man doing his very best to play a weatherman. "
    "His grammar isn't that great, and he clears his throat nervously sometimes. You can condense "
    "each day's forecast; it does not have to be read out in full detail. Conclude your report "
    f"with 'And this was {WEBHOOK_NAME}, with the weather.' Throw in a lot of wordplay and "
    "colloquialisms. Do not include any scripted actions, as this will be used to create an audio "
    "recording. Say state names instead of their abbreviations, e.g. 'Texas' instead of 'TX'."
)


def cache_coordinates(zip_code: str,
                      coordinates: dict[float, float],
                      zip_cache_filename: str) -> None:
    """Caches coordinates for a given zip code.

    Args:
        zip_code (str): The zip code to cache
        coordinates (dict): The coordinates to cache
        zip_cache_filename (str): The filename of the zip code cache
    """

    with open(zip_cache_filename, 'a', encoding='utf-8') as zip_cache:
        zip_cache.write(f'{zip_code},{coordinates["lat"]},{coordinates["lng"]}\n')


def call_retriable_api(url: str) -> dict:
    """Utility function for calling an API with retries.

    Args:
        url (str): The URL to call

    Returns:
        dict: The JSON response from the API
    """

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
    session.mount('http://', adapter)
    session.mount('https://', adapter)

    try:
        response = session.get(url, timeout=5)
        response.raise_for_status()
        return response.json()

    except RequestException as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)


def construct_output(zip_code: str, limit: int, markdown: bool) -> str:
    """Builds the forecast text output.

    Args:
        zip_code (str): The zip code to get the forecast for
        limit (int): The number of periods to display
        markdown (bool): Whether to output in markdown format

    Returns:
        str: The formatted forecast text
    """

    print(f'Getting forecast for {zip_code}... ', file=sys.stderr)
    forecast = get_forecast_from_weather_api(zip_code)

    city = forecast['location']['city']
    state = forecast['location']['state']
    radar_station = forecast['location']['radar_station']

    header2 = '## ' if markdown else ''
    bold = '**' if markdown else ''
    blockquote = '>' if markdown else ' '

    output = f'{header2}Weather forecast for {city}, {state} ({radar_station}):\n\n'

    for i in range(limit):
        period = forecast['response']['properties']['periods'][i]
        short_forecast = period['shortForecast']
        weather_icon = get_weather_icon(short_forecast)

        output += (
            f"{bold}{period['name']}:{bold}\n"
            f"{blockquote} {weather_icon} {period['temperature']}°F {short_forecast}\n"
            f"{blockquote} {period['detailedForecast']}\n\n"
        )

    return output


def generate_audio_script(forecast_text: str, openai_api_key: str) -> str:
    """Generates the text script for the forecast audio.
    
    Args:
        forecast_text (str): The forecast text to convert to audio
        openai_api_key (str): The OpenAI API key

    Returns:
        str: The audio script to use for the forecast
    """

    # Summarize forecast_text using gpt-3.5-turbo model
    try:
        client = OpenAI(api_key=openai_api_key)
        response = client.chat.completions.create(
            model='gpt-3.5-turbo',
            messages=[{
                'role': 'system',
                'content': FORECAST_SCRIPT_SYSTEM_PROMPT,
            },
            {
                'role': 'user',
                'content': forecast_text,
            }]
        )

    except OpenAIError as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)

    return response.choices[0].message.content


def generate_audio_file(forecast_audio_script: str, openai_api_key: str) -> str:
    """Generates the audio file for the forecast.

    Args:
        forecast_audio_script (str): The audio script to use for the forecast
        openai_api_key (str): The OpenAI API key

    Returns:
        str: The filename of the audio file
    """

    try:
        client = OpenAI(api_key=openai_api_key)
        response = client.audio.speech.create(
            input=forecast_audio_script,
            model='tts-1-hd',
            response_format='mp3',
            speed=TTS_SPEED,
            voice=TTS_VOICE,
        )

    except OpenAIError as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)

    # Save to file
    today = datetime.date.today().strftime('%Y-%m-%d')
    audio_filename = f'{today} Weather Forecast.mp3'
    with open(audio_filename, 'wb') as audio_file:
        audio_file.write(response.read())

    return audio_filename


def get_command_line_args() -> dict[str, int, bool, str, str]:
    """Get the command line arguments.
    
    Returns:
        dict: The command line arguments
    """

    parser = argparse.ArgumentParser(description='Get the weather forecast for a given zip code')

    parser.add_argument('zip_code',
                        type=str,
                        help='The zip code to get the weather forecast for')

    parser.add_argument('--limit', '-l',
                        type=int,
                        default=14,
                        help=('The number of periods to display (1-20). There are two periods per '
                              'day. Default value is 14.'))

    parser.add_argument('--markdown', '-m',
                        action='store_true',
                        help='Output in markdown format')

    parser.add_argument('--openai-api-key', '-o',
                        type=str,
                        help='The OpenAI API key')

    parser.add_argument('--discord-webhook-url', '-d',
                        type=str,
                        help='The Discord webhook URL')

    args = parser.parse_args()

    if args.limit < 1 or args.limit > 20:
        print('Error: Limit must be a value between 1-20.', file=sys.stderr)
        sys.exit(1)

    if bool(args.openai_api_key) and not bool(args.discord_webhook_url):
        print('Error: OpenAI API key requires a Discord webhook URL.', file=sys.stderr)
        sys.exit(1)

    return {
        'zip_code': args.zip_code,
        'limit': args.limit,
        'markdown': args.markdown,
        'openai_api_key': args.openai_api_key,
        'discord_webhook_url': args.discord_webhook_url,
    }


def get_coordinates(zip_code: str) -> dict[float, float]:
    """Gets the coordinates for a given zip code from the cache or geo API.
    
    Args:
        zip_code (str): The zip code to get the coordinates for

    Returns:
        dict: The coordinates for the given zip code
    """

    zip_cache_filename = '.zip_cache'

    # Check local cache
    coordinates = get_coordinates_from_cache(zip_code, zip_cache_filename)
    if coordinates:
        return coordinates

    else:
        coordinates = get_coordinates_from_geo_api(zip_code, zip_cache_filename)
        return coordinates


def get_coordinates_from_cache(zip_code: str, zip_cache_filename: str) -> dict[float, float]:
    """Gets the ZIP code coordinates from the cache.
    
    Args:
        zip_code (str): The zip code to get the coordinates for
        zip_cache_filename (str): The filename of the zip code cache

    Returns:
        dict: The coordinates for the given zip code
    """

    if os.path.exists(zip_cache_filename):
        with open(zip_cache_filename, 'r', encoding='utf-8') as zip_cache:
            for line in zip_cache:
                if zip_code in line:
                    print('Using cached coordinates.', file=sys.stderr)
                    coordinates = line.split(',')

                    return {
                        'lat': float(coordinates[1]),
                        'lng': float(coordinates[2]),
                    }

    # Coordinates not cached
    return None


def get_coordinates_from_geo_api(zip_code: str, zip_cache_filename: str) -> dict[float, float]:
    """Gets the ZIP code coordinates from the geo API.

    Args:
        zip_code (str): The zip code to get the coordinates for
        zip_cache_filename (str): The filename of the zip code cache

    Returns:
        dict: The coordinates for the given zip code
    """

    print('Getting coordinates from geo API.', file=sys.stderr)
    geo_api = f'https://api.zippopotam.us/us/{zip_code}'
    geo_response = call_retriable_api(geo_api)

    coordinates = {
        'lat': geo_response['places'][0]['latitude'],
        'lng': geo_response['places'][0]['longitude'],
    }

    cache_coordinates(zip_code, coordinates, zip_cache_filename)

    return coordinates


def get_forecast_from_weather_api(zip_code: str) -> dict[str, dict]:
    """Gets the weather forecast for a given location from the NWS API.

    Args:
        zip_code (str): The zip code to get the forecast for

    Returns:
        dict: The location and forecast data
    """

    # Get coordinates from geo API
    coordinates = get_coordinates(zip_code)

    # Get location from NWS API
    nws_location_api = f'https://api.weather.gov/points/{coordinates["lat"]},{coordinates["lng"]}'
    nws_location_response = call_retriable_api(nws_location_api)
    location = get_location(nws_location_response)

    # Get forecast from NWS API
    nws_forecast_api = nws_location_response['properties']['forecast']
    nws_forecast_response = call_retriable_api(nws_forecast_api)

    return {
        'location': location,
        'response': nws_forecast_response,
    }


def get_location(nws_location_response: dict) -> dict[str, str, str]:
    """Gets the city, state, and radar_station for a provided NWS response.
    
    Args:
        nws_location_response (dict): The response from the NWS API

    Returns:
        dict: The location data
    """

    location_data = nws_location_response['properties']['relativeLocation']['properties']
    city = location_data['city']
    state = location_data['state']
    radar_station = nws_location_response['properties']['radarStation']

    return {
        'city': city,
        'state': state,
        'radar_station': radar_station,
    }


def get_weather_icon(short_forecast: str) -> str:
    """Gets the weather icon for a given short forecast.

    Args:
        short_forecast (str): The short forecast to get the icon for

    Returns:
        str: The weather icon
    """

    icon_mapping = {
        'sunny': '☀️',
        'clear': '🌙',
        'cloudy': '☁️',
        'rain': '🌧️',
        'thunder': '⛈️',
        'snow': '❄️',
    }

    forecast = short_forecast.lower()

    for keyword, icon in icon_mapping.items():
        if keyword in forecast:
            return icon

    return '❓'


def output_forecast(forecast_text: str, openai_api_key: str, discord_webhook_url: str) -> None:
    """Output the forecast to the console or send to Discord

    Args:
        forecast_text (str): The forecast text to output
        openai_api_key (str): The OpenAI API key
        discord_webhook_url (str): The Discord webhook URL
    """

    if openai_api_key:
        # Generate audio script and file
        print('Generating audio script... ', file=sys.stderr)
        forecast_audio_script = generate_audio_script(forecast_text, openai_api_key)
        print('Generating audio file... ', file=sys.stderr)
        audio_filename = generate_audio_file(forecast_audio_script, openai_api_key)

        # Send to Discord webhook
        print('Sending to Discord webhook... ', file=sys.stderr)
        discord_response = requests.post(
            discord_webhook_url,
            data={
                'content': forecast_text,
            },
            files={
                'file': open(audio_filename, 'rb'),
            },
            timeout=5,
        )
        print(f'Discord response: {discord_response}', file=sys.stderr)

        # Clean up
        os.remove(audio_filename)

    elif discord_webhook_url:
        # Send to Discord webhook without audio if no OpenAI API key
        message_payload = {
            'content': forecast_text,
        }

        discord_response = requests.post(
            discord_webhook_url,
            json=message_payload,
            timeout=5,
        )
        print(f'Discord response: {discord_response}', file=sys.stderr)

    else:
        # Output to console only
        print(forecast_text)


def print_usage() -> None:
    """Print script usage."""

    print('Usage:', file=sys.stderr)
    print(f'  {sys.argv[0]} zip_code [limit]', file=sys.stderr)
    sys.exit(1)


def main() -> None:
    """Main function."""

    try:
        options = get_command_line_args()
        forecast_text = construct_output(options['zip_code'], options['limit'], options['markdown'])
        output_forecast(forecast_text, options['openai_api_key'], options['discord_webhook_url'])

    except KeyboardInterrupt:
        print('Error: Script execution cancelled.', file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
