# -*- coding: utf-8 -*-

import pandas
import biogasrm.constants as constants

def defaults():
    # dry weight / wet weight
    params = {}

    params['DM_FRACS'] = pandas.DataFrame(
        {
            'glw_cattle': {'liquid': 0.08, 'solid': 0.2},
            'glw_pigs': {'liquid': 0.06, 'solid': 0.2},
            'glw_chickens': {'liquid': 0.30, 'solid': 0.70},
            'cropland': {
                'straw': 0.85,
                'stover': 0.85,
                'sunflower stalks': 0.85,
                'beet tops': 0.13
                }
        }
    )

    # VS / DM
    params['VS_FRACS'] = pandas.DataFrame(
        {
            'glw_cattle': {'liquid': .8, 'solid': .85},
            'glw_pigs': {'liquid': .8, 'solid': .85},
            'glw_chickens': {'liquid': 0.7, 'solid': 0.7},
            'cropland': {
                'straw': 0.9,
                'stover': 0.9,
                'sunflower stalks': 0.9,
                'beet tops': 0.9
                }
        }
    )

    # C / VS
    params['C_FRACS'] = pandas.DataFrame(
        {
            'glw_cattle': {'liquid': 0.55, 'solid': 0.55},
            'glw_pigs': {'liquid': 0.55, 'solid': 0.55},
            'glw_chickens': {'liquid': 0.55, 'solid': 0.55},
            'cropland': {
                'straw': 0.55,
                'stover': 0.55,
                'sunflower stalks': 0.55,
                'beet tops': 0.55
                }
        }
    )

    # N / VS
    params['N_FRACS'] = pandas.DataFrame(
        {
            'glw_cattle': {'liquid': 0.07, 'solid': 0.035},
            'glw_pigs': {'liquid': 0.10, 'solid': 0.05},
            'glw_chickens': {'liquid': 0.09, 'solid': 0.09},
            'cropland': {
                'straw': 0.005,
                'stover': 0.005,
                'sunflower stalks': 0.005,
                'beet tops': 0.025
                }
        }
    )


    for n in ('DM_FRACS', 'VS_FRACS', 'C_FRACS', 'N_FRACS'):
        df = params[n]
        df.columns.names=['density']
        df.index.names=['substrate']


    # Mg VS / year
    # Based on 2006 IPCC Guidelines except hens and broilers.
    params['EXCRETION_PER_HEAD'] = pandas.Series({
        'dairy cows': 5.1 * 365 / 1000,
        'other cattle': 2.6 * 365 / 1000,
        'breeding swine': 0.5 * 365 / 1000, #.46 for Western Europe, .5 for Eastern Europe
        'market swine': 0.3 * 365 / 1000,
        #'sheep': 0.4 * 365 / 1000,
        'goats': 0.3 * 365 / 1000,
        'hens': 11 / 1000 * 0.7 * 1000, # DM per year * guesstimate for VS/DM ratio * 1000 heads
        'broilers': 7 / 1000 * 0.7 * 1000 # DM per year * guesstimate for VS/DM ratio * 1000 heads
    })

    params['SOLID_STRAW_BEDDING_RATIO'] = pandas.Series({
        'glw_cattle': 1,
        'glw_pigs': 1,
        #'sheep': {'solid': .5, 'liquid': 0, 'other': 1},
        'glw_chickens': 0
    })
    params['SOLID_STRAW_BEDDING_RATIO'].index.name = 'animal'



    # Residue wet weight / reported crop production (unitless)
    params['RESIDUE_RATIOS'] = pandas.DataFrame.from_dict({
        'straw': {
            # Rough numbers for straw loosely based on Nilsson & Bernesson (2009)
            # Including all straw (stubble height 0) but excluding husks.
            'C1120': 0.9, # Common wheat and spelt
            'C1130': 0.9, # Durum wheat
            'C1150': 1.1, # Rye
            'C1160': 0.7, # Barley
            'C1180': 0.8, # Oats
            'C1420': 1.2 # Rape and turnip rape
            },
        'stover': {
            'C1200': 1 #Grain maize, based on Scarlat et al (2010), Table 1
        },
        'beet tops': {
            'C1370': 0.6 #43 Mg/ha / 75 Mg/ha # Based on Kreuger et al (2014) http://lup.lub.lu.se/record/5336629
        },
        'sunflower stalks': {
            'C1450': 2 #Based on Scarlat et al (2010), Table 1
        }
    })

    params['REMOVAL_RATE'] = 0.4

    params['RESIDUE_RATIOS'] *= params['DM_FRACS']['cropland'] * params['VS_FRACS']['cropland']

    # m^3 CH4 / Mg VS
    params['BIOGAS_YIELDS'] = pandas.DataFrame({
        'cropland': {
            'straw': 200,
            'beet tops': 300, 
            'sunflower stalks': 200,
            'stover': 200
        },
        'glw_pigs': {
            'liquid': 200, 
            'solid': 200,
        },
        'glw_cattle': {
            'liquid': 200,
            'solid': 200
        },
        # 'sheep': {
        #     'liquid': 200,
        #     'solid': 200
        # }
        'glw_chickens': {
            'liquid': 250,
            'solid': 250
        },
    })
    # Expressed in m^3 CH4 / Mg VS. Convert to MW year / Mg VS:
    params['BIOGAS_YIELDS'] *= constants.MJ_PER_NM3_CH4 / constants.MJ_PER_MW_YEAR

    params['BIOGAS_YIELDS'].columns.names = ['density']
    params['BIOGAS_YIELDS'].index.names = ['substrate']

    params['D_min'] = 0.0
    params['D_max'] = 0.12
    params['CN_min'] = 10
    params['CN_max'] = 35
    params['P_min'] = 1
    params['RADIUS'] = 20

    return params
