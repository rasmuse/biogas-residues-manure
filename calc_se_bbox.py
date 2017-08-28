import shapely.geometry
import shapely.ops
import fiona

path = 'outdata/included_NUTS.geojson'
region_criterion = lambda r: r['properties']['NUTS_ID'].startswith('SE')

with fiona.open(path) as ds:
    regions = tuple(
        shapely.geometry.shape(r['geometry']) for r in ds
        if region_criterion(r))

big_region = shapely.ops.cascaded_union(regions)

print(*map(str, big_region.bounds))

