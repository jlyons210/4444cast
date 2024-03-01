"""
Get a weather forecast for a given zip code.
"""

import os
import sys
from src.api_tools import ApiTools

class NwsWeatherForecast:
    """
    Get a weather forecast for a given zip code.

    Args:
        zip_code (str): The zip code to get the weather forecast for

    Attributes:
        zip_code (str): The zip code to get the weather forecast for
        forecast (dict): The weather forecast
        city (str): The city for the weather forecast
        state (str): The state for the weather forecast
        radar_station (str): The radar station for the weather forecast

    Returns:
        dict: The weather forecast
    """

    def __init__(self,
            zip_code: str,
        ):
        """
        Initializes the NwsWeatherForecast class.
        """

        self.zip_code       = zip_code
        self.forecast       = self._get_forecast_from_weather_api()
        self.city           = self.forecast['location']['city']
        self.state          = self.forecast['location']['state']
        self.radar_station  = self.forecast['location']['radar_station']

    def _cache_coordinates(
            self,
            coordinates         : dict[float, float],
            zip_cache_filename  : str,
        ) -> None:
        """
        Caches coordinates for a given zip code.

        Args:
            coordinates (dict): The coordinates to cache
            zip_cache_filename (str): The filename of the zip code cache
        """

        with open(zip_cache_filename, 'a', encoding='utf-8') as zip_cache:
            zip_cache.write(f'{self.zip_code},{coordinates["lat"]},{coordinates["lng"]}\n')


    def _get_coordinates(self) -> dict[float, float]:
        """
        Gets the coordinates for a given zip code from the cache or geo API.
        
        Returns:
            dict: The coordinates for the given zip code
        """

        zip_cache_filename = '.zip_cache'

        # Check local cache
        coordinates = self._get_coordinates_from_cache(zip_cache_filename)
        if coordinates:
            return coordinates

        else:
            coordinates = self._get_coordinates_from_geo_api()
            self._cache_coordinates(coordinates, zip_cache_filename)
            return coordinates


    def _get_coordinates_from_cache(
            self,
            zip_cache_filename: str,
        ) -> dict[float, float]:
        """
        Gets the ZIP code coordinates from the cache.
        
        Args:
            zip_cache_filename (str): The filename of the zip code cache

        Returns:
            dict: The coordinates for the given zip code
        """

        if os.path.exists(zip_cache_filename):
            with open(zip_cache_filename, 'r', encoding='utf-8') as zip_cache:
                for line in zip_cache:
                    if self.zip_code in line:
                        print('Using cached coordinates.', file=sys.stderr)
                        coordinates = line.split(',')

                        return {
                            'lat': float(coordinates[1]),
                            'lng': float(coordinates[2]),
                        }

        # Coordinates not cached
        return None


    def _get_coordinates_from_geo_api(
            self,
        ) -> dict[float, float]:
        """
        Gets the ZIP code coordinates from the geo API.

        Args:
            zip_code (str): The zip code to get the coordinates for

        Returns:
            dict: The coordinates for the given zip code
        """

        print('Getting coordinates from geo API.', file=sys.stderr)
        geo_api         = f'https://api.zippopotam.us/us/{self.zip_code}'
        geo_response    = ApiTools.call_with_retries(self, geo_api)

        coordinates = {
            'lat': geo_response['places'][0]['latitude'],
            'lng': geo_response['places'][0]['longitude'],
        }

        return coordinates


    def _get_forecast_from_weather_api(self) -> dict[str, dict]:
        """
        Gets the weather forecast for a given location from the NWS API.
        """

        # Get coordinates from geo API
        coordinates             = self._get_coordinates()
        lat                     = coordinates['lat']
        lng                     = coordinates['lng']

        # Get location from NWS API
        nws_location_api        = f'https://api.weather.gov/points/{lat},{lng}'
        nws_location_response   = ApiTools.call_with_retries(self, nws_location_api)
        location                = self._get_nws_location_info(nws_location_response)

        # Get forecast from NWS API
        nws_forecast_api        = nws_location_response['properties']['forecast']
        nws_forecast_response   = ApiTools.call_with_retries(self, nws_forecast_api)

        return {
            'location': location,
            'response': nws_forecast_response,
        }


    def _get_nws_location_info(
            self,
            nws_location_response: dict,
        ) -> dict[str, str, str]:
        """
        Gets the city, state, and radar_station for a provided NWS response.
        
        Args:
            nws_location_response (dict): The response from the NWS API

        Returns:
            dict: The location data
        """

        location_data   = nws_location_response['properties']['relativeLocation']['properties']
        city            = location_data['city']
        state           = location_data['state']
        radar_station   = nws_location_response['properties']['radarStation']

        return {
            'city'          : city,
            'state'         : state,
            'radar_station' : radar_station,
        }
