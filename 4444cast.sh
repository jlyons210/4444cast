#!/usr/bin/env bash

## Validate ZIP with regex
if [[ "$1" == "" ]]; then

    ## Display usage if ZIP not provided
    echo "Usage:"
    echo "  $0 zip_code [limit]"
    exit 1

elif [[ "$1" =~ ^[0-9]{5}$ ]]; then

    ZIP_CODE=$1

else

    echo "Invalid ZIP code provided. Provide a 5-digit ZIP code."
    exit 1

fi

## Support 'limit' parameter
if [[ "$2" != "" ]]; then LIMIT=$2; fi

## Check local ZIP cache
ZIP_CACHE=$(grep $ZIP_CODE zip_cache 2> /dev/null)

if [[ "$ZIP_CACHE" != "" ]]; then

    echo "Using coordinates from local cache."
    LAT=$(echo $ZIP_CACHE | cut -d, -f2)
    LNG=$(echo $ZIP_CACHE | cut -d, -f3)

else

    echo "Polling Google Maps API for coordinates."

    ## Get latitude and longitude by ZIP code
    LATLNG_JSON=$(./util_get_latlng_by_zip.sh $ZIP_CODE)
    LAT=$(jq -r ".lat" <<< $LATLNG_JSON)
    LNG=$(jq -r ".lng" <<< $LATLNG_JSON)

    ## Round lat/lng to 4 decimal places
    LAT=$(printf "%0.4f\n" $LAT)
    LNG=$(printf "%0.4f\n" $LNG)

    ## Cache lookup
    echo "$ZIP_CODE,$LAT,$LNG" >> zip_cache

fi

## Query NWS API for forecast endpoint
NWS_API="https://api.weather.gov/points/$LAT,$LNG"
NWS_API_RESPONSE=$(curl -s $NWS_API)
NWS_FORECAST_API=$(jq -r ".properties.forecast" <<< $NWS_API_RESPONSE)

## Query NWS forecast endpoint
NWS_FORECAST_API_RESPONSE=$(curl -s $NWS_FORECAST_API)
PERIODS=$(jq -r '.["properties"].periods' <<< $NWS_FORECAST_API_RESPONSE)
PERIOD_COUNT=$(jq -r length <<< $PERIODS)


## Limit output if specified
if [ "$LIMIT" != "" ] && [ $PERIOD_COUNT -gt $LIMIT ]; then PERIOD_COUNT=$LIMIT; fi

## Set constants
DEG_SYMBOL=$'\xc2\xb0'
ICON_CLOUDY=$'\xE2\x98\x81'
ICON_MOSTLY_CLEAR=$'\xF0\x9F\x8C\x99'
ICON_PARTLY_SUNNY=$'\xF0\x9F\x8C\xA4'
ICON_RAIN=$'\xF0\x9F\x8C\xA7'
ICON_SUNNY=$'\xF0\x9F\x8C\x9E'

for (( i=1; i<=$PERIOD_COUNT; i++ ))
do

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

        "Sunny")
            PERIOD_FC_ICON=$ICON_SUNNY
            ;;

        *)
            PERIOD_FC_ICON=""
            ;;

    esac

    ## Report conditions
    echo "$PERIOD_NAME: $PERIOD_FC_ICON $PERIOD_FC_SHORT $PERIOD_TEMP$DEG_SYMBOL$PERIOD_TEMP_UNIT"

done