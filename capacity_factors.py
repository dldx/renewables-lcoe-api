import rasterio

pv_output = rasterio.open('data/World_PVOUT_GISdata_LTAy_AvgDailyTotals_GlobalSolarAtlas-v2_GEOTIFF/PVOUT.tif')

def get_solar_capacity_factor(longitude: float, latitude: float) -> float:
    """Get the solar capacity factor for a given latitude and longitude by reading from a raster GEOTIFF file.

    This file contains the average daily solar radiation in kWh/kWp globally, and is sourced from the Global Solar Atlas.

    To convert this to a capacity factor, we divide by 24 hours.

    Args:
        longitude (float): The longitude.
        latitude (float): The latitude.

    Returns:
        float: The solar capacity factor.
    """

    capacity_factor = float(next(pv_output.sample([(longitude, latitude)]))[0]/24)

    return capacity_factor