import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / '.env')
for key, default in {'GDAL_CACHEMAX': '128', 'GDAL_NUM_THREADS': '1', 'VSI_CACHE': 'FALSE', 'OMP_NUM_THREADS': '1', 'OPENBLAS_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1', 'GDAL_HTTP_TIMEOUT': '40', 'GDAL_HTTP_MAX_RETRY': '2', 'GDAL_DISABLE_READDIR_ON_OPEN': 'EMPTY_DIR'}.items():
    os.environ.setdefault(key, default)
RUNTIME = ROOT / '.runtime'
JOBS = RUNTIME / 'jobs'
MODEL = os.getenv('META_REASONING_MODEL', 'muse-wonder-1.0')
SAM_MODEL = os.getenv('META_SEGMENTATION_MODEL', 'sam-3.1')
META_URL = os.getenv('META_API_BASE_URL', 'https://api.meta.ai/v1').rstrip('/')
STAC_URL = os.getenv('STAC_API_URL', 'https://planetarycomputer.microsoft.com/api/stac/v1').rstrip('/')
IDLE_TTL = int(os.getenv('ANALYSIS_IDLE_TTL_MINUTES', '60')) * 60
HARD_TTL = int(os.getenv('ANALYSIS_MAX_LIFETIME_MINUTES', '240')) * 60
BUDGET = float(os.getenv('META_SESSION_BUDGET_USD', '150'))

SOURCES = {
    'landsat': {'name': 'Landsat', 'collection': 'landsat-c2-l2', 'start': 1982, 'resolution': 30, 'kind': 'optical', 'description': 'Long histories · surface reflectance · 30 m'},
    'sentinel2': {'name': 'Sentinel-2', 'collection': 'sentinel-2-l2a', 'start': 2015, 'resolution': 20, 'kind': 'optical', 'description': 'Detailed optical observations · 20 m analysis'},
    'hls_l30': {'name': 'HLS Landsat', 'collection': 'hls2-l30', 'start': 2020, 'resolution': 30, 'kind': 'optical', 'description': 'Harmonized Landsat · this catalog from 2020'},
    'hls_s30': {'name': 'HLS Sentinel', 'collection': 'hls2-s30', 'start': 2020, 'resolution': 30, 'kind': 'optical', 'description': 'Harmonized Sentinel · this catalog from 2020'},
    'modis': {'name': 'MODIS', 'collection': 'modis-09A1-061', 'start': 2000, 'resolution': 500, 'kind': 'optical', 'description': 'Regional 8-day surface reflectance · 500 m'},
    'sentinel1': {'name': 'Sentinel-1 radar', 'collection': 'sentinel-1-rtc', 'start': 2014, 'resolution': 30, 'kind': 'radar', 'description': 'Terrain-corrected radar · matched orbit required'},
}
