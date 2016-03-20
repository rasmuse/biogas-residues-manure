# -*- coding: utf-8 -*-

import tempfile
import pickle
import os
import re
from subprocess import check_call
import shutil
import json

import click
import numpy as np
import pandas as pd
from scipy.optimize import linprog
import fiona
import shapely

import biogasrm.parameters as parameters
import biogasrm.constants as constants
import biogasrm.util as util
import biogasrm.spatial_util as spatial_util

INCLUDED_NUTS_PATH = 'outdata/included_NUTS.geojson'

def _duplicate_columns(data, duplications, allow_missing=False):

    result = {}
    for target, src in duplications.items():
        if not src in data:
            if allow_missing:
                continue
            raise ValueError("source column '{}' is missing in data".format(src))

        result[target] = data[src]
            
    return pd.DataFrame.from_dict(result)


def get_excretion(params):
    """
    Get total excretion of manure in different management systems.

    Unit Mg VS / year

    Returns: DataFrame.
        Rows: NUTS regions. Columns: 2-level index (livestock, management).
    """

    mgmt = pickle.load(open('outdata/manure_mgmt.pkl', 'rb'))
    animal_pop = pickle.load(open('outdata/animal_pop.pkl', 'rb'))
    mgmt = mgmt.stack().unstack(1)[constants.STAT_YEARS].mean(axis=1)

    NUTS = constants.NUTS

    mgmt = mgmt.unstack(0)
    NUTS0_parents = {n: NUTS.ancestor(n, 0) for n in animal_pop.index}

    # copy manure mgmt to subregions
    mgmt = _duplicate_columns(mgmt, NUTS0_parents, allow_missing=True)

    # Add 'animals' and 'geo' names to match Eurostat animal populations data.
    animal_pop = animal_pop.unstack()
    mgmt = mgmt.stack().unstack(1)
    mgmt.index.names = animal_pop.index.names = 'animal', 'geo'

    mgmt.columns.name = 'mgmt'

    # Multiply them. Result: number of heads with different management.
    pop_by_mgmt = mgmt.mul(animal_pop, axis=0).dropna(how='all')

    pop_by_mgmt = util.aggregate(
        pop_by_mgmt.unstack().T,
        constants.EXCR_CLASSES_TO_EUROSTAT)

    excretion_by_mgmt = pop_by_mgmt * params['EXCRETION_PER_HEAD']

    # Aggregate to GLW classes
    excretion_by_mgmt = util.aggregate(excretion_by_mgmt, constants.GLW_TO_IPCC)

    excretion_by_mgmt.columns.name = 'animal'

    excretion_by_mgmt = excretion_by_mgmt.unstack(0)

    #

    return excretion_by_mgmt

def get_residues(params):
    """
    Get available amounts of different residues including other uses.

    Calculated as total residue production * REMOVAL_RATE.

    Unit Mg VS / year.

    Returns: DataFrame.
        Rows: NUTS regions. Columns: Residue types.
    """

    years = list(map(str, constants.STAT_YEARS))    

    # National and subnational harvested areas from Eurostat ef_oluaareg
    ef_oluaareg = pickle.load(open('outdata/eurostat/ef_oluaareg.pkl', 'rb'))
    ef_oluaareg_years = [y for y in years if y in ef_oluaareg.columns]
    ef_oluaareg = (ef_oluaareg
                   .xs('TOTAL', level='agrarea')[ef_oluaareg_years]
                   .mean(axis=1)
                   .unstack(0))

    crop_areas = util.aggregate(ef_oluaareg, constants.EF_OLUAAREG_CODES)
    crop_areas = crop_areas.fillna(0) # Assume zero harvest area for missing data

    # National and subnational harvests, but incomplete
    agr_r_crops = pickle.load(open('outdata/eurostat/agr_r_crops.pkl', 'rb'))
    agr_r_crops = agr_r_crops.xs('PR', level='strucpro')[years].mean(axis=1).unstack(0)
    agr_r_crops *= 1000 # Unit conversion to Mg harvest

    # National harvest data from Eurostat apro_cpp_crop table
    apro_cpp_crop = pickle.load(open('outdata/eurostat/apro_cpp_crop.pkl', 'rb'))
    apro_cpp_crop *= 1000 # Unit conversion to Mg
    apro_cpp_crop = apro_cpp_crop.xs('PR', level='strucpro')[years].mean(axis=1).unstack(0)

    national_harvests = {}
    for target, sources in constants.APRO_CPP_CROP_CODES.items():
        national_harvests[target] = apro_cpp_crop[sources[0]] # Base choice
        for src in sources[1:]: # Fill in with other choices if previous not available
            src = apro_cpp_crop[src].copy()
            src.update(national_harvests[target]) # Target overwrites src where not-null
            national_harvests[target] = src # Then write back

    national_harvests = pd.DataFrame(national_harvests)


    NUTS = constants.NUTS
    candidate_regions = set.union(NUTS.level(0), NUTS.level(1), NUTS.level(2))
    regions = list(candidate_regions.intersection(set(crop_areas.index)))

    subnational_harvests = pd.DataFrame(index=regions, columns=crop_areas.columns)
    subnational_harvests.update(national_harvests) # National harvests as base alternative
    subnational_harvests.update(agr_r_crops) # Fill in subnational

    missing = subnational_harvests.isnull().stack()
    missing = missing[missing].index

    # Estimate missing data using harvested areas and parent areas' harvests:
    
    for nuts_code, crop in missing:
        ancestor = NUTS.ancestor(nuts_code, 0)
        anc_area = crop_areas.loc[ancestor, crop]
        this_area = crop_areas.loc[nuts_code, crop]
        if this_area == 0 or anc_area == 0:
            harvest = 0
        else:
            weight = this_area / anc_area
            harvest = subnational_harvests.loc[ancestor, crop] * weight
        
        subnational_harvests.loc[nuts_code, crop] = harvest


    RESIDUE_RATIOS = params['RESIDUE_RATIOS']
    residues = pd.DataFrame.from_dict(
        {r: subnational_harvests.multiply(RESIDUE_RATIOS[r], axis=1).sum(axis=1)
         for r in RESIDUE_RATIOS.columns}).dropna(how='all')

    return residues


