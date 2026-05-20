
# Data needed to reproduce the code

The data used in this study is only partially open available. 
We here give an overview of which data was used for which processing step and where it can be accessed - if necessary after signing a license agreement.

## Administrative units needes:

* **Germany:**
  * Core states: BW, RP
  * 20 km buffer: + HE
* **France:**
  * Core departements: 57, 67
  * 20 km buffer: + 54, 68, 88

## 01 Area definition

### 01a Get isochrones

#### Central Points:

* manually created as point in city center
* the points used are provided as [central_points.gpkg](B2_procdata/01_AreaDefinition/central_points.gpkg)
* location: `B2_procdata/01_AreaDefinition/central_points.gpkg`

### 01b Community Selector based on Threshold value

#### Municipalities:

* **Germany:**
  * layer with all German municipalities
  * source: [Bundesamt für Kartographie und Geodäsie (BKG), 2023: Verwaltungsgebiete 1 : 25 000 (VG25) Deutschland 2021](https://gdz.bkg.bund.de/index.php/default/digitale-geodaten/verwaltungsgebiete/verwaltungsgebiete-1-25-000-stand-31-12-vg25.html) © BKG (2022) CC BY 4.0, [Datenquellen](https://sgx.geodatenzentrum.de/web_public/gdz/datenquellen/datenquellen_vg25.pdf)
  * location: `A_basedata/DE/GEMEINDEN/VG25_GEM.shp`
  
* **France:**
  * layer with all French municipalities
  * source: [Institut national de l’information géographique et forestière (IGN), 2025: ADMIN-EXPRESS édition Octobre 2025 par territoire France Métropolitaine](https://geoservices.ign.fr/adminexpress)
    * version used: [2025-10-15 (download link)](https://data.geopf.fr/telechargement/download/ADMIN-EXPRESS/ADMIN-EXPRESS_4-0__GPKG_LAMB93_FXX_2025-10-15/ADMIN-EXPRESS_4-0__GPKG_LAMB93_FXX_2025-10-15.7z)
  * location: `A_basedata/FR/ADMIN-EXPRESS_4-0__GPKG_LAMB93_FXX_2025-10-15/`

## 00 Harmonisation

### 00b 01 Addresses

#### Addresses:

* **Germany:**
  * csv file per state
  * source: [BKG, 2024: Georeferenzierte Adressdaten (GA).](https://gdz.bkg.bund.de/index.php/default/georeferenzierte-adressdaten-ga.html) © GeoBasis-DE / BKG (2024), [Datenquellen](https://sg.geodatenzentrum.de/web_public/gdz/datenquellen/datenquellen_ga.pdf), [Nutzungsbedingungen](https://sg.geodatenzentrum.de/web_public/gdz/lizenz/deu/nutzungsbedingungen_hk-de.pdf)
  * location: `A_basedata/DE/Adressdaten/`
  
* **France:**
  * csv file per departement
  * source: IGN, 2024: [Base Adresse Nationale (BAN). Export du mercredi 13 novembre 2024.](https://adresse.data.gouv.fr/data/ban/adresses/2024-11-13/csv)
  * location: `A_basedata/FR/addresses-<dep>.csv/addresses-<dep>.csv`

### 00b 02 Buildings

#### Buildings

* **Germany:**
  * layer with building parts per state
  * source: BKG, 2020: [3D-Gebäudemodelle LoD2 Deutschland (LoD2-DE).](https://gdz.bkg.bund.de/index.php/default/digitale-geodaten/sonstige-geodaten/3d-gebaudemodelle-lod2-deutschland-lod2-de.html)  © GeoBasis-DE / BKG (2021)
  * location: `A_basedata/DE/GEBÄUDE/<state>/<state>_lod2020_parts.gpkg`
  * script `00b_02_01_loadfromserver_DE.R` converts from gdb to gpkg
  
* **France:**
  * shapefile per departement
  * source: IGN, 2021: [BD TOPO® 2021 Tous Thèmes par département format Shapefile projection légale.](https://geoservices.ign.fr/bdtopo#telechargementshpdep2021)
  * location: `A_basedata/FR/BDTOPO_3-0_TOUSTHEMES_SHP_LAMB93_D0<dep>_2021-03-15/.../BATI/BATIMENT.shp`
      * script `00b_02_02a` uses shapefile but `00d` uses gpkg -> recommended to also change to gpkg here

* **OSM:**
  * layer containing all OSM buildings in the study area + 20 km buffer
  * source: OpenStreetMap Contributors, 2024: [Building polygons (Geofabrik shapefile extract, 28-07-2024.)](https://download.geofabrik.de/) © OpenStreetMap contributors. Licensed under ODbL 1.0.
      * layer: `gis_osm_buildings_a_free_1.shp`
  * location: `B2_procdata/00_Harmonisation/00b_02_buildings/00b_02_04a_OSM_merged_BW_RP_HE_FR_20km.gpkg`  (merged and clipped manually)
  
#### Departements

* **France:**
  * shapefile with all departements
  * source: IGN, 2021: [BD TOPO® 2021 Tous Thèmes par département format Shapefile projection légale.](https://geoservices.ign.fr/bdtopo#telechargementshpdep2021)
      * using `DEPARTEMENT.shp` from departement 67 (has all other departements because they are adjacent))
  * location: `A_basedata/FR/BDTOPO_3-0_TOUSTHEMES_SHP_LAMB93_D067_2021-03-15/.../ADMINISTRATIF/DEPARTEMENT.shp`

### 00c Parcels

#### Parcels

* **Germany:**
  * folder per state with zip file per municipality 
  * source: BKG, 2022: [Flurstücksinformationen Deutschland (FS-DE).](https://gdz.bkg.bund.de/index.php/default/digitale-geodaten/sonstige-geodaten/flurstuecksinformationen-deutschland-fs-de.html) © GeoBasis-DE / BKG (2023) 
  * location: `A_basedata/DE/FLURSTÜCKE/{state}/{ags_name}.zip`
  
* **France:**
  * shapefile per departement
  * source: Direction Interministérielle du Numérique (DINUM), 2024: [Cadastre Etalab. Parcelles. ](https://cadastre.data.gouv.fr/datasets/cadastre-etalab)
      * version used: [2024-10-01](https://cadastre.data.gouv.fr/data/etalab-cadastre/2024-10-01/shp/departements/)
  * location: `A_basedata/FR/cadastre-<dep>-parcelles-shp/parcelles.shp`

### 00d Streets

#### Streets

* **Germany:**
  * 2-4 shapefiles per state
  * source: BKG, 2022: [Digitales Basis-Landschaftsmodell (Basis-DLM).](https://gdz.bkg.bund.de/index.php/default/digitale-geodaten/digitale-landschaftsmodelle/digitales-basis-landschaftsmodell-ebenen-basis-dlm-ebenen.html) © GeoBasis-DE / BKG (2023)
  * location: `A_basedata/DE/STRASSEN/{state}/`
    * layers: `ver01_l.shp`, `ver02_l.shp` (streets), `gew01_l.shp`, `gew03_l.shp` (rivers)

* **France:**
  * 5-7 layers per departement 
  * source: IGN, 2021: [BD TOPO® 2021 Tous Thèmes par département format GeoPackage projection légale.](https://geoservices.ign.fr/bdtopo#telechargementgpkgdep2021)
  * location: `A_basedata/FR/BDTOPO_3-0_TOUSTHEMES_GPKG_LAMB93_D0<dep>_2021-03-15/.../BDT_3-0_GPKG_LAMB93_D0<dep>-ED2021-03-15.gpkg`
    * layers: `itineraire_autre`, `route_numerotee_ou_nommee`, `troncon_de_route`, `troncon_de_voie_ferree`, `voie_ferree_nommee` (streets), `troncon_hydrographique`, `cours_d_eau` (rivers)

### 00e Corine

* layer with vector land cover for complete study area
* source: European Environmental Agency (EEA), 2020: [CORINE Land Cover 2018 (vector), Europe, 6-yearly – version 2020_20u1. Copernicus Land Monitoring Service](https://doi.org/10.2909/71c95a07-e296-44fc-b22b-415f42acfdf0)
* location: `A_basedata/EU/Corine/clc2018/corine_2018.gdb`
    * layer: `clc18_all`

## 02 Development Block Identification

* only needs data harmonisation outputs

## 03 Building Type Identification

### 03 01 Prepare building metrics

#### List of residential functions:

* csv table of building function with information if the function is residential
* the table used is provided as [03_01b_list_residential.csv](B2_procdata/03_BuildingTypeIdentification/03_01b_list_residential.csv)
* location: `B2_procdata/03_BuildingTypeIdentification/03_01b_list_residential.csv`

### 03 02 Training data

#### Training data

* manually created training data set of building polygons
* geometries do not need to be identical with building metrics data set, the training data will be mapped to our buildings
* the script draws a subset with equal distributions over regions and types
* our training data is provided as [03_02_trainingdata.gpkg](B2_procdata/03_BuildingTypeIdentification/03_02_trainingdata.gpkg)
* location: `B2_procdata/03_BuildingTypeIdentification/03_02_trainingdata.gpkg`

#### Building types

* .csv table of building types and descriptions
* the training data we have was created using different classification systems, the table unifies them into one.
* we have changed the classification system throughout the process, the new one was added to the table as v2 and the script takes and writes a version number for this step; that makes sense to avoid confusion what type system a data set refers to 
* our table is provided here: [03_02_trainingsdaten_old_to_ref12.csv](B2_procdata/03_BuildingTypeIdentification/03_02_trainingsdaten_old_to_ref12.csv)
* location: `B2_procdata/03_BuildingTypeIdentification/03_02_trainingsdaten_old_to_ref12.csv`


# 04 Block Age 

#### Building age

* raster layer with dominant building ages for France and Germany
* source: Uhl, J.H., Politis, P. and Pesaresi, M. (2025): [GHS-AGE R2025A – Global gridded estimates of the dominant age of the built stock (1975-2020). European Commission, Joint Research Centre (JRC) (Dataset)](http://data.europa.eu/89h/d503bb56-9884-4e4d-bb8f-d86711d9f749)
* location: `A_basedata/EU/GHSL/GHS_AGE_GLOBE_R2025A_54009_V1_0/GHS_AGE_1975052020_GLOBE_R2025A_54009_100_V1_0.tif`

#### Validation data

* manually created validation data set using historic satellite imagery and French [Base de Données Nationale des Batiments (BDNB)](https://bdnb.io/) construction year data
* provided as [04_DevBlocks_validation.gpkg](B2_procdata/04_BlockAge_GHSAGE/04_validation/04_DevBlocks_validation.gpkg)
* location: `B2_procdata/04_BlockAge_GHSAGE/04_validation/04_DevBlocks_validation.gpkg`

#### GHS Age table

* .txt file that contains labels and value ranges for extraction
* provided as [ghs_age.txt](B2_procdata/04_BlockAge_GHSAGE/04_ghs_age/ghs_age.txt)
* also readable by QGIS for raster visualisation


# 05 Accessibility Analysis

#### Population data

* raster layer with population for France and Germany
* source: Carioli, A., Schiavina, M., MacManus, K. J. and Freire, S. (2023): [GHS-POP R2023A - GHS population grid multitemporal (1975-2030). European Commission, Joint Research Centre (JRC) (Dataset)](http://data.europa.eu/89h/d503bb56-9884-4e4d-bb8f-d86711d9f749)
* location: `A_basedata/EU/GHSL/GHS_POP_E2020_GLOBE_R2023A_54009_100_V1_0_R4_C19/GHS_POP_E2020_GLOBE_R2023A_54009_100_V1_0_R4_C19.tif`