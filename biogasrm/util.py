# -*- coding: utf-8 -*-

import os
import os.path
import logging
import itertools
import collections
import time

from osgeo import gdal, ogr, osr, gdalconst, gdal_array
import numpy as np
import pandas
import rasterio
import rasterio.crs

logger = logging.getLogger(__name__)

def aggregate(data, coldict, allow_missing=False):
    """Aggregate columns of a pandas DataFrame or Series

    Sums groups of columns to produce a DataFrame/Series with 
    new columns/rows.

    Args:
        data (DataFrame or Series): Data to aggregate.
        coldict (dict): Keys: Labels or indices of source columns. 
            Values: Iterables with labels of new columns.
        allow_missing (bool): Whether to silently skip columns not
            present in the source data. Default False.
    """
    new_data = {}
    for new, sources in coldict.items():
        if allow_missing:
            sources = [src for src in sources if src in data]
        axis = 1 if isinstance(data, pandas.DataFrame) else None
        new_data[new] = data[list(sources)].sum(axis=axis)
    if isinstance(data, pandas.DataFrame):
        return pandas.DataFrame.from_dict(new_data)
    elif isinstance(data, pandas.Series):
        return pandas.Series(new_data)


def distribute(data, categories, allow_missing=False):
    """Disaggregate data by copying each column toone or more new columns.

    Categories is a dict-like object, mapping column indices or labels 
    to iterables of new column names.

    Args:
        data (DataFrame): Data to disaggregate.
        categories (dict): Keys: Labels or indices of source columns.
            Values: Iterables of labels for the target columns.
        allow_missing (bool): Whether to silently skip categories not
            present in the source data. Default False.

    Raises:
        ValueError if source column is missing and !allow_missing.
        ValueError when there is a collision among target columns.
    """

    result = {}
    for src, targets in categories.items():
        if not src in data:
            if allow_missing:
                continue
            raise ValueError("source column '{}' is missing in data".format(src))
            
        for t in targets:
            if t in result:
                raise ValueError("target column '{}' is defined twice".format(t))
            result[t] = data[src]
            
    return pandas.DataFrame.from_dict(result)
