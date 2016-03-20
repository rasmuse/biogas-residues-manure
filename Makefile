arg2 = $(word 2,$^)
arg3 = $(word 3,$^)

.SECONDARY: # to save intermediate results

DENSITIES = glw_cattle glw_pigs glw_chickens cropland
REQUIRE_COVERAGE = temp/glw_cattle_or_water temp/glw_chickens_or_water temp/glw_pigs_or_water cropland
COVERAGE_FILES = $(foreach cov,$(REQUIRE_COVERAGE),outdata/temp/coverage/$(cov).json)
EUROSTAT_TABLES = agr_r_animal agr_r_crops apro_cpp_crop ef_olsaareg ef_oluaareg

# PREPARATIONS

outdir:
	mkdir -p outdata/temp

outdata/clc.tif: indata/CLC/g250_06.zip
	unzip -o indata/CLC/g250_06.zip g250_06.tif -d outdata/temp
	touch outdata/temp/g250_06.tif
	mv outdata/temp/g250_06.tif $@

outdata/temp/NUTS.geojson: indata/Eurostat/NUTS_2010_03M_SH.zip outdata/clc.tif
	unzip -o $< -d outdata/temp
	ogr2ogr -t_srs `rio info outdata/clc.tif --crs` -f GeoJSON $@ outdata/temp/NUTS_2010_03M_SH/Data/NUTS_RG_03M_2010.shp

outdata/NUTS_2010.xls: indata/Eurostat/NUTS_2010.zip
	unzip -o $< -d $(@D)
	touch $@

outdata/temp/cattle_europe_orig.tif: indata/GLW/EUCattle1km_AD_2010_GLW2_01_TIF.zip
	unzip -o $< -d outdata/temp
	mv outdata/temp/EU_Cattle1km_AD_2010_v2_1.tif $@
	touch $@

outdata/temp/cattle_asia_orig.tif: indata/GLW/ASCattle1km_AD_2010_GLW2_01_TIF.zip
	unzip -o $< -d outdata/temp
	mv outdata/temp/AS_Cattle1km_AD_2010_v2_1.tif $@
	touch $@

outdata/temp/pigs_europe_orig.tif: indata/GLW/EU_Pigs1km_AD_2010_GLW2_01_TIF.zip
	unzip -o $< -d outdata/temp
	mv outdata/temp/EU_Pigs1km_AD_2010_GLW2_01.tif $@
	touch $@

outdata/temp/pigs_asia_orig.tif: indata/GLW/AS_Pigs1km_AD_2010_GLW2_01_TIF.zip
	unzip -o $< -d outdata/temp
	mv outdata/temp/AS_Pigs1km_AD_2010_GLW2_01.tif $@
	touch $@

outdata/temp/chickens_europe_orig.tif: indata/GLW/EU_Chickens1km_AD_2010_v2_01_TIF.zip
	unzip -o $< -d outdata/temp
	mv outdata/temp/EU_Chickens1km_AD_2010_v2_01.tif $@
	touch $@

outdata/temp/chickens_asia_orig.tif: indata/GLW/AS_Chickens1km_AD_2010_v2_01_TIF.zip
	unzip -o $< -d outdata/temp
	mv outdata/temp/AS_Chickens1km_AD_2010_v2_01.tif $@
	touch $@

outdata/temp/%_warped.tif: outdata/temp/%_orig.tif outdata/clc.tif
	(rio warp $< $@ --like $(arg2) --co TILED=YES && rm $<) || rm $@

outdata/glw_%.tif: outdata/temp/%_europe_warped.tif outdata/temp/%_asia_warped.tif
	rio merge -f $^ $@

outdata/cropland.tif: outdata/clc.tif
	biogasrm-prep cropland $< $@

outdata/temp/water.tif: outdata/clc.tif
	biogasrm-prep water $< $@

outdata/temp/NIRs/: indata/NIRs/
	mkdir -p $(@D)
	find $< -name "*.zip" -exec unzip -o {} -d $@ \;

outdata/temp/%_or_water.tif: outdata/%.tif outdata/temp/water.tif
	rio merge -f $^ $@

outdata/temp/coverage/%.json: outdata/%.tif outdata/temp/NUTS.geojson
	mkdir -p $(@D)
	biogasrm-prep coverage $< $(arg2) --key-property NUTS_ID > $@ || rm $@

all_coverage: $(COVERAGE_FILES)

outdata/eurostat/%.pkl: indata/Eurostat/%.tsv.gz
	mkdir -p $(@D)
	(gunzip $< -k -c > outdata/temp/eurostat_temp && \
	biogasrm-prep read_eurostat outdata/temp/eurostat_temp > $@) || rm $@
	rm outdata/temp/eurostat_temp

all_eurostat: $(foreach n,$(EUROSTAT_TABLES),outdata/eurostat/$(n).pkl)

outdata/manure_mgmt.pkl: outdata/temp/NIRs/
	biogasrm-prep manure_mgmt $< > $@ || rm $@

outdata/animal_pop.pkl: outdata/eurostat/ef_olsaareg.pkl
	biogasrm-prep animal_pop $^ > $@ || rm $@

outdata/included_NUTS.geojson: outdata/temp/NUTS.geojson all_coverage \
	all_eurostat outdata/manure_mgmt.pkl outdata/animal_pop.pkl
	biogasrm-prep included_nuts -o $@ $< $(COVERAGE_FILES)

outdata/regional_sums/%.json: outdata/%.tif outdata/included_NUTS.geojson
	mkdir -p $(@D)
	rio zonalstats $(arg2) --stats sum -r $< \
	| jq '[.features[].properties]' \
	| jq 'map(select(._sum | type | . == "number"))' \
	| jq 'map({(.NUTS_ID): ._sum}) | add' > $@

all_regional_sums: $(foreach raster,$(DENSITIES),outdata/regional_sums/$(raster).json)

preparations: outdir outdata/NUTS_2010.xls all_regional_sums all_eurostat \
	outdata/manure_mgmt.pkl outdata/animal_pop.pkl

# END PREPARATIONS


# SAMPLING

SAMPLING = default

outdata/sampling/$(SAMPLING)/samples.shp: outdata/included_NUTS.geojson sampling-settings/$(SAMPLING)
	rm -rf $(@D)
	mkdir -p $(@D)
	biogasrm-sample disks $< $@ `cat $(arg2)`

outdata/sampling/$(SAMPLING)/%_fracs.pkl: \
	outdata/sampling/$(SAMPLING)/samples.shp outdata/%.tif outdata/regional_sums/%.json

	biogasrm-sample sample_region_fracs $^ $@

sample: preparations $(foreach raster,$(DENSITIES),outdata/sampling/$(SAMPLING)/$(raster)_fracs.pkl)

# END SAMPLING

