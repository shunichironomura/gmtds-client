import asyncio
import logging
import urllib.parse
from itertools import product

import aiohttp
import tqdm.asyncio

logger = logging.getLogger(__name__)


def build_url(
    base: str = "https://gmtds.maplarge.com/ogc/ais:density/wms",
    **kwargs: str,
) -> str:
    return base + "?" + urllib.parse.urlencode(kwargs)


async def fetch_ais_density(
    session: aiohttp.ClientSession,
    bbox: str,
    width: int,
    height: int,
    i: int,
    j: int,
    time: str,
) -> float:
    # # -179 <= lon < -178 -> i = 0
    # # ...
    # # 179 <= lon < 180 -> i = 358
    # lon = (lon + 180) % 360 - 180
    # # Because the data for -180 < lon < -179 is erroneous, we use the neighboring value.
    # if -180.0 <= lon < -179.5:
    #     lon = 180.0
    # elif -179.5 <= lon < -179:
    #     lon = -179.0
    # i = floor(lon + 179)
    # assert 0 <= i <= 358, f"i = {i} is out of bounds"

    # lat = (lat + 90) % 180 - 90
    # lat = 90.0 if lat == -90.0 else lat
    # j = floor(90 - lat)
    # assert 0 <= j <= 179, f"j = {j} is out of bounds"
    url = build_url(
        SERVICE="WMS",
        VERSION="1.3.0",
        REQUEST="GetFeatureInfo",
        BBOX=bbox,
        CRS="EPSG:4326",
        WIDTH=str(width),
        HEIGHT=str(height),
        LAYERS="ais:density",
        FORMAT="image/png",
        TRANSPARENT="TRUE",
        time=time,
        CQL_FILTER="category_column='Loitering' AND category='NonLoitering'",
        query_layers="ais:density",
        info_format="application/vnd.geo+json",
        feature_count="1",
        i=str(i),
        j=str(j),
    )
    logger.info(f"Fetching data for i={i}, j={j}")
    async with session.get(url) as response:
        data = await response.json()
        logger.info(f"Data for i={i}, j={j} fetched")
        try:
            return float(data["features"][0]["properties"]["DEFAULT"])
        except IndexError:
            logger.info(f"No data for i={i}, j={j}")
            return float("nan")
        except KeyError:
            logger.info(f"No data for i={i}, j={j}")
            return float("nan")


async def fetch_ais_density_grid(
    longitude_range: tuple[float, float],
    latitude_range: tuple[float, float],
    n_longitudes: int,
    n_latitudes: int,
    time: str,
) -> list[float]:
    bbox = f"{latitude_range[0]},{longitude_range[0]},{latitude_range[1]},{longitude_range[1]}"
    async with aiohttp.ClientSession() as session:
        tasks = [
            fetch_ais_density(session, bbox, width=n_longitudes, height=n_latitudes, i=i, j=j, time=time)
            for i, j in product(range(n_longitudes), range(n_latitudes))
        ]
        return await tqdm.asyncio.tqdm.gather(*tasks, timeout=60 * 60)


if __name__ == "__main__":
    import json

    import numpy as np

    logging.basicConfig(level=logging.WARNING)

    data = asyncio.run(
        fetch_ais_density_grid(
            latitude_range=(-90.0, 90.0),
            longitude_range=(-179.5, 179.5),
            n_longitudes=359 * 2,
            n_latitudes=180 * 2,
            time="2023-10-01T00:00:00Z",
        ),
    )
    # Reshape data
    data_np = np.asarray(data).reshape(359, 180).transpose()

    # Dump data
    with open("data.json", "w") as f:
        json.dump(data_np.tolist(), f)
