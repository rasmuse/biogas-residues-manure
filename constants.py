# -*- coding: utf-8 -*-

from collections import defaultdict
import pandas
import nuts

MJ_PER_NM3_CH4 = 40
M_PER_KM = 1000

import quantities as qty

def set_value(func):
    return func()

@set_value
def MJ_PER_MW_YEAR():
    MJ_per_year = 1e6 * qty.J / (qty.year)
    return 1 / MJ_per_year.rescale(qty.MW).item()

# A2000         Live bovine animals
# A2010         Bovine animals, less than 1 year
# A2010B        Bovine animals, less than 1 year, for slaughter
# A2010C        Bovine animals, less than 1 year, not for slaughter
# A2020         Bovine animals, 1 year
# A2030         Bovine animals, 2 years or over
# A2110C        Male calves, less than 1 year, not for slaughter
# A2120         Male bovine animals, 1 year
# A2130         Male bovine animals, 2 years or over
# A2210C        Female calves, less than 1 year, not for slaughter
# A2220         Heifers, 1 year
# A2220B        Heifers, 1 year, for slaughter
# A2220C        Heifers, 1 year, not for slaughter
# A2230         Heifers, 2 years or over
# A2230B        Heifers, 2 years or over, for slaughter
# A2230C        Heifers, 2 years or over, not for slaughter
# A2230_2330    Female bovine animals, 2 years or over
# A2300         Cows
# A2300F        Dairy cows
# A2300G        Non dairy cows
# A2400         Buffaloes
# A3100         Live swine, domestic species
# A3110         Piglets, less than 20 kg
# A3120         Breeding sows
# A3120K        Covered sows
# A3120KA       Sows covered for the first time
# A3120L        Sows, not covered
# A3120LA       Gilts not yet covered
# A3120_3133    Breeding pigs
# A3131         Pigs, from 20 kg to less than 50 kg
# A3132         Fattening pigs, 50 kg or over
# A3132X        Fattening pigs, from 50 kg to less than 80 kg
# A3132Y        Fattening pigs, from 80 kg to less than 110 kg
# A3132Z        Fattening pigs, 110 kg or over
# A3133         Breeding boars
# A4100         Live sheep
# A4110K        Ewes and ewe-lambs put to the ram
# A4110KC       Milk ewes and ewe-lambs put to the ram
# A4110KD       Non milk ewes and ewe-lambs put to the ram
# A4120         Other sheep
# A4200         Live goats
# A4210K        Goats mated and having already kidded
# A4210KA       Goats mated for the first time
# A4210KB       Goats having already kidded
# A4220         Other goats 
# A5110         Hens
# A5110O        Laying hens
# A5120         Cocks
# A5130         Chicks of chicken
# A5140         Broilers

# C_5_1_1000_HEADS    1000 heads: Poultry - broilers
# C_5_2_1000_HEADS    1000 heads: Laying hens
# C_5_3_1000_HEADS    1000 heads: Poultry - others


# Keys: Gridded Livestock of the World animals. Values: excretion classes
GLW_TO_IPCC = {
    'glw_cattle': ('dairy cows', 'other cattle'),
    'glw_pigs': ('breeding swine', 'market swine'),
    #'sheep': ('sheep',),
    'glw_chickens': ('hens', 'broilers')
}

# Keys: excretion classes (based on IPCC, except for poultry). Values: Eurostat animals.
EXCR_CLASSES_TO_EUROSTAT = {
    'dairy cows': ('A2300F',),
    'other cattle': ('A2010', 'A2120', 'A2130', 'A2220', 'A2230', 'A2300G'),
    'breeding swine': ('A3120',),
    'market swine': ('C_4_99_HEADS',),
    'hens': ('A5110O',),
    #'sheep': ('A4100',),
    'broilers': ('A5140',)
}