def get_substrates(params, basis='VS'):
    """
    Get total available substrates.

    Unit is Mg VS / year by default.
    Use basis='DM' to get Mg DM / year instead.

    Returns: DataFrame.
        Rows: NUTS regions. Columns: 2-level index (density, substrate).
    """

    excretion = get_excretion(params)
    residues = get_residues(params)

    # Excretion by manure management --> bedding requirements
    bedding_straw_wish = (excretion
                    .xs('solid', level='mgmt', axis=1)
                    .multiply(params['SOLID_STRAW_BEDDING_RATIO'])
                    .dropna())

    # Intersection of straw data and manure data
    straw = residues['straw'].dropna()
    idx = straw.index.intersection(bedding_straw_wish.index)
    straw = straw.loc[idx]
    bedding_straw_wish = bedding_straw_wish.loc[idx]

    # The bedding "needed", and what can maximally be supplied per region
    available = straw / bedding_straw_wish.sum(axis=1)
    available[available > 1] = 1

    # If there is no bedding needed, 100% is available (to avoid x/0 NaN)
    available[bedding_straw_wish.sum(axis=1)==0] = 1

    # Actual bedding used (minimum of "needed" and straw amount in region)
    bedding_straw = bedding_straw_wish.multiply(available, axis=0)

    # The solid manure production that cannot be supported by local straw
    impossible_solid = bedding_straw_wish - bedding_straw
    for animal in impossible_solid:
        excretion[animal, 'solid'] -= impossible_solid[animal]
        excretion[animal, 'liquid'] += impossible_solid[animal]


    substrates = {}
    # Residues are distributed like cropland.
    # Maximal removal rates are formulated for resource after bedding use removal.
    substrates['cropland'] = residues
    substrates['cropland']['straw'] -= bedding_straw.sum(axis=1)
    substrates['cropland'] *= params['REMOVAL_RATE']
    substrates['cropland']['straw'] = (
        substrates['cropland']['straw'].apply(lambda x: max(x, 0)))


    # Distributed like animals
    for animal in excretion.columns.levels[0]:
        substrates[animal] = excretion[animal]
        del substrates[animal]['unavailable']

    substrates = pd.concat(substrates, axis=1)

    substrates.columns.names = ['density', 'substrate']

    substrates.dropna(how='any', axis=0, inplace=True)


    if basis == 'VS':
        pass
    elif basis == 'DM':
        substrates = substrates.div(
            params['VS_FRACS'].unstack().dropna(), axis=1)
    else:
        raise ValueError('Basis must be VS or DM.')

    return substrates

def get_sample_fracs(sampling):
    samples_dir = os.path.abspath('outdata/sampling/{}/'.format(sampling))
    fracs = {}
    for filename in os.listdir(samples_dir):
        if not filename.endswith('_fracs.pkl'):
            continue
        density_name = filename.replace('_fracs.pkl', '')
        with open(os.path.join(samples_dir, filename), 'rb') as f:
            fracs[density_name] = pickle.load(f)
    fracs = pd.DataFrame(fracs)
    fracs.dropna(inplace=True, axis=(0,1))
    return fracs


