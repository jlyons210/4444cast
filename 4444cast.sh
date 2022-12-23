#!/usr/bin/env bash

## Execution requires a five-digit ZIP code
if [[ "$1" == "" ]]; then

    ## Display usage if ZIP not provided
    echo "Usage:"
    echo "  $0 zip_code"
    exit 1

else

    ## Validate ZIP with regex
    if [[ "$1" =~ ^[0-9]{5}$ ]]; then

        ZIP_CODE=$1
    
    else

        echo "Invalid ZIP code provided. Provide a 5-digit ZIP code."
        exit 1

    fi

fi

## Get latitude and longitude by ZIP code
LATLNG_JSON=$(./util_get_latlng_by_zip.sh $ZIP_CODE)
LAT=$(jq -r ".lat" <<< $LATLNG_JSON)
LNG=$(jq -r ".lng" <<< $LATLNG_JSON)

## Round lat/lng to 4 decimal places
LAT=$(printf "%0.4f\n" $LAT)
LNG=$(printf "%0.4f\n" $LNG)

## Query NWS API for forecast endpoint
NWS_API="https://api.weather.gov/points/$LAT,$LNG"
NWS_API_RESPONSE=$(curl -s $NWS_API)
NWS_FORECAST_API=$(jq -r ".properties.forecast" <<< $NWS_API_RESPONSE)

## Query NWS forecast endpoint
NWS_FORECAST_API_RESPONSE=$(curl -s $NWS_FORECAST_API)
PERIODS=$(jq -r '.["properties"].periods[]' <<< $NWS_FORECAST_API_RESPONSE)
echo $PERIODS