# Keys: IPCC inventory guidelines for manure management animals. Values: Eurostat animals.
IPCC_MANURE_MGMT_TO_EUROSTAT = {
    'Dairy Cattle': ('A2300F',),
    'Non-Dairy Cattle': ('A2010', 'A2120', 'A2130', 'A2220', 'A2230', 'A2300G'),
    'Mature Dairy Cattle': ('A2300F',),
    'Mature Non-Dairy Cattle': ('A2130', 'A2300G'),
    'Young Cattle': ('A2010', 'A2120', 'A2220', 'A2230'),
    'Swine': ('A3120', 'C_4_99_HEADS'),
    #'Sheep': ('A4100',),
    'Poultry': ('A5110O', 'A5140')
}

# Keys: our simplified manure management classes. Values: IPCC manure mgmt classes.
IPCC_MANURE_MGMT_AGGREGATION = {
    'liquid': ('Anaerobic lagoon', 'Liquid system'),
    'solid': ('Solid storage', 'Dry lot', 'Other'),
    'unavailable': ('Pasture range paddock', 'Daily spread')
}

MANURE_MGMT_REPLACEMENTS = {
    # Spain reports 100% "Other" which should not be interpreted
    # as 100% solid manure. Replace by Portugal's management system.
    'ES': 'PT'
    }

# A2010         Bovine animals, less than 1 year
# A2010B        Bovine animals, less than 1 year, for slaughter
# A2010C        Bovine animals, less than 1 year, not for slaughter
# A2020         Bovine animals, 1 year
# A2030         Bovine animals, 2 years or over
# A2110C        Male calves, less than 1 year, not for slaughter
# A2120         Male bovine animals, 1 year
# A2130         Male bovine animals, 2 years or over
# A2210C        Female calves, less than 1 year, not for slaughter
# A2220         Heifers, 1 year
# A2220B        Heifers, 1 year, for slaughter
# A2220C        Heifers, 1 year, not for slaughter
# A2230         Heifers, 2 years or over
# A2230B        Heifers, 2 years or over, for slaughter
# A2230C        Heifers, 2 years or over, not for slaughter
# A2230_2330    Female bovine animals, 2 years or over
# A2300         Cows
# A2300F        Dairy cows
# A2300G        Non dairy cows
# A2400         Buffaloes
# A3100         Live swine, domestic species
# A3110         Piglets, less than 20 kg
# A3120         Breeding sows
# A3120K        Covered sows
# A3120KA       Sows covered for the first time
# A3120L        Sows, not covered
# A3120LA       Gilts not yet covered
# A3120_3133    Breeding pigs
# A3131         Pigs, from 20 kg to less than 50 kg
# A3132         Fattening pigs, 50 kg or over
# A3132X        Fattening pigs, from 50 kg to less than 80 kg
# A3132Y        Fattening pigs, from 80 kg to less than 110 kg
# A3132Z        Fattening pigs, 110 kg or over
# A3133         Breeding boars
# A4100         Live sheep
# A4110K        Ewes and ewe-lambs put to the ram
# A4110KC       Milk ewes and ewe-lambs put to the ram
# A4110KD       Non milk ewes and ewe-lambs put to the ram
# A4120         Other sheep
# A4200         Live goats
# A4210K        Goats mated and having already kidded
# A4210KA       Goats mated for the first time
# A4210KB       Goats having already kidded
# A4220         Other goats 
# A5110         Hens
# A5110O        Laying hens
# A5120         Cocks
# A5130         Chicks of chicken
# A5140         Broilers


EF_OLSAAREG_CODES = {
    'A2010': ('C_2_1_HEADS',), # head: Bovine <1 year old - total
    'A2120': ('C_2_2_HEADS',), # head: Bovine 1-<2 years - males
    'A2220': ('C_2_3_HEADS',), # head: Bovine 1-<2 years - females
    'A2130': ('C_2_4_HEADS',), # head: Bovine 2 years and older - males
    'A2230': ('C_2_5_HEADS',), # head: Heifers, 2 years and older
    'A2300G': ('C_2_99_HEADS',), # head: Other cows, bovine 2 years old and over
    'A2300F': ('C_2_6_HEADS',), # head: Dairy cows
    'A4100': ('C_3_1_HEADS',), # head: Sheep - total
    'A3120': ('C_4_2_HEADS',), # head: Pigs - breeding sows over 50 kg
    'C_4_99_HEADS': ('C_4_99_HEADS',), # head: Pigs - others
    'A5140': ('C_5_1_1000_HEADS',), # 1000 heads: Poultry - broilers
    'A5110O': ('C_5_2_1000_HEADS',) # 1000 heads: Laying hens
}

