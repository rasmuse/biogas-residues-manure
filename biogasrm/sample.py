# -*- coding: utf-8 -*-

import os
import logging
from collections import OrderedDict
from math import ceil
import json
import pickle

import click
import fiona
import rasterio
import shapely
from shapely.geometry import shape
import shapely.prepared
import shapely.ops
from rasterstats import zonal_stats
import pandas

import biogasrm.constants as constants

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

@click.group()
def cli():
    pass

@cli.command()
@click.argument('regions-path', type=click.Path(exists=True))
@click.argument('output', type=click.Path())
@click.option('--step', type=float, required=True)
@click.option('--bbox', '-b', type=float, nargs=4, required=False, default=None)
@click.option('--radii', type=str, required=True)
def disks(regions_path, output, step, bbox, radii):
    """
    Sample disk-shaped areas in a map.

    Args:
        regions_path: The NUTS regions.
        output: The path to write to (a shapefile).
        step: The step size between sample centers in km.
        radii: The radii of disks in km.
            Multiple values are separated by commas: "10,20,30"
        bbox: Bounding box to restrict samples to. If None, the whole
            map will be covered.
    """

    radii = [float(r) for r in radii.split(',')]
    step = step * constants.M_PER_KM

    with fiona.open(regions_path) as ds:
        crs = ds.crs
        driver = 'Shapefile'
        regions = {r['properties']['NUTS_ID']: shape(r['geometry']) for r in ds}
        prepared = {key: shapely.prepared.prep(shp) for key, shp in regions.items()}
    
    whole_area = shapely.ops.cascaded_union(regions.values())

    if not bbox:
        bbox = whole_area.bounds
        log.info('Bounds: {}'.format(bbox))

    whole_area = shapely.prepared.prep(whole_area)

    schema = {
        'geometry': 'Polygon',
        'properties': OrderedDict(
            [('NUTS_ID', 'str'),
            ('x', 'float'),
            ('y', 'float'),
            ('r', 'float')])
    }

    visited = set()
    with fiona.open(output, 'w', driver=driver, crs=crs, schema=schema) as dst:
        for point in generate_points(step, step, bbox):
            if not whole_area.contains(point):
                continue

            for radius in radii:
                disk = point.buffer(radius * constants.M_PER_KM)

                candidates = (
                    k for k, r in prepared.items() if r.intersects(disk))

                intersections = {
                    k: regions[k].intersection(disk)
                    for k in candidates}

                for key, intersection in intersections.items():
                    if key not in visited:
                        visited.add(key)
                        log.info('Visiting {}'.format(key))
                    if intersection.is_empty:
                        continue
                    f = dict(
                        geometry=shapely.geometry.mapping(intersection),
                        properties=dict(
                            NUTS_ID=key,
                            x=point.x,
                            y=point.y,
                            r=radius))
                    dst.write(f)


def generate_points(dx, dy, bbox):
    xmin, ymin, xmax, ymax = bbox
    
    x = dx * ceil(xmin / dx)
    while x <= xmax:
        y = dy * ceil(ymin / dy)
        while y <= ymax:
            yield shapely.geometry.Point(x, y)
            y += dy
        x += dx

@cli.command()
@click.argument('samples-path', type=click.Path(exists=True))
@click.argument('raster-path', type=click.Path(exists=True))
@click.argument('region-sums', type=click.File('r'))
@click.argument('dst', type=click.File('wb'))
def sample_region_fracs(samples_path, raster_path, region_sums, dst):
    """
    Calculate each sample's fraction of a region.
    """

    density_name = os.path.splitext(os.path.split(raster_path)[1])[0]
    stats = zonal_stats(
        samples_path,
        raster_path,
        stats=['sum'],
        geojson_out=True)

    sample_sums = pandas.DataFrame.from_records(
        [
        {key: item['properties'][key]
        for key in  ('x','y','r','NUTS_ID','sum')}
        for item in stats], index=['x','y','r','NUTS_ID'])['sum']

    region_sums = pandas.Series(json.loads(region_sums.read()))

    sample_fracs = sample_sums.divide(region_sums, axis=0, level='NUTS_ID')

    pickle.dump(sample_fracs, dst)
