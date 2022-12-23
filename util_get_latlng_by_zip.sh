#!/usr/bin/env bash

## Validate 'zip_code' parameter
if [[ "$1" == "" ]]; then

    ## Display usage if ZIP not provided
    echo "Usage:"
    echo "  $0 zip_code"
    exit 1

elif [[ "$1" =~ ^[0-9]{5}$ ]]; then

    ## Use provided ZIP code
    ZIP_CODE=$1

else

    ## Handle bad input
    echo "Invalid ZIP code provided. Provide a 5-digit ZIP code."
    exit 1

fi

## Import Google API key
API_KEY=$(cat google_api_key)

if [[ $API_KEY == "" ]]; then

    echo "Google API key not imported. Create a 'google_api_key' file with your Google API key on a single line."

fi

## Query Google Maps API for latitude/longitude of the provided ZIP code
API_URL="https://maps.googleapis.com/maps/api/geocode/json?address=$ZIP_CODE&key=$API_KEY"
API_RESPONSE=$(curl -s $API_URL)

## Return lat/lng
jq -r ".results[].geometry.location" <<< $API_RESPONSE