def get_sample_substrates(sampling, params):
    samples = get_sample_fracs(sampling)
    region_substrates = get_substrates(params)

    sample_substrates = (
        pd.concat(
            {
                distribution: 
                 (region_substrates[distribution]
                  .multiply(samples[distribution], level='NUTS_ID', axis=0)
                  .groupby(level=['x', 'y', 'r']).sum().stack())
                 for distribution in region_substrates.stack().columns
            }, axis=1)
        .unstack()
        .dropna(how='all', axis=1))
    sample_substrates.columns.names = ['density', 'substrate']
    sample_substrates = sample_substrates.fillna(0)
    return sample_substrates


def maximize_prod(substrates, params):
    """
    Maximize biogas production from a composition of substrates.

    Amounts should be expressed as Mg VS.

    Args:
        substrates: Either a Series with substrates, or a
            DataFrame where each row is such a Series.

    Returns:
        The amount of substrates utilized after optimization.
    """
    if isinstance(substrates, pd.Series):
        return _one_maximize_prod(substrates, params)
    else:
        limited = substrates.copy()
        for idx, row in limited.iterrows():
            limited.loc[idx] = _one_maximize_prod(row, params)
        return limited


def _one_maximize_prod(substrates, params):
    gas_yields = params['BIOGAS_YIELDS'].copy()

    biogas_yields = gas_yields.unstack().dropna()

    # Index the whole problem after yields
    indices = biogas_yields.index

    biogas_yields = biogas_yields.values
    point = substrates[indices].values

    # Used for constraints:
    vs_fracs = params['VS_FRACS'].unstack()[indices].values
    dm_fracs = params['DM_FRACS'].unstack()[indices].values
    c_fracs = params['C_FRACS'].unstack()[indices].values
    n_fracs = params['N_FRACS'].unstack()[indices].values

    # We are optimizing
    # minimize c * point
    # subject to
    #  A_ub * point <= b_ub

    c = -biogas_yields

    A_ub_rows = []
    b_ub_values = []

    def add_le(A_row, b_val):
        A_ub_rows.append(A_row)
        b_ub_values.append(b_val)

    # Substrate amount constraints
    for i, amount in enumerate(point):
        arr = np.zeros(len(point))
        arr[i] = 1
        add_le(arr, amount) # Less than available
        add_le(-arr, 0) # More than zero

    # Lower DM limit
    add_le(params['D_min']/(dm_fracs * vs_fracs) - 1/vs_fracs, 0)

    # Upper DM limit
    add_le(1/vs_fracs - params['D_max']/(dm_fracs * vs_fracs), 0)

    # Lower C:N limit
    add_le(params['CN_min'] * n_fracs - c_fracs, 0)

    # Upper C:N limit
    add_le(c_fracs - params['CN_max'] * n_fracs, 0)

    # Minimal plant size
    add_le(-biogas_yields, -params['P_min'])

    A_ub = np.vstack(A_ub_rows)
    b_ub = np.array(b_ub_values)
    result = linprog(c, A_ub=A_ub, b_ub=b_ub)

    # 0 : Optimization terminated successfully
    # 1 : Iteration limit reached
    # 2 : Problem appears to be infeasible
    # 3 : Problem appears to be unbounded

    if result['status'] == 0:
        return pd.Series(index=indices, data=result['x'])
    elif result['status'] == 2:
        return pd.Series(index=indices, data=0*point)
    else:
        raise RuntimeError('unexpected status')

def biogas_prod(substrates, params):
    """
    Unconstrained production of biogas from substrates.

    Essentially the dot product of substrate amounts and biogas yields.

    Use maximize_prod() to find the optimal substrate composition to use
    (i.e. which substrates to exclude).

    Args:
        substrates: either a DataFrame with one substrate set per row,
            or a Series with a substrate set
    """
    prod = substrates * params['BIOGAS_YIELDS'].unstack().dropna()
    if isinstance(prod, pd.DataFrame):
        return prod.sum(axis=1)
    else:
        return prod.sum()

def overall_limit(sampling, params):

    limited_substrates = get_sample_substrates(sampling, params)
    limited_substrates = limited_substrates.xs(params['RADIUS'], level='r')
    limited_substrates = maximize_prod(limited_substrates, params)
    actual = biogas_prod(limited_substrates.sum(), params)

    unlimited_substrates = get_sample_substrates(sampling, params).xs(
        params['RADIUS'], level='r')
    benchmark = biogas_prod(unlimited_substrates.sum(), params)

    return actual / benchmark

def total_potential(sampling, params, regions):
    substrates = get_substrates(params).loc[regions].sum()
    P_theoretical = biogas_prod(substrates, params)
    return P_theoretical * overall_limit(sampling, params)


