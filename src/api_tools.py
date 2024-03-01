"""
Utility functions for calling APIs.
"""

import sys
import requests
from requests.adapters import HTTPAdapter, Retry
from requests.exceptions import RequestException

API_MAX_RETRIES = 5
API_BACKOFF_FACTOR = 0.3

class ApiTools:
    """
    Utility functions for calling APIs.
    """

    def call_with_retries(
            self,
            url: str,
        ) -> dict:
        """
        Utility function for calling an API with retries.

        Args:
            url (str): The URL to call

        Returns:
            dict: The JSON response from the API
        """

        session = requests.Session()
        retry = Retry(
            total               = API_MAX_RETRIES,
            backoff_factor      = API_BACKOFF_FACTOR,
            status_forcelist    = [
                429,  # Too Many Requests
                500,  # Internal Server Error
                502,  # Bad Gateway
                503,  # Service Unavailable
                504,  # Gateway Timeout
            ]
        )

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
