# -*- coding: utf-8 -*-

import os
import json

import rasterio
from rasterstats import zonal_stats
import shapely
import fiona
import numpy as np
import pandas as pd
import gdal
import click

def transform(in_path, out_path, func, band=1, masked=False, **options):
    #make output raster with **options
    #loop over chunks in input raster
    #transform chunks with func and write to output raster
    #close

    if not isinstance(band, int):
        raise ValueError('only single bands supported for now')

    with rasterio.open(in_path) as src:
        profile = src.profile
        profile.update(options)
        with rasterio.open(out_path, 'w', **profile) as dst:
            for ji, window in src.block_windows(band):
                block = src.read(indexes=band, window=window, masked=masked)
                transformed = func(block)
                assert transformed.dtype == profile['dtype']
                if isinstance(transformed, np.ma.MaskedArray):
                    nodata = dst.nodatavals[band-1]
                    transformed = transformed.filled(nodata)
                dst.write(transformed, indexes=band, window=window)

def coverage(raster, regions, key_property=None):
    if key_property is None:
        key_property = 'id'

    with rasterio.open(raster) as r:
        res = r.res
        cell_area = res[0] * res[1]

    def _not_nodata(x):
        return (~x.mask).sum()

    with fiona.open(regions) as features:
        key_mapping = {}

        areas = {}
        keys = []
        
        stats = zonal_stats(
            features,
            raster,
            stats='',
            add_stats={'count':_not_nodata},
            geojson_out=True)
    
    def _coverage(item):
        count = item['properties']['count']
        total_area = shapely.geometry.shape(item['geometry']).area
        return count * cell_area / total_area

    result = {
        item['properties'][key_property]: _coverage(item)
        for item in stats}

    return result


def make_raster_array(values, step, nodata=None, dtype=None):
    """
    Make a raster from dictionary
    
    Args:
        values (dict-like): Keys are (x, y) map coordinates, 
            values are corresponding values.
        step (number): The step size (xstep == ystep) to accept values at.
        nodata (number): The value to use if no value is provided.
        dtype: The data type of the raster.
        
    Asserts that values are either (1) missing or (2) situated at an
    even number of steps from the top left (x, y) pair.
        
    """
    
    points = iter(values)
    topleft_x, topleft_y = next(points)
    bottomright_x, bottomright_y = topleft_x, topleft_y
    for x, y in points:
        topleft_x = min(x, topleft_x)
        topleft_y = max(y, topleft_y)
        bottomright_x = max(x, bottomright_x)
        bottomright_y = min(y, bottomright_y)

    # Make a rasterio-style transformation from map coordinates 
    # to raster coordinates:
    T = ~rasterio.transform.from_origin(topleft_x, topleft_y, step, step)
    
    colmax, rowmax = T * (bottomright_x, bottomright_y)
    
    def almost_int(n, tol=1e-3):
        answer = abs(round(n) - n) < tol
        if not answer:
            print(n)
        return answer
    assert almost_int(colmax)
    assert almost_int(rowmax)
    colmax = int(colmax)
    rowmax = int(rowmax)
    
    shape = (rowmax + 1, colmax + 1)
    
    data = np.zeros(shape, dtype=dtype)
    mask = np.ones(shape, dtype=bool)
    
    for point, value in values.items():
        col, row = T * point
        assert almost_int(col)
        assert almost_int(row)
        col, row = map(int, (col, row))
        data[row, col] = value
        mask[row, col] = False
        
    raster = np.ma.array(data, mask=mask, fill_value=nodata)
    transform = rasterio.transform.from_origin(
        topleft_x, topleft_y, step, step)

    return raster, transform

def write_raster(path, array, transform, crs):
    """Write a 1-band GeoTIFF

    Args:
        path: File path to save.
        array: Numpy array or MaskedArray.
        transform: The rasterio Affine transform
            from (col, row) coords to map coords.
        crs: A rasterio crs or EPSG string, e.g. 'EPSG:3035'.

    Example:
        >>> import numpy
        >>> w, h = 50, 100
        >>> array = numpy.random.random((h, w))
        >>> topleft_x, topleft_y = 10, 20000 # Map coordinates for top left corner
        >>> x_step, y_step = 20, 30
        >>> T = rasterio.transform.from_origin(topleft_x, topleft_y, xstep, ystep)
        >>> crs = rasterio.crs.from_string('EPSG:3035')
        >>> write_raster('/tmp/file.tif', array, T, crs)
    """
            
    settings = dict(
        crs=crs,
        affine=transform,
        width=array.shape[1],
        height=array.shape[0],
        driver='GTiff',
        count=1,
        dtype=array.dtype.name
    )

    if isinstance(crs, str):
        crs = rasterio.crs.from_string(crs)
        
    if isinstance(array, np.ma.MaskedArray):
        assert 'nodata' not in settings
        settings['nodata'] = array.fill_value
        array = array.filled()
        
    with rasterio.open(path, 'w', **settings) as dst:
        dst.write(array, indexes=1)


def write_data_to_regions(src_path, dst_path, key_property, data):
    with fiona.open(src_path) as src:

        # Copy the source schema and add the new properties.
        sink_schema = src.schema.copy()
        for col in data.columns:
            data_dtype = str(data[col].dtype)
            if data_dtype.startswith('float'):
                schema_dtype = 'float'
            elif data_dtype.startswith('int'):
                schema_dtype = 'int'
            else:
                raise NotImplementedError('unsupported dtype')

            sink_schema['properties'][col] = schema_dtype

        settings = dict(crs=src.crs, driver=src.driver, schema=sink_schema)

        if os.path.exists(dst_path):
            os.remove(dst_path)
        with fiona.open(dst_path, 'w', **settings) as dst:
            for feature in src:
                key = feature['properties'][key_property]
                for col in data:
                    feature['properties'][col] = data.loc[key, col]
                dst.write(feature)