def read_sampling_settings(sampling):
    with open('sampling-settings/{}'.format(sampling), 'r') as f:
        settings_string = f.read()
    step = float(
        re.search('--step\s+(?P<step>\d+(\.\d+)?)', settings_string)
        .group('step'))
    radii = [float(s) for s in
            re.search(r'--radii\s+(?P<radii>[0-9\.,]+)', settings_string)
            .group('radii')
            .split(',')]

    return {'step': step, 'radii': radii}


def save_raster_from_points(series, path, nodata=None, sampling='default'):
    if nodata is None:
        nodata = -1
    settings = read_sampling_settings(sampling)
    arr, transform = spatial_util.make_raster_array(
        series.to_dict(),
        settings['step'] * constants.M_PER_KM,
        nodata=nodata,
        dtype=series.dtype)

    # Same as CLC2006 (yeah, we are assuming A LOT about the data here...)
    crs = 'EPSG:3035'

    spatial_util.write_raster(path, arr, transform, crs)


def make_substrate_raster(substrate, dst_path, removal_rate, basis='DM'):
    """
    Make a raster with the same extent and CRS as the CLC raster,
    but with each cell containing the number of dry metric tonnes
    of a substrate.

    Args:
        substrate: A tuple like ('cropland', 'straw') to identify the
            desired substrate. Possible values can be seen by calling
            get_substrates() and checking the columns.
        dst_path: Where to put the file. May not exist.
        removal_rate: A number between 0 and 1 to indicate how large
            portion of residues may be removed from fields.
        basis: 'DM' to express amounts as dry matter. 'VS' to express as VS.

    """

    if os.path.exists(dst_path):
        raise ValueError('Path {} already exists!'.format(dst_path))
    if not (0 <= removal_rate <= 1):
        raise ValueError('Removal rate must be between 0 and 1.')


    raster_name = substrate[0]
    density_template_path = 'outdata/{}.tif'.format(raster_name)

    with open('outdata/regional_sums/{}.json'.format(raster_name), 'r') as f:
        regional_sums = json.loads(f.read())
        regional_sums = pd.Series(regional_sums)

    params = parameters.defaults()
    params['REMOVAL_RATE'] = removal_rate

    amounts = get_substrates(params, basis=basis)[substrate]
    colname = 'substrate'
    amounts_per_raster_unit = amounts / regional_sums
    amounts_per_raster_unit[regional_sums[regional_sums == 0].index] = 0
    amounts_per_raster_unit.dropna(inplace=True)
    amounts_per_raster_unit = pd.DataFrame({colname: amounts_per_raster_unit})

    tempdir = tempfile.mkdtemp()
    region_substrates_path = os.path.join(tempdir, 'substrates.geojson')
    temp_raster_path = os.path.join(tempdir, 'substrate.tif')

    try:
        spatial_util.write_data_to_regions(
            src_path=INCLUDED_NUTS_PATH,
            dst_path=region_substrates_path,
            key_property='NUTS_ID',
            data=amounts_per_raster_unit)

        rasterize_command = (
            'rio rasterize --like {template} '
            '--property {property_name} --fill {fill} '
            '-o {dst} {region_substrates_path}'
            .format(
                template=density_template_path,
                property_name=colname,
                fill=-1, # nodata
                dst=temp_raster_path,
                region_substrates_path=region_substrates_path).split(' '))

        result = check_call(rasterize_command)
        assert 0 == result, 'Rasterization failed!'

        multiply_command = ([
            'rio', 'calc', '(* (read 1) (read 2))',
            '-o', dst_path,
            density_template_path, temp_raster_path])

        result = check_call(multiply_command)
        assert 0 == result, 'Raster multiplication failed!'

    finally:
        shutil.rmtree(tempdir)


@click.group()
def cli():
    pass

default_removal_rate = parameters.defaults()['REMOVAL_RATE']

@cli.command()
@click.argument('density', type=str)
@click.argument('substrate', type=str)
@click.argument('dst_path', '-o', type=click.Path())
@click.option('--removal-rate', '-r', type=float,
    help='Residue removal rate. Default {}.'.format(default_removal_rate),
    default=default_removal_rate)
@click.option('--basis', '-b', type=click.Choice(['DM', 'VS']),
    help='DM or VS basis?')
def make_raster(density, substrate, dst_path, removal_rate, basis):
    """Rasterize a substrate density.

    Args:
        density: One of the densities:
            "cropland",
            "glw_cattle",
            "glw_pigs",
            "glw_chickens"
        substrate: One of the substrates:
            "liquid",
            "solid",
            "straw",
            "stover",
            "sunflower stalks",
            "beet tops"
        dst_path: The path where to put the resulting raster.
        removal_rate: The fraction of crop residues removed from cropland
            (including for use as bedding).
        basis: "VS" or "DM" to get the results as Mg VS / year or
        as Mg DM / year (per raster cell).

    """

    make_substrate_raster(
        (density, substrate), dst_path, removal_rate, basis=basis)
