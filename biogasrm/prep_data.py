# -*- coding: utf-8 -*-

from collections import defaultdict
import json
import os
import re

import click
import numpy as np
import rasterio
import pandas
import pickle
import fiona

import biogasrm.util as util
import biogasrm.spatial_util as spatial_util
import biogasrm.constants as constants

@click.group()
def cli():
    pass

@cli.command()
@click.argument('land-cover', type=click.Path(exists=True))
@click.argument('dst', type=click.Path())
def cropland(land_cover, dst):
    transform = lambda clc_class: constants.CROPLAND_WEIGHTS[clc_class]
    transform = np.vectorize(transform, otypes=[np.float32])
    spatial_util.transform(
        land_cover, dst, transform,
        masked=True, dtype='float32', nodata=-1)
    spatial_util.update_stats(dst)

@cli.command()
@click.argument('land-cover', type=click.Path(exists=True))
@click.argument('dst', type=click.Path())
def water(land_cover, dst):
    transform = lambda clc_class: constants.WATER_WEIGHTS[clc_class]
    transform = np.vectorize(transform, otypes=[np.float32])
    spatial_util.transform(
        land_cover, dst, transform,
        masked=True, dtype='float32', nodata=0)
    spatial_util.update_stats(dst)


@cli.command()
@click.argument('raster', type=click.Path(exists=True))
@click.argument('regions', type=click.Path(exists=True))
@click.option('--key-property', '-k', type=str, default=None)
@click.option('--output', '-o', type=click.File('w'), default='-')
def coverage(raster, regions, key_property, output):
    result = spatial_util.coverage(raster, regions, key_property=key_property)
    json.dump(result, output)


def nuts_partition():
    NUTS = constants.NUTS
    countries = NUTS.level(0)
    levels = {
        country: constants.NUTS_LEVEL[country]
        for country in countries
        if constants.NUTS_LEVEL[country] != 'exclude'}
    included = set.union(*(NUTS.descendants(c, levels[c]) for c in levels))
    return included


@cli.command()
@click.argument('regions', type=click.Path(exists=True))
@click.option('--output', '-o', type=click.Path())
@click.argument('cover-files', type=click.Path(exists=True), nargs=-1)
def included_NUTS(regions, output, cover_files):
    covers = [json.loads(open(path, 'r').read()) for path in cover_files]

    def sufficient_cover(code):
        return all(
            code in cover and
            cover[code] is not None and
            abs(cover[code]-1) <= 0.02
            for cover in covers)

    # First list of candidates
    candidates = nuts_partition()

    # This is a lousy hack: Requires that substrate amounts are computable,
    # so manure_mgmt.pkl and animal_pop.pkl must exist (see Makefile)
    import biogasrm.substrates as substrates
    import biogasrm.parameters as parameters
    params = parameters.defaults()
    substrates_known = set(substrates.get_substrates(params).index)

    # Exclude candidates which are not sufficiently covered
    included = set(
        [c for c in candidates
        if sufficient_cover(c) and c in substrates_known])

    with fiona.open(regions, 'r') as src:
        settings = dict(driver=src.driver, crs=src.crs, schema=src.schema.copy())
        with fiona.open(output, 'w', **settings) as dst:
            for f in src:
                if f['properties']['NUTS_ID'] in included:
                    dst.write(f)


@cli.command()
@click.argument('src', type=click.Path(exists=True))
@click.argument('dst', type=click.File('wb'), default='-')
def read_eurostat(src, dst):
    header = pandas.read_csv(
        src, delimiter='\s?\t', nrows=1, header=None, engine='python')
    row_level_names, col_level_names = [
        s.split(',') for s in header[0][0].split('\\')]

    data = pandas.read_csv(
        src,
        delimiter='\s?[a-z]?\t',
        na_values=[':', ': z'],
        index_col=0,
        engine='python')

    row_indices = tuple(zip(*(s.split(',') for s in data.index)))
    col_indices = tuple(zip(*(s.split(',') for s in data.columns)))
    
    data.index = pandas.MultiIndex.from_arrays(
        row_indices, names=row_level_names)
    data.columns = pandas.MultiIndex.from_arrays(
        col_indices, names=col_level_names)

    data.dropna(how='all', axis=('index', 'columns'), inplace=True)

    pickle.dump(data, dst)

@cli.command()
@click.argument('ef_olsaareg', type=click.File('rb'))
@click.argument('output', type=click.File('wb'), default='-')
def animal_pop(ef_olsaareg, output):
    years = list(map(str, constants.STAT_YEARS))    

    # Livestock populations from Eurostat ef_olsaareg
    ef_olsaareg = pickle.load(ef_olsaareg)
    ef_olsaareg_years = [y for y in years if y in ef_olsaareg.columns]

    animal_pop = ef_olsaareg.xs('TOTAL', level='agrarea')[ef_olsaareg_years].mean(axis=1)
    
    animal_pop = util.aggregate(animal_pop.unstack().T, constants.EF_OLSAAREG_CODES)

    pickle.dump(animal_pop, output)

