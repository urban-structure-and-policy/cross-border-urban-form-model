
# Urban form model for cross-border data harmonisation and regional analysis

The approach for an urban form model described here delivers the basis for the analysis of anticipated outcomes of land policies in Kleiner and Jehling ([2026](https://doi.org/10.1177/23998083261454751)).
Comparing urban form quantitatively is highly valuable for understanding its structures and dynamics. However, making buildings, streets, plots and blocks readable 
across countries is challenging due to extensive preprocessing and harmonisation efforts. 
This repository provides a preprocessing workflow to harmonise administrative data from different countries for modelling urban form, using the examples of France and Germany. 
It includes preprocessing steps for municipalities, parcels, streets, addresses, buildings and an approach for deriving development blocks. 
The result allows for the computation of urban metrics to describe and further analyse urban form on various levels ([Kleiner, Reiter, Jehling (2025)](https://doi.org/10.5194/agile-giss-6-31-2025)).
The repository includes approaches to perform a random forest building type classification, 
an approach to determine the dominant building age for the development blocks and integrates an existing accessibility analysis approach to use on overlapping urban regions.
These further processing steps to include in the urban form model build upon the preprocessing steps but not on each other and can therefore be run independently from each other.

## Workflow

The workflow is divided into six main steps:

* Preprocessing
  * 00 - Harmonisation
  * 01 - Area definition
  * 02 - Development block definition
* Urban form analysis steps (independent steps)
  * 03 - Building type classification
  * 04 - Block age extraction
  * 05 - Accessibility analysis

We start the process with step 01 to select communities as the study area to filter all other data sets to, this helps reducing the computational requirements during the harmonisation steps.
Step 00 takes mainly administrative input data from both countries, filters them to the communities and retains, matches and generates relevant attributes.
Step 02 contains an approach to generate development blocks from the harmonised datasets.
Step 03 uses a random forest classification to determine dominant building types within the blocks.
Step 04 uses the GHS-AGE building age layer to determine the dominant building age within the blocks.
Step 05 uses a Closeness-Centrality approach from [Jehling & Kluwe (2026)](https://doi.org/10.5281/zenodo.19481958) to determine each blocks' relative centrality based on population accessibility.


## Output

### Preprocessing
The main output of the preprocessing (00-02) is a geographic data set of developments blocks in the defined communities.
Development blocks are a spatial aggregation unit of buildings that were developed together.
In the creation and analysis of the urban form model they will be used as an additional analytical level.

Intermediate outputs are geographic datasets of the selected communities (01) and of the harmonised datasets (00)
that will also be used in further analysis.

### Urban form model
The further steps output a copy of the development block dataset each containing additional information value as part of the urban form model.
Information included is:
* Administrative, building and parcel affiliations (preprocessing)
* dominant building type (03)
* dominant building age (04)
* closeness centrality in regards to the dominant urban region (05) 

Additional output:
* building metrics and building type classifications on the building level (03)
* closeness centrality raster layer for each of the urban regions (05)


## Getting started

The purpose of this repository is to provide the code for review and documentation. 
As some of the data for reproducing the whole process is not open accessible, possibilites for running the workflow are limited.

### Input data

The process uses several datasources of which not all are openly available. Data that was created for the project like training and validation data is included in [B2_procdata](B2_procdata/).
More information on input data is provided in [data_input.md](data_input.md).

### Prerequisites

The workflow uses [R](https://www.r-project.org/) and [Python](https://www.python.org/) as well as Python from a [QGIS](https://qgis.org/) install.
Further, an API and a local instance of [OpenRouteService](https://openrouteservice.org/) is needed.
Details on the software used can be found in [software_used.md](software_used.md).

Before running: 
* ORS:
  * Set up your own OpenRouteService instance. See details here: https://giscience.github.io/openrouteservice/run-instance/
  * Install ORSTools QGIS Plugin: https://github.com/GIScience/orstools-qgis-plugin 
  * Set your local instance as provider for the plugin in [B_workflow.Rmd](B1_code/B_workflow.Rmd) ##01a
* QuickOSM:
  * Install QuickOSM QGIS Plugin: https://quickosm.github.io/QuickOSM/
* Conda:
  * Step 03_01

### Description of the code

The file [B_workflow.Rmd](B1_code/B_workflow.Rmd) gives an overview on the processing steps and describes them in detail. For some processing steps, minimal configurations need to be specified. They are located at the respective location in the workflow where the child script is called. 
Almost all processing steps can be run directly form the workflow script. Only steps 05a.01 and 05a.02 need to be run from the QGIS Python console.

The directory structure is expected to be like this:

    maindir/
        A_basedata/
        A_resultdata/
        (A_resultdata_test/)
        B_procdata_code/ (main)
            B1_code/
              B_workflow.Rmd
            B2_procdata/
            (B2_procdata_test/)

Within each directory of resultdata, procdata and code, the code expects or creates a subfolder structure like:

    datadir/
        00_Harmonisation/
            00b_01_addresses/
            00b_02_buildings/
            00c_parcels/
            00d_streets/
            00e_corine/
        01_AreaDefinition/
        02c_DevelopmentBlockIdentification/
        03_BuildingTypeIdentification/
        04_BlockAge_GHSAGE/
        05a_AccessibilityAnalysis
        
        
