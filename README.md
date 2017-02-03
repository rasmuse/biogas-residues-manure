# Biogas from manure and crop residues

## Instructions

1. Install [gdal 2.0.2](https://trac.osgeo.org/gdal/wiki/DownloadSource) and [jq 1.5](https://stedolan.github.io/jq/).

2. Using Python 3.4, and preferrably in a virtualenv, do this (`editable` is optional, but useful if you want to change the code):
    
    ```
    pip install --editable .
    ```

3. Obtain the indata (see below).

4. Work in the root directory of the git repository:

    ```
    cd ~/path/to/biogas-residues-manure/
    ```

    If you don't want to work there, that's fine too, but you have to copy out the `sampling-settings/` directory and the `Makefile`:

    ```
    cp -r sampling-settings Makefile ~/my/working/directory
    ```

    (`sampling-settings/` and `Makefile` should sit in the same directory as `indata/`)

5. `make preparations` (This may take a while.)

    If you are low on disk space, you can remove the whole `outdata/temp` directory after this step.

6. `make sample` (This may take a long while, depending on your sampling settings.)

    You may want to use other sampling settings than the defaults. If so, take a copy of `sampling-settings/default` to some other name `sampling-settings/custom-settings`. Then run `make sample SAMPLING=custom-settings`.

7. At this point you should be able to `import biogasrm.substrates` and use all the functions in there. Make sure you are in your working directory, because otherwise the importing will fail because necessary files are not found.

    You can also try e.g.

    ```
    biogasrm-substrates make_raster -b DM cropland straw straw.tif
    ```


## Data

The needed data is described below. After obtaining all the necessary files, put them in the following structure (in some working directory you like)

```
indata/
    CLC/
        g250_06.zip
    Eurostat/
        agr_r_animal.tsv.gz
        agr_r_crops.tsv.gz
        apro_cpp_crop.tsv.gz
        ef_olsaareg.tsv.gz
        ef_oluaareg.tsv.gz
        NUTS_2010.zip
        NUTS_2010_03M_SH.zip
    GLW/
        ASCattle1km_AD_2010_GLW2_01_TIF.zip
        AS_Chickens1km_AD_2010_v2_01_TIF.zip
        AS_Pigs1km_AD_2010_GLW2_01_TIF.zip
        EUCattle1km_AD_2010_GLW2_01_TIF.zip
        EU_Chickens1km_AD_2010_v2_01_TIF.zip
        EU_Pigs1km_AD_2010_GLW2_01_TIF.zip
    NIRs/
        aut-2014-crf-14apr.zip
        bel-2014-crf-13sep.zip
        ...
        ...
        ...
```

### NUTS

NUTS is the nomenclature of territorial units for statistics used by the EU.

For the residues software we need polygons describing the NUTS regions, which are [available in various resolutions here](http://ec.europa.eu/eurostat/c/portal/layout?p_l_id=6033084&p_v_l_s_g_id=0). Specifically, the residues software expects a Shapefile, and our default setting is the 1:3 million scale for 2010, called [NUTS_2010_03M_SH.zip](http://ec.europa.eu/eurostat/cache/GISCO/geodatafiles/NUTS-2013-03M-SH.zip). The program will probably work with other resolutions and years too.

You will also need [an Excel file with metadata about the NUTS regions](http://ec.europa.eu/eurostat/ramon/documents/nuts/NUTS_2010.zip).


### Corine Land Cover 2006

Corine Land Cover (CLC) is a raster dataset with land cover in Europe, based on interpretation of satellite images. We are developing the residues software with the 250x250 meters raster version of CLC2006, available [here](http://www.eea.europa.eu/data-and-maps/data/ds_resolveuid/a47ee0d3248146908f72a8fde9939d9d). You might also want to read the [technical guidelines from EEA](http://www.eea.europa.eu/publications/technical_report_2007_17).

There is also a 100x100 m resolution version of CLC2006 which will probably work well too (but with significantly longer computational time). The raster resolution is not hard coded anywhere, so it should be straightforward to change the input data.

### Gridded Livestock of the World 2

Gridded Livestock of the World (GLW) is a model-based estimation of livestock densities in the whole world. The map is based on national and subnational statistics and further disaggregated using a statistical model taking into account a number of prediction variables describing climate, vegetation, topography and demographics. GLW version 2 reports estimated livestock densities in a raster with pixels about 1 km² large. Please visit the [Livestock Geo-Wiki](http://www.livestock.geo-wiki.org/) for more information.

We are currently using GLW 2.01, available at the [FAO GeoNetwork](http://www.fao.org/geonetwork/srv/en/main.home). Search for ``gridded livestock 2014`` or use the following URLs:

* http://www.fao.org/geonetwork/srv/en/resources.get?id=47949&fname=EUCattle1km_AD_2010_GLW2_01_TIF.zip&access=private
* http://www.fao.org/geonetwork/srv/en/resources.get?id=47949&fname=ASCattle1km_AD_2010_GLW2_01_TIF.zip&access=private
* http://www.fao.org/geonetwork/srv/en/resources.get?id=48052&fname=EU_Pigs1km_AD_2010_GLW2_01_TIF.zip&access=private
* http://www.fao.org/geonetwork/srv/en/resources.get?id=48052&fname=AS_Pigs1km_AD_2010_GLW2_01_TIF.zip&access=private
* http://www.fao.org/geonetwork/srv/en/resources.get?id=48051&fname=EU_Chickens1km_AD_2010_v2_01_TIF.zip&access=private
* http://www.fao.org/geonetwork/srv/en/resources.get?id=48051&fname=AS_Chickens1km_AD_2010_v2_01_TIF.zip&access=private


### Eurostat agricultural statistics

We also use agricultural statistics from Eurostat, supplied as tab separated data from Eurostat's bulk download facility. You find it at http://ec.europa.eu/eurostat/estat-navtree-portlet-prod/BulkDownloadListing. Browse to `[data]` and download the following files:

* [agr_r_crops.tsv.gz](http://ec.europa.eu/eurostat/estat-navtree-portlet-prod/BulkDownloadListing?sort=1&file=data%2Fagr_r_crops.tsv.gz)
* [agr_r_animal.tsv.gz](http://ec.europa.eu/eurostat/estat-navtree-portlet-prod/BulkDownloadListing?sort=1&file=data%2Fagr_r_animal.tsv.gz)
* [ef_olsaareg.tsv.gz](http://ec.europa.eu/eurostat/estat-navtree-portlet-prod/BulkDownloadListing?sort=1&file=data%2Fef_olsaareg.tsv.gz)
* [ef_oluaareg.tsv.gz](http://ec.europa.eu/eurostat/estat-navtree-portlet-prod/BulkDownloadListing?sort=1&file=data%2Fef_olsaareg.tsv.gz)
* [apro_cpp_crop.tsv.gz](http://ec.europa.eu/eurostat/estat-navtree-portlet-prod/BulkDownloadListing?sort=1&file=data%2Fapro_cpp_crop.tsv.gz)

**Update 3 February 2017:** It seems like Eurostat has removed some of the datasets. The needed files are now also hosted in this repo until I know what can be done about this.

### National Inventory Reports

We have used the 2014 NIR submissions for years 2009--2011, so to reproduce the results you'll need those. Download the CRF zip files for all EU28 countries.

http://unfccc.int/national_reports/annex_i_ghg_inventories/national_inventories_submissions/items/8108.php