EF_OLUAAREG_CODES = {
    'C1120': ('B_1_1_1_HA',), # Common wheat and spelt
    'C1130': ('B_1_1_2_HA',), # Durum wheat
    'C1150': ('B_1_1_3_HA',), # Rye
    'C1160': ('B_1_1_4_HA',), # Barley
    'C1180': ('B_1_1_5_HA',), # Oats
    'C1200': ('B_1_1_6_HA',), # Grain maize
    'C1370': ('B_1_4_HA',), # Sugar beet
    'C1420': ('B_1_6_4_HA',), # Rape and turnip rape
    'C1450': ('B_1_6_5_HA',) # Sunflower seed
}

APRO_CPP_CROP_CODES = {
    'C1120': ('C1120',), # Common wheat and spelt
    'C1130': ('C1130',), # Durum wheat
    'C1150': ('C1150', 'C1140'), # Take "Rye" if not null, otherwise "Rye and maslin"
    'C1160': ('C1160',), # Barley
    'C1180': ('C1180',), # Oats
    'C1200': ('C1201',), # Grain maize and corn cob mix (C1200 is not available)
    'C1370': ('C1370',), # Sugar beet
    'C1420': ('C1420',), # Rape and turnip rape
    'C1450': ('C1450',) # Sunflower seed 
}

# NUTS0 codes to ISO 3166-1 alpha 3 codes
ISO3166_3_TO_NUTS0 = {
'FRA': 'FR',
'SWE': 'SE',
'DEU': 'DE',
'LTU': 'LT',
'GRC': 'EL',
'HRV': 'HR',
'LVA': 'LV',
'BGR': 'BG',
'MLT': 'MT',
'ROU': 'RO',
'EST': 'EE',
'GBR': 'UK',
'ESP': 'ES',
'CYP': 'CY',
'FIN': 'FI',
'DNK': 'DK',
'NLD': 'NL',
'PRT': 'PT',
'CZE': 'CZ',
'POL': 'PL',
'HUN': 'HU',
'AUT': 'AT',
'IRL': 'IE',
'SVK': 'SK',
'SVN': 'SI',
'ITA': 'IT',
'LUX': 'LU',
'BEL': 'BE'}


STAT_YEARS = [2009, 2010, 2011]

NUTS = nuts.NUTS('outdata/NUTS_2010.xls')

MAPS = {
    'liquid': [
        ('glw_cattle', 'liquid'),
        ('glw_pigs', 'liquid'),
        ('glw_chickens', 'liquid')],
    'solid': [
        ('glw_cattle', 'solid'),
        ('glw_pigs', 'solid'),
        ('glw_chickens', 'solid')],
    'residues': 'cropland'
}

CROPLAND_WEIGHTS = defaultdict(float, {
    12: 1, #Non-irrigated arable land
    13: 1, #Permanently irrigated land
    14: 0, #Rice fields
    15: 0, #Vineyards
    16: 0, #Fruit trees and berry plantations
    17: 0, #Olive groves
    18: 0, #Pastures
    19: 0.5, #Annual crops associated with permanent crops
    20: 0.5, #Complex cultivation patterns
    21: 0.5, #Land principally occupied by agriculture with significant areas of natural vegetation
    22: 0, #Agro-forestry areas
})

WATER_WEIGHTS = defaultdict(float, {
    40: 1, #Water courses
    41: 1, #Water bodies
    42: 1, #Coastal lagoons
    43: 1, #Estuaries
    44: 1, #Sea and ocean
    50: 1, #UNCLASSIFIED WATER BODIES
})

NUTS_LEVEL = defaultdict(lambda: 2, {'DE': 1, 'MT': 'exclude'})