@cli.command()
@click.argument('src-dir', type=click.Path(exists=True))
@click.argument('output', type=click.File('wb'), default='-')
def manure_mgmt(src_dir, output):
    data = {}
    for filename in os.listdir(src_dir):
        if not (len(filename) == 22 and filename.endswith('.xls')):
            continue
        ISO_code = filename[0:3]
        year = int(filename[9:13])
        try:
            NUTS0_code = constants.ISO3166_3_TO_NUTS0[ISO_code]
        except KeyError:
            continue
        path = os.path.join(src_dir, filename)
        result = _one_manure_mgmt(path)
        if result.empty:
            continue
        data[(NUTS0_code, year)] = result

    # Possibly replace some countries' reports with other countries' reports.
    for replace, replace_with in constants.MANURE_MGMT_REPLACEMENTS.items():
        for NUTS0_code, year in data.keys():
            if NUTS0_code == replace:
                del data[(NUTS0_code, year)]
                if (replace_with, year) in data:
                    data[(replace, year)] = data[(replace_with, year)]
    
    keys, dfs = zip(*data.items())
    pickle.dump(pandas.concat(data), output)

def _CRF_4Bas2(path):

    def convert_data(d):
        if hasattr(d, 'replace'):
            d = d.replace(',', '.')
        try:
            return float(d)
        except ValueError:
            return d

    cols_header_row = 6
    data_colnums = list(range(3, 10))
    data_rownums = list(range(9, 87))
    index_header_row = 5
    index_colnums = list(range(3))

    d = pandas.read_excel(
        path,
        sheetname='Table4.B(a)s2',
        header=None,
        converters={c: convert_data for c in data_colnums})

    colnames = [s.strip() for s in d[data_colnums].loc[cols_header_row]]
    index_levels = [s.strip() for s in d[index_colnums].loc[index_header_row]]

    for rownum, row in d.loc[data_rownums].iterrows():
        take_previous = row.isnull()
        for colnum in index_colnums:
            if take_previous[colnum]:
                d.at[rownum, colnum] = d.at[rownum-1, colnum]
            d.at[rownum, colnum] = d.at[rownum, colnum].strip()

    index_arrays = [d[c][data_rownums].values for c in index_colnums]
            
    d = d.loc[data_rownums][data_colnums]
    d.columns = colnames
    d.index = pandas.MultiIndex.from_arrays(index_arrays, names=index_levels)

    return d


def _one_manure_mgmt(path):
    data = _CRF_4Bas2(path)
    # Keep only the allocation data
    data = data.xs('Allocation (%)', level='Indicator')
    data[data.isnull()] = 0 # Replace null values with 0
    data[data == 'NO'] = 0 # Interpret "NO" as 0
    data[data == 'No'] = 0 # Interpret "No" as 0
    data[data == 'IE'] = 0 # Interpret "IE" as 0
    data[data == 'NE'] = 0 # Interpret "NE" as 0
    data = data.sum(level='Animal category') # Sum over climate regions
    data /= 100. # Convert percentages to fractions    
    max_rel_error = 0.01

    # Poland's 2014 submission contains very large numbers.
    # I'm guessing they are at least correct in proportion to one another,
    # so let's divide all numbers by the sum of the row.
    if re.search('POL-2014-20\d\d-v2.1.xls$', path):
        data = data.divide(data.sum(axis=1), axis=0)

    data_OK = abs(data.sum(axis=1) - 1) <= max_rel_error
    data = data[data_OK]

    # Aggregate management classes
    data = util.aggregate(data, constants.IPCC_MANURE_MGMT_AGGREGATION)
    # Disaggregate animal classes
    data = util.distribute(
        data.T, constants.IPCC_MANURE_MGMT_TO_EUROSTAT, allow_missing=True).T

    return data


def _CRF_4Bas1_excretion(path):

    def convert_data(d):
        if hasattr(d, 'replace'):
            d = d.replace(',', '.')
        try:
            return float(d)
        except ValueError:
            return d

    index_colnum = 0
    data_colnums = [6]
    data_rownums = [10,11] + list(range(13, 24))

    d = pandas.read_excel(
        path,
        sheetname='Table4.B(a)s1',
        header=None,
        converters={c: convert_data for c in data_colnums})

    idx = d.loc[data_rownums][index_colnum]
    d = d.loc[data_rownums][data_colnums]
    d.index = idx

    return d
