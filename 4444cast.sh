#!/usr/bin/env bash

## Validate 'zip_code' parameter
if [[ "$1" == "" ]]; then

    ## Display usage if ZIP not provided
    echo "Usage:"
    echo "  $0 zip_code [limit]"
    exit 1

elif [[ "$1" =~ ^[0-9]{5}$ ]]; then

    ## Use provided ZIP code
    ZIP_CODE=$1

else

    ## Handle bad input
    echo "Invalid ZIP code provided. Provide a 5-digit ZIP code."
    exit 1

fi

## Check 'limit' parameter
if [[ "$2" != "" ]]; then LIMIT=$2; fi

## Check local ZIP cache
ZIP_CACHE=$(grep $ZIP_CODE .zip_cache 2> /dev/null)

if [[ "$ZIP_CACHE" != "" ]]; then

    ## Use locally cached coordinates
    echo "Using coordinates from local cache."
    LAT=$(echo $ZIP_CACHE | cut -d, -f2)
    LNG=$(echo $ZIP_CACHE | cut -d, -f3)

else

    ## Use Google Maps API for coordinates
    echo "Polling Google Maps API for coordinates."

    ## Import Google API key
    API_KEY=$(cat .google_api_key 2> /dev/null)
    if [[ $API_KEY == "" ]]; then

        echo "Google API key not imported. Create a '.google_api_key' file with your Google API key on a single line."
        exit 1

    fi

    ## Query Google Maps API for latitude/longitude of the provided ZIP code
    API_URL="https://maps.googleapis.com/maps/api/geocode/json?address=$ZIP_CODE&key=$API_KEY"
    API_RESPONSE=$(curl -s $API_URL)

    ## Get latitude and longitude by ZIP code
    LATLNG_JSON=$(jq -r ".results[].geometry.location" <<< $API_RESPONSE)
    LAT=$(jq -r ".lat" <<< $LATLNG_JSON)
    LNG=$(jq -r ".lng" <<< $LATLNG_JSON)

    ## Round lat/lng to 4 decimal places
    LAT=$(printf "%0.4f\n" $LAT)
    LNG=$(printf "%0.4f\n" $LNG)

    ## Cache results
    echo "$ZIP_CODE,$LAT,$LNG" >> .zip_cache

fi

## Query NWS API for forecast endpoint
NWS_API="https://api.weather.gov/points/$LAT,$LNG"
NWS_API_RESPONSE=$(curl -s $NWS_API)
NWS_FORECAST_API=$(jq -r ".properties.forecast" <<< $NWS_API_RESPONSE)

## Query NWS forecast endpoint
NWS_FORECAST_API_RESPONSE=$(curl -s $NWS_FORECAST_API)
PERIODS=$(jq -r '.["properties"].periods' <<< $NWS_FORECAST_API_RESPONSE)
PERIOD_COUNT=$(jq -r length <<< $PERIODS)

## Set weather icons
DEG_SYMBOL=$'\xc2\xb0'
ICON_CLOUDY=$'\xE2\x98\x81'
ICON_MOSTLY_CLEAR=$'\xF0\x9F\x8C\x99'
ICON_PARTLY_SUNNY=$'\xF0\x9F\x8C\xA4'
ICON_RAIN=$'\xF0\x9F\x8C\xA7'
ICON_SUNNY=$'\xF0\x9F\x8C\x9E'
ICON_THUNDERSTORM=$'\xE2\x9B\x88'

## Limit output if specified
if [ "$LIMIT" != "" ] && [ $PERIOD_COUNT -gt $LIMIT ]; then PERIOD_COUNT=$LIMIT; fi

## Iterate through weather forecast periods
for (( i=1; i<=$PERIOD_COUNT; i++ )); do

    ## Capture current conditions
    PERIOD_NAME=$(jq -r ".[] | select(.number==$i).name" <<< $PERIODS)
    PERIOD_FC_SHORT=$(jq -r ".[] | select(.number==$i).shortForecast" <<< $PERIODS)
    PERIOD_TEMP=$(jq -r ".[] | select(.number==$i).temperature" <<< $PERIODS)
    PERIOD_TEMP_UNIT=$(jq -r ".[] | select(.number==$i).temperatureUnit" <<< $PERIODS)

    ## Set weather emojis
    case $PERIOD_FC_SHORT in

        "Mostly Clear")
            PERIOD_FC_ICON=$ICON_MOSTLY_CLEAR
            ;;

        *"Cloudy"*)
            PERIOD_FC_ICON=$ICON_CLOUDY
            ;;

        "Partly Sunny")
            PERIOD_FC_ICON=$ICON_PARTLY_SUNNY
            ;;

        *"Rain"*)
            PERIOD_FC_ICON=$ICON_RAIN
            ;;

        "Sunny" | "Mostly Sunny")
            PERIOD_FC_ICON=$ICON_SUNNY
            ;;

        *"Thunderstorm"*)
            PERIOD_FC_ICON=$ICON_THUNDERSTORM
            ;;

        *)
            PERIOD_FC_ICON=""
            ;;

    esac

    ## Report conditions
    echo "$PERIOD_NAME: $PERIOD_FC_ICON $PERIOD_FC_SHORT $PERIOD_TEMP$DEG_SYMBOL$PERIOD_TEMP_UNIT"

done