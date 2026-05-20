# Plugin ORS tools needs to be installed

import sys, os
import glob
from PyQt5.QtCore import QVariant
import processing
from qgis.core import *
from datetime import datetime
import traceback
import csv
import geopandas as gpd
import pandas as pd
import logging

now = datetime.now()
print("Start: " + now.strftime("%y/%m/%d/%H:%M:%S"))

# --- PATHS ---
maindir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../'))
worksp = os.path.join(maindir, 'B2_procdata', '05a_AccessibilityAnalysis')

municip_path = os.path.join(worksp, 'A_resultdata', '01_AreaDefinition', '01a_isochrones_20240606.gpkg')
municip_layer = 'isochrones_separated'

# --- PARAMETERS ---
umkreis = 20000
pct = 50
count_nearest_destinations = f'{pct}perc'
grid_space = 1000
crs = 'EPSG:32632'
ew_field = 'EW1'
region_field = "location"
get_matrix = True
reuse_selection = True  # Set True to reuse previous random selection, False to generate new


# --- Reset logging (important in QGIS console) ---
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)

# --- set up logging ---
log_file = os.path.join(worksp, f"run_log_{now.strftime('%y_%m_%d_%H%M%S')}.txt")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_file, mode='w', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)   # optional: still print to console
    ]
)    

logging.info("Start: " + now.strftime("%y/%m/%d/%H:%M:%S"))

# --- READ AND PREPARE DATA ---
municip = gpd.read_file(municip_path).to_crs(crs)
regions = municip.set_index(region_field)

def set_outpaths(region_name):
    date_tag = now.strftime('%y_%m_%d')
    output_folder = os.path.join(worksp, f'output/{region_name}_{count_nearest_destinations}_{date_tag}/')
    matrix_folder = os.path.join(output_folder, 'Matrizen')
    os.makedirs(matrix_folder, exist_ok=True)
    
    point_path = os.path.join(worksp, f'output/osmpoints_mitEWsum_{grid_space}mgrid_{region_name}.gpkg')
    region_buffer = os.path.join(worksp, f'output/buffer/buffer_{region_name}.gpkg')
    points_ew_out_s1 = os.path.join(worksp, f'output/ew_points_{region_name}.gpkg')
    points_ew_out = os.path.join(output_folder, f'{region_name}_new.gpkg')
    extract_file = os.path.join(output_folder, f'random_extract_{region_name}.gpkg')
    destins_10perc_out = os.path.join(output_folder, f'{region_name}_10perc_ew.gpkg')
    destins_out = os.path.join(output_folder, f'destination_points_{grid_space}mgrid_{region_name}{count_nearest_destinations}.gpkg')
    
    return output_folder, matrix_folder, point_path, region_buffer, points_ew_out_s1, points_ew_out, extract_file, destins_10perc_out, destins_out

    
# --- MAIN LOOP ---
for region_name, region in regions.iterrows():
	logging.info(f"\n--- Region: {region_name} ---")

    ## Get paths for this region:
    output_folder, matrix_folder, point_path, region_buffer, points_ew_out_s1, points_ew_out, extract_file, destins_10perc_out, destins_out = set_outpaths(region_name)

    logging.info("Load population points...")
    ew_points = iface.addVectorLayer(points_ew_out_s1, f'ew_points_{region_name}', "ogr")
    ew_points = processing.run("native:createspatialindex", {'INPUT': ew_points})

    ## Extract 50% of points (reduce computation time) 
    logging.info(f"Only keep {pct}% of road network points...")
    if reuse_selection and os.path.exists(extract_file):
        logging.info(f"> Reusing previous random selection for {region_name}...")
        extract = iface.addVectorLayer(extract_file, f'random_extract_{region_name}', 'ogr')
    else:
        logging.info(f"> Generating new random selection for {region_name}...")
        extract = processing.run("native:randomextract", {
            'INPUT': point_path,
            'METHOD': 1,
            'NUMBER': pct,
            'OUTPUT': 'TEMPORARY_OUTPUT'
        })
        extract = processing.runAndLoadResults("native:deleteduplicategeometries", {'INPUT': extract['OUTPUT'], 'OUTPUT': 'TEMPORARY_OUTPUT'})
        # Save the random selection for later reuse
        extract = processing.run("native:savefeatures", {'INPUT': extract['OUTPUT'], 'OUTPUT': extract_file})['OUTPUT']

    ## Get population points sum and add to road points for reduced road data points 
    ## (process like in script 01 but with 50% of points)
    logging.info("Add population data to points...")
    logging.info('> voronoipolygons')
    voronoi = processing.runAndLoadResults("qgis:voronoipolygons", {'INPUT': extract, 'BUFFER': 2, 'OUTPUT': 'TEMPORARY_OUTPUT'})
    logging.info('> joinbylocationsummary')
    voronoi_einw = processing.runAndLoadResults("qgis:joinbylocationsummary", {
        'INPUT': voronoi['OUTPUT'],
        'PREDICATE': [1],
        'JOIN': ew_points['OUTPUT'],
        'JOIN_FIELDS': [ew_field],
        'SUMMARIES': [5],
        'DISCARD_NONMATCHING': False,
        'OUTPUT': 'TEMPORARY_OUTPUT'
    })
    logging.info('> joinattributestable')
    origin_einw = processing.runAndLoadResults("native:joinattributestable", {
        'INPUT': extract,
        'FIELD': 'id',
        'INPUT_2': voronoi_einw['OUTPUT'],
        'FIELD_2': 'id',
        'FIELDS_TO_COPY': [f'{ew_field}_sum_2'],
        'METHOD': 1,
        'DISCARD_NONMATCHING': False,
        'PREFIX': '',
        'OUTPUT': 'TEMPORARY_OUTPUT'
    })
    logging.info('> fieldcalculator')
    points = processing.runAndLoadResults("native:fieldcalculator", {
        'INPUT': origin_einw['OUTPUT'],
        'FIELD_NAME': 'EW_10',
        'FIELD_TYPE': 0,
        'FIELD_LENGTH': 10,
        'FIELD_PRECISION': 3,
        'FORMULA': f' if("{ew_field}_sum_2" < 1,0, "{ew_field}_sum_2" )',
        'OUTPUT': destins_10perc_out
    })
    region_points = QgsProject.instance().mapLayersByName(region_name + '_10perc_ew')[0]
    region_points = processing.run("native:fixgeometries", {'INPUT': region_points, 'METHOD': 1, 'OUTPUT': 'TEMPORARY_OUTPUT'})['OUTPUT']

    logging.info("select destination points")
    destinations_all = processing.runAndLoadResults("native:extractbyexpression", {
        'INPUT': points['OUTPUT'],
        'EXPRESSION': ' "EW_10" >= 5',
        'OUTPUT': destins_out
    })
    
    if get_matrix:
        logging.info('Matrix calculation')
        err = []
        
		# for checking single points: (here point that is not accessible by car that does not get a matrix calculated)
        #point_id_to_run = 8366
        
        for point in region_points.getFeatures():
            point_id = int(point['id'])
            
            #if point_id != point_id_to_run:
            #        continue
            
            logging.info(point_id)

            matrix_out = os.path.join(matrix_folder, f'matrix_{region_name}_{grid_space}mgrid_{point_id}.csv')
            
            # skip existing files if they are not empty (minimum size)
            if (os.path.isfile(matrix_out)) and (os.stat(matrix_out).st_size > 100):
                logging.info(f"Matrix for point {point_id} already exists. Skipping...")
                continue
            
            # Select this specific point as origin
            processing.run("qgis:selectbyattribute", {'INPUT': region_points, 'FIELD': 'id', 'OPERATOR': 0, 'VALUE': point_id, 'METHOD': 0})
            origin = processing.run("native:saveselectedfeatures", {'INPUT': region_points, 'OUTPUT': 'TEMPORARY_OUTPUT'})

            # --- Error handling: ---
            # common error: GenericServerError: 500 ({"error":{"code":6020,"message":"Unable to compute a distance/duration matrix: Search exceeds the limit of visited nodes."}
            # -> journeys through dense city centers are too long and complex 
            # -> split destination points in two layers 
            # simple retries always failed on all attempts 
            # (sometimes the points worked when restarting the script but never with a retry loop directly after fail)

            try:
                matrix_firsttry = processing.run("ORS Tools:matrix_from_layers", {
                    'INPUT_PROVIDER': 1,
                    'INPUT_PROFILE': 0,
                    'INPUT_START_LAYER': origin['OUTPUT'],
                    'INPUT_START_FIELD': 'id',
                    'INPUT_END_LAYER': destinations_all['OUTPUT'],
                    'INPUT_END_FIELD': 'id',
                    'OUTPUT': 'TEMPORARY_OUTPUT'
                })
                
                # QGIS sometimes overwrites merged split files again with an empty file from before 
                # first write Output to temporary file, then save as csv file 
                processing.run("native:savefeatures", {'INPUT':matrix_firsttry['OUTPUT'],'OUTPUT':matrix_out})

                
            except Exception as e:
                logging.info(str(e))
                logging.info("ORS failed, attempting split-mode...")

                #  SPLIT DESTINATION POINTS INTO 2 SUBSETS
                dest_layer = QgsVectorLayer(destinations_all['OUTPUT'], "destsplit", "ogr")
                all_feats = list(dest_layer.getFeatures())
                mid = len(all_feats) // 2
                
                subset1 = QgsVectorLayer("Point?crs="+dest_layer.crs().authid(), "subset1", "memory")
                pr1 = subset1.dataProvider()
                pr1.addAttributes(dest_layer.fields())
                subset1.updateFields()

                subset2 = QgsVectorLayer("Point?crs="+dest_layer.crs().authid(), "subset2", "memory")
                pr2 = subset2.dataProvider()
                pr2.addAttributes(dest_layer.fields())
                subset2.updateFields()

                # fill both subsets
                for f in all_feats[:mid]:
                    pr1.addFeature(f)
                for f in all_feats[mid:]:
                    pr2.addFeature(f)

                subset1.updateExtents()
                subset2.updateExtents()

                # temp file outputs
                temp1 = os.path.join(matrix_folder, f"tmp_{point_id}_A.csv")
                temp2 = os.path.join(matrix_folder, f"tmp_{point_id}_B.csv")

                try:
                    #  TRY MATRIX CALC FOR SUBSET 1
                    processing.run("ORS Tools:matrix_from_layers", {
                        'INPUT_PROVIDER': 1,
                        'INPUT_PROFILE': 0,
                        'INPUT_START_LAYER': origin['OUTPUT'],
                        'INPUT_START_FIELD': 'id',
                        'INPUT_END_LAYER': subset1,
                        'INPUT_END_FIELD': 'id',
                        'OUTPUT': temp1
                    })

                    #  TRY MATRIX CALC FOR SUBSET 2
                    processing.run("ORS Tools:matrix_from_layers", {
                        'INPUT_PROVIDER': 1,
                        'INPUT_PROFILE': 0,
                        'INPUT_START_LAYER': origin['OUTPUT'],
                        'INPUT_START_FIELD': 'id',
                        'INPUT_END_LAYER': subset2,
                        'INPUT_END_FIELD': 'id',
                        'OUTPUT': temp2
                    })

                    #  MERGE BOTH SUBMATRICES → FINAL FILE

                    df1 = pd.read_csv(temp1)
                    df2 = pd.read_csv(temp2)
                    df = pd.concat([df1, df2], ignore_index=True)

                    df.to_csv(matrix_out, index=False)
                    
                    # delete temp files
                    for tmp_file in [temp1, temp2]:
                        if os.path.exists(tmp_file):
                            os.remove(tmp_file)
                    
                except Exception as e:
                    # If still failing after all attempts → log ID
                    logging.info(str(e))
                    logging.info(f"Split mode failed. Adding {point_id} to error list")
                    err.append(point_id)


        logging.info("Building err_points layer...")

        if len(err) > 0:
            logging.info(f"> {len(err)} points failed. Creating error geometry layer.")

            # Create memory table of failed IDs
            failed_ids = QgsVectorLayer("None", "failed_ids", "memory")
            pr = failed_ids.dataProvider()
            pr.addAttributes([QgsField("id", QVariant.Int)])
            failed_ids.updateFields()

            # Add rows with failed IDs
            for i in err:
                feat = QgsFeature()
                feat.setAttributes([i])
                pr.addFeature(feat)

            failed_ids.updateExtents()

            # Join failed IDs to region_points to extract their geometry
            error_points = processing.runAndLoadResults("native:joinattributestable", {
                'INPUT': region_points,
                'FIELD': 'id',
                'INPUT_2': failed_ids,
                'FIELD_2': 'id',
                'FIELDS_TO_COPY': [],
                'METHOD': 1,
                'DISCARD_NONMATCHING': True,
                'PREFIX': '',
                'OUTPUT': os.path.join(output_folder, 'err_points_'+now.strftime('%y_%m_%d')+'.gpkg')
            })

            logging.info("> Saved error points to region folder")

        else:
            logging.info("> No ORS errors detected. No err_points layer created.")
    else:
        logging.info("No matrice calculation.")
    
end = datetime.now()
logging.info('End of script.')
logging.info(f'Runtime: {end - now}')
