#!/usr/bin/env python3
"""Get a weather forecast for a given zip code. Optionally, output the forecast to Discord with
    audio.

Usage:
    4444cast.py zip_code [limit] [--markdown] [--openai-api-key=API_KEY]
                         [--discord-webhook-urls=URLs]
    4444cast.py -h | --help

Arguments:
    zip_code                The zip code to get the weather forecast for
    limit                   The number of periods to display (1-20). There are two periods per day.
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
import requests

from openai import OpenAI, OpenAIError
from src.nws_weather_forecast import NwsWeatherForecast

# Other Configuration
WEBHOOK_NAME            = 'Barthur'
TTS_VOICE               = 'onyx'
TTS_SPEED               = 1.0
FORECAST_SCRIPT_SYSTEM_PROMPT = (
    "You will be provided with a weather forecast. Summarize the weather report, "
    "conversationally, in the voice of a grumpy old man doing his very best to play a weatherman. "
    "His grammar isn't that great, and he clears his throat nervously sometimes. You can condense "
    "each day's forecast; it does not have to be read out in full detail. Conclude your report "
    f"with 'And this was {WEBHOOK_NAME}, with the weather.' Throw in a lot of wordplay and "
    "colloquialisms. Do not include any scripted actions, as this will be used to create an audio "
    "recording. Say state names instead of their abbreviations, e.g. 'Texas' instead of 'TX'. "
    "Convert the '°' symbol to the word 'degrees', and F and C abbreviations to the words "
    "'fahrenheit' and 'celsius'."
)


def construct_output(
        zip_code        : str,
        limit           : int,
        use_markdown    : bool,
    ) -> str:
    """
    Builds the forecast text output.

    Args:
        zip_code (str): The zip code to get the forecast for
        limit (int): The number of periods to display
        use_markdown (bool): Whether to output in markdown format

    Returns:
        str: The formatted forecast text
    """

    print(f'Getting forecast for {zip_code}... ', file=sys.stderr)
    nws_payload     = NwsWeatherForecast(zip_code)
    city            = nws_payload.city
    state           = nws_payload.state
    radar_station   = nws_payload.radar_station
    header2         = '## ' if use_markdown else ''
    bold            = '**' if use_markdown else ''
    blockquote      = '>' if use_markdown else ' '

    output = f'{header2}Weather forecast for {city}, {state} ({radar_station}):\n\n'
    for i in range(limit):
        period          = nws_payload.forecast['response']['properties']['periods'][i]
        short_forecast  = period['shortForecast']
        weather_icon    = get_weather_icon(short_forecast)

        output += (
            f"{bold}{period['name']}:{bold}\n"
            f"{blockquote} {weather_icon} {period['temperature']}°F {short_forecast}\n"
            f"{blockquote} {period['detailedForecast']}\n\n"
        )

    return output


def generate_audio_file(
        forecast_audio_script   : str,
        openai_api_key          : str,
    ) -> str:
    """
    Generates the audio file for the forecast.

    Args:
        forecast_audio_script (str): The audio script to use for the forecast
        openai_api_key (str): The OpenAI API key

    Returns:
        str: The filename of the audio file
    """

    try:
        client = OpenAI(api_key=openai_api_key)
        response = client.audio.speech.create(
            input           = forecast_audio_script,
            model           = 'tts-1-hd',
            response_format = 'mp3',
            speed           = TTS_SPEED,
            voice           = TTS_VOICE,
        )

    except OpenAIError as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)

    today           = datetime.date.today().strftime('%Y-%m-%d')
    audio_filename  = f'{today} Weather Forecast.mp3'

    with open(audio_filename, 'wb') as audio_file:
        audio_file.write(response.read())

    return audio_filename


def generate_audio_script(
        forecast_text   : str,
        openai_api_key  : str,
    ) -> str:
    """
    Generates the text script for the forecast audio.
    
    Args:
        forecast_text (str): The forecast text to convert to audio
        openai_api_key (str): The OpenAI API key

    Returns:
        str: The audio script to use for the forecast
    """

    # Summarize forecast_text using gpt-3.5-turbo model
    try:
        client      = OpenAI(api_key=openai_api_key)
        response    = client.chat.completions.create(
            model   = 'gpt-3.5-turbo',
            messages=[
                {
                    'role':     'system',
                    'content':  FORECAST_SCRIPT_SYSTEM_PROMPT,
                },
                {
                    'role':     'user',
                    'content':  forecast_text,
                },
            ]
        )

    except OpenAIError as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)

    return response.choices[0].message.content


def get_command_line_args() -> dict[str, int, bool, str, str]:
    """
    Get the command line arguments.
    
    Returns:
        dict: The command line arguments
    """

    parser = argparse.ArgumentParser(description='Get the weather forecast for a given zip code')

    parser.add_argument(
        'zip_code',
        type    = str,
        help    = 'The zip code to get the weather forecast for',
    )

    parser.add_argument(
        '--limit', '-l',
        type    = int,
        default = 14,
        help    = (
            'The number of periods to display (1-20). There are two periods per day. Default '
            'value is 14.'
        ),
    )

    parser.add_argument(
        '--markdown', '-m',
        action  = 'store_true',
        help    = 'Output in markdown format',
    )

    parser.add_argument(
        '--openai-api-key', '-o',
        type    = str,
        help    = 'The OpenAI API key',
    )

    # A comma-separated list of webhook URLs
    parser.add_argument(
        '--discord-webhook-urls', '-d',
        type    = str,
        help    = 'The Discord webhook URL (supports multiple, comma-separated URLs)',
    )

    args = parser.parse_args()

    # Handle invalid arguments
    if args.limit < 1 or args.limit > 20:
        print('Error: Limit must be a value between 1-20.', file=sys.stderr)
        sys.exit(1)

    if bool(args.openai_api_key) and not bool(args.discord_webhook_urls):
        print('Error: OpenAI API key requires a Discord webhook URL.', file=sys.stderr)
        sys.exit(1)

    return {
        'zip_code'              : args.zip_code,
        'limit'                 : args.limit,
        'use_markdown'          : args.markdown,
        'openai_api_key'        : args.openai_api_key,
        'discord_webhook_urls'  :
            args.discord_webhook_urls.split(',') if args.discord_webhook_urls else [],
    }


def get_weather_icon(short_forecast: str) -> str:
    """
    Gets the weather icon for a given short forecast.

    Args:
        short_forecast (str): The short forecast to get the icon for

    Returns:
        str: The weather icon
    """

    icon_mapping = {
        'sunny':    '☀️',
        'clear':    '🌙',
        'cloudy':   '☁️',
        'rain':     '🌧️',
        'thunder':  '⛈️',
        't-storm':  '⛈️',
        'snow':     '❄️',
        'fog':      '🌫️',
    }

    forecast = short_forecast.lower()

    for keyword, icon in icon_mapping.items():
        if keyword in forecast:
            return icon

    return '❓'


def output_forecast(
        forecast_text           : str,
        openai_api_key          : str,
        discord_webhook_urls    : list[str],
    ) -> None:
    """
    Output the forecast to the console or send to Discord

    Args:
        forecast_text (str): The forecast text to output
        openai_api_key (str): The OpenAI API key
        discord_webhook_urls (list): The Discord webhook URLs
    """

    plural_webhooks             = 's' if len(discord_webhook_urls) > 1 else ''
    data_payload                = { 'content': forecast_text }

    if openai_api_key:
        print('Generating audio script... ', file=sys.stderr)
        forecast_audio_script   = generate_audio_script(forecast_text, openai_api_key)
        print(f'Audio script: {forecast_audio_script}', file=sys.stderr)

        print('Generating audio file... ', file=sys.stderr)
        audio_filename          = generate_audio_file(forecast_audio_script, openai_api_key)
        with open(audio_filename, 'rb') as audio_file:
            audio_content       = audio_file.read()
            audio_payload       = { 'file': (audio_filename, audio_content, 'audio/mp3') }

        print(f'Sending to Discord webhook{plural_webhooks}... ', file=sys.stderr)
        for discord_webhook_url in discord_webhook_urls:
            discord_response    = requests.post(
                discord_webhook_url,
                data            = data_payload,
                files           = audio_payload,
                timeout         = 5,
            )
            print(f'Discord response: {discord_response}', file=sys.stderr)

        # Clean up
        os.remove(audio_filename)

    elif discord_webhook_urls:
        # Send to Discord webhook without audio if no OpenAI API key is provided
        print(f'Sending to Discord webhook{plural_webhooks}... ', file=sys.stderr)
        for discord_webhook_url in discord_webhook_urls:
            discord_response    = requests.post(
                discord_webhook_url,
                data            = data_payload,
                timeout         = 5,
            )
            print(f'Discord response: {discord_response}', file=sys.stderr)

    else:
        # Output to console only
        print(forecast_text)


def main() -> None:
    """Main function."""

    try:
        options = get_command_line_args()

        forecast_text = construct_output(
            options['zip_code'],
            options['limit'],
            options['use_markdown'],
        )

        output_forecast(
            forecast_text,
            options['openai_api_key'],
            options['discord_webhook_urls'],
        )

    except KeyboardInterrupt:
        print('Error: Script execution cancelled.', file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
