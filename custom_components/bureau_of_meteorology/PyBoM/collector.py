"""BOM data 'collector' that downloads the observation data."""
import asyncio
import datetime
import aiohttp
import logging

from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = datetime.timedelta(minutes=10)
DAILY_FORECASTS_URL = "https://api.weather.bom.gov.au/v1/locations/{}/forecasts/daily"
LOCATIONS_URL = "https://api.weather.bom.gov.au/v1/locations/{}"
MDI_ICON_MAP = {
    'clear': 'mdi:weather-night',
    'cloudy': 'mdi:weather-cloudy',
    'cyclone': 'mdi:weather-hurricane',
    'dust': 'mdi:weather-hazy',
    'dusty': 'mdi:weather-hazy',
    'fog': 'mdi:weather-fog',
    'frost': 'mdi:snowflake-melt',
    'haze': 'mdi:weather-hazy',
    'hazy': 'mdi:weather-hazy',
    'heavy_shower': 'mdi:weather-pouring',
    'heavy_showers': 'mdi:weather-pouring',
    'light_rain': 'mdi:weather-partly-rainy',
    'light_shower': 'mdi:weather-light-showers',
    'light_showers': 'mdi:weather-light-showers',
    "mostly_sunny": "mdi:weather-sunny",
    'partly_cloudy': 'mdi:weather-partly-cloudy',
    'rain': 'mdi:weather-pouring',
    'shower': 'mdi:weather-rainy',
    'showers': 'mdi:weather-rainy',
    'snow': 'mdi:weather-snowy',
    'storm': 'mdi:weather-lightning-rainy',
    'storms': 'mdi:weather-lightning-rainy',
    'sunny': 'mdi:weather-sunny',
    'tropical_cyclone': 'mdi:weather-hurricane',
    'wind': 'mdi:weather-windy',
    'windy': 'mdi:weather-windy',
}
OBSERVATIONS_URL = "https://api.weather.bom.gov.au/v1/locations/{}/observations"


class Collector:
    """Data collector for BOM integration."""

    def __init__(self, latitude, longitude):
        """Init BOM data collector."""
        self.observations_data = None
        self.daily_forecasts_data = None
        self.geohash = self.geohash_encode(latitude, longitude)
        _LOGGER.debug(f"geohash: {self.geohash}")

    async def get_location_name(self):
        """Get JSON location name from BOM API endpoint."""
        url = LOCATIONS_URL.format(self.geohash)

        async with aiohttp.ClientSession() as session:
            response = await session.get(url)

        if response is not None and response.status == 200:
            locations_data = await response.json()
            self.location_name = locations_data["data"]["name"]
            return True

    async def get_observations_data(self):
        """Get JSON observations data from BOM API endpoint."""
        url = OBSERVATIONS_URL.format(self.geohash)

        async with aiohttp.ClientSession() as session:
            response = await session.get(url)

        if response is not None and response.status == 200:
            self.observations_data = await response.json()
            await self.flatten_observations_data()

    async def flatten_observations_data(self):
        """Flatten out wind and gust data."""
        flattened = {}

        wind = self.observations_data["data"]["wind"]
        flattened["wind_speed_kilometre"] = wind["speed_kilometre"]
        flattened["wind_speed_knot"] = wind["speed_knot"]
        flattened["wind_direction"] = wind["direction"]

        if self.observations_data["data"]["gust"] is not None:
            gust = self.observations_data["data"]["gust"]
            flattened["gust_speed_kilometre"] = gust["speed_kilometre"]
            flattened["gust_speed_knot"] = gust["speed_knot"]
        else:
            flattened["gust_speed_kilometre"] = None
            flattened["gust_speed_knot"] = None

        self.observations_data["data"].update(flattened)


    async def get_daily_forecasts_data(self):
        """Get JSON daily forecasts data from BOM API endpoint."""
        url = DAILY_FORECASTS_URL.format(self.geohash)

        async with aiohttp.ClientSession() as session:
            response = await session.get(url)

        if response is not None and response.status == 200:
            self.daily_forecasts_data = await response.json()
            await self.flatten_forecast_data()

    async def flatten_forecast_data(self):
        """Flatten out forecast data."""
        flattened = {}
        for day in range(0, 6):
            icon = self.daily_forecasts_data["data"][day]["icon_descriptor"]
            flattened["mdi_icon"] = MDI_ICON_MAP[icon]

            uv = self.daily_forecasts_data["data"][day]["uv"]
            flattened["uv_category"] = uv["category"]
            flattened["uv_max_index"] = uv["max_index"]
            flattened["uv_start_time"] = uv["start_time"]
            flattened["uv_end_time"] = uv["end_time"]

            rain = self.daily_forecasts_data["data"][day]["rain"]
            flattened["rain_amount_min"] = rain["amount"]["min"]
            flattened["rain_amount_max"] = rain["amount"]["max"]
            flattened["rain_chance"] = rain["chance"]

            self.daily_forecasts_data["data"][day].update(flattened)

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self):
        """Refresh the data on the collector object."""
        await self.get_observations_data()
        await self.get_daily_forecasts_data()

    def geohash_encode(self, latitude, longitude, precision=6):
        base32 = '0123456789bcdefghjkmnpqrstuvwxyz'
        lat_interval = (-90.0, 90.0)
        lon_interval = (-180.0, 180.0)
        geohash = []
        bits = [16, 8, 4, 2, 1]
        bit = 0
        ch = 0
        even = True
        while len(geohash) < precision:
            if even:
                mid = (lon_interval[0] + lon_interval[1]) / 2
                if longitude > mid:
                    ch |= bits[bit]
                    lon_interval = (mid, lon_interval[1])
                else:
                    lon_interval = (lon_interval[0], mid)
            else:
                mid = (lat_interval[0] + lat_interval[1]) / 2
                if latitude > mid:
                    ch |= bits[bit]
                    lat_interval = (mid, lat_interval[1])
                else:
                    lat_interval = (lat_interval[0], mid)
            even = not even
            if bit < 4:
                bit += 1
            else:
                geohash += base32[ch]
                bit = 0
                ch = 0
        return ''.join(geohash)