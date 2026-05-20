import os, sys, glob
from datetime import datetime
from PyQt5.QtCore import QVariant
from qgis.core import *
import processing
import geopandas as gpd

now = datetime.now()
print("Start:", now.strftime("%H:%M:%S"))

# --- PATHS ---
maindir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../'))
worksp = os.path.join(maindir, 'B2_procdata', '05a_AccessibilityAnalysis')

municip_path = os.path.join(worksp, 'A_resultdata', '01_AreaDefinition', '01a_isochrones_20240606.gpkg')
municip_layer = 'isochrones_separated'
zensus = os.path.join(worksp, 'A_basedata', 'EU', 'GHSL', 'GHS_POP_E2020_GLOBE_R2023A_54009_100_V1_0_R4_C19', 'GHS_POP_E2020_GLOBE_R2023A_54009_100_V1_0_R4_C19.tif')

# --- PARAMETERS ---
umkreis = 20000  # buffer in meters, set to same value as in next scripts
crs = 'EPSG:32632'  # Make sure all files are in or transformed to this CRS
pct = 50
count_nearest_destinations = f'{pct}perc'
grid_space = 1000
ew_field = 'EW1'
region_field = "location"
zensus_geomtype = "Raster"  # 'Point', 'Polygon' or 'Raster'

# also adjust file paths below

# --- FOLDER SETUP ---
required_folders = [
    'input/OSM',
    'output',
    'output/buffer'
]

for folder in required_folders:
    full_path = os.path.join(worksp, folder)
    os.makedirs(full_path, exist_ok=True)

# --- FILE INPUTS ---
if not os.path.exists(municip_path):
    raise FileNotFoundError(f"Missing file: {municip_path}")
if not os.path.exists(zensus):
    raise FileNotFoundError(f"Missing file: {zensus}")

# --- READ AND PREPARE DATA ---
municip = gpd.read_file(municip_path, layer = municip_layer).to_crs(crs)
regions = municip.set_index(region_field)
buffer = regions.copy()
buffer.geometry = regions.buffer(umkreis)


# function to run for each region to get their file paths
def set_outpaths(region_name):
    date_tag = now.strftime('%y_%m_%d')
    output_folder = os.path.join(worksp, f'output/{region_name}_{count_nearest_destinations}_{date_tag}/')
    matrix_folder = os.path.join(output_folder, 'Matrizen')
    os.makedirs(matrix_folder, exist_ok=True)

    buffer_out = os.path.join(worksp, f'output/buffer/buffer_{region_name}.gpkg')
    points_out = os.path.join(worksp, f'output/osmpoints_{grid_space}mgrid_{region_name}.gpkg')
    points_ew_out = os.path.join(worksp, f'output/ew_points_{region_name}.gpkg')
    points_out_2 = os.path.join(worksp, f'output/osmpoints_mitEWsum_{grid_space}mgrid_{region_name}.gpkg')
    return output_folder, matrix_folder, buffer_out, points_out, points_ew_out, points_out_2


# function to run for each region to get their bounding box to only extract OSM data for this 
def get_bbox(region):
    bounds = region.geometry.bounds
    return f"{bounds[0]},{bounds[2]},{bounds[1]},{bounds[3]} [{crs}]"
	
# function to retry overpass API request when gateway timeout happens
def run_with_retry(alg, params, retries=5, backoff=2):
    for attempt in range(1, retries + 1):
        try:
            return processing.run(alg, params)
        except Exception as e:
            if "Gateway Timeout" not in str(e):
                raise  # real error, not Overpass
            if attempt == retries:
                print(f"Giving up on {params['URL']}")
                return None
            sleep = backoff ** attempt
            print(f"Overpass timeout, retrying in {sleep}s...")
            time.sleep(sleep)

# --- MAIN LOOP ---
for region_name, region in regions.iterrows():
    print("\n--- Region:", region_name, "---")
    
    # get paths, buffer and bbox for this region
    output_folder, matrix_folder, buffer_out, points_out, points_ew_out, points_out_2 = set_outpaths(region_name)
	
    buffer.loc[[region_name]].to_file(buffer_out, driver="GPKG")
    bbox = get_bbox(region)
    
    
    print(datetime.now(), 'Download OSM Data...')
    
    # send query to overpass API to get road data
    alg_params = {
        'EXTENT': bbox,
        'KEY': 'highway',
        'SERVER': 'https://lz4.overpass-api.de/api/interpreter',
        'TIMEOUT': 600,  # 10 minutes
        'VALUE': ''
    }
    query = processing.run('quickosm:buildqueryextent', alg_params)
    osm_path = os.path.join(worksp, f'input/OSM/{region_name}_roh.osm')
    file = run_with_retry("native:filedownloader", {'URL': query['OUTPUT_URL'], 'OUTPUT': osm_path})
    if file is None:
        print(f"Skipping {region_name}: could not download.")
        continue  # skip to next region
    else:
        print(f"Downloaded region {region_name}.")
		
    vlayer = iface.addVectorLayer(file['OUTPUT'] + '|layername=lines', "highway_OSM", "ogr")
    vlayer.removeSelection()

    # select only specified road types 
    print(datetime.now(), 'Filter roads...')
    processing.run("qgis:selectbyexpression", {
        'INPUT': vlayer,
        'EXPRESSION': ''' "highway" IN (
            'motorway','trunk','primary','secondary','tertiary','unclassified',
            'residential','motorway_link','trunk_link','primary_link','secondary_link',
            'tertiary_link','living_street','service') AND "other_tags" NOT LIKE '%"access"=>"private"%' ''',
        'METHOD': 0
    })

    highways = processing.run("native:saveselectedfeatures", {'INPUT': vlayer, 'OUTPUT': 'TEMPORARY_OUTPUT'})

    # Create grid with specified width
    print(datetime.now(), 'Raster points for road network...')
    grid = processing.run("native:creategrid", {
        'TYPE': 4, 'EXTENT': bbox, 'HSPACING': grid_space, 'VSPACING': grid_space,
        'HOVERLAY': 0, 'VOVERLAY': 0, 'CRS': QgsCoordinateReferenceSystem(crs), 'OUTPUT': 'TEMPORARY_OUTPUT'
    })
    
    # Get centroid of each grid cell
    points = processing.run("native:centroids", {'INPUT': grid['OUTPUT'], 'ALL_PARTS': False, 'OUTPUT': 'TEMPORARY_OUTPUT'})
    join = processing.run("native:joinbynearest", {
        'INPUT': points['OUTPUT'], 'INPUT_2': highways['OUTPUT'],
        'FIELDS_TO_COPY': [], 'DISCARD_NONMATCHING': False, 'PREFIX': '',
        'NEIGHBORS': 1, 'MAX_DISTANCE': grid_space / 2, 'OUTPUT': 'TEMPORARY_OUTPUT'
    })

    # Move centroid to closest point on the road network
    pointsfromhighways = processing.run("native:geometrybyexpression", {
        'INPUT': join['OUTPUT'], 'OUTPUT_GEOMETRY': 2, 'WITH_Z': False, 'WITH_M': False,
        'EXPRESSION': 'make_point("nearest_x", "nearest_y")', 'OUTPUT': 'TEMPORARY_OUTPUT'
    })
    
    # Clip points to region buffer
    c = processing.run("native:clip", {'INPUT': pointsfromhighways['OUTPUT'], 'OVERLAY': buffer_out, 'OUTPUT': 'TEMPORARY_OUTPUT'})
    
    # Clean geometries
    points = processing.run("native:multiparttosingleparts", {'INPUT': c['OUTPUT'], 'OUTPUT': 'TEMPORARY_OUTPUT'})
    points_single = processing.run("native:deleteduplicategeometries", {'INPUT': points['OUTPUT'], 'OUTPUT': 'TEMPORARY_OUTPUT'})
    processing.run("native:deletecolumn", {
        'INPUT': points_single['OUTPUT'],
        'COLUMN': ['left','top','right','bottom','osm_id','name','highway','waterway','aerialway',
                   'barrier','man_made','railway','z_order','other_tags','n','distance',
                   'feature_x','feature_y','nearest_x','nearest_y'],
        'OUTPUT': points_out
    })

    # Load population data based on geometry type
    print(datetime.now(), 'Add population data to points...')
    if zensus_geomtype == "Polygon":
        print("> Zensus as polygons, getting centroids...")
        grid_layer = iface.addVectorLayer(zensus, 'Zensus', 'ogr')
        grid_layer = processing.run("native:reprojectlayer", {
            'INPUT': grid_layer, 'TARGET_CRS': QgsCoordinateReferenceSystem(crs), 'OUTPUT': 'TEMPORARY_OUTPUT'
        })['OUTPUT']

        grid_clip = processing.run("native:clip", {'INPUT': grid_layer, 'OVERLAY': buffer_out, 'OUTPUT': 'TEMPORARY_OUTPUT'})['OUTPUT']
        ew_points = processing.run("native:centroids", {'INPUT': grid_clip, 'ALL_PARTS': False, 'OUTPUT': points_ew_out})
    elif zensus_geomtype == "Raster":
        print("> Zensus as raster layer, extracting point grid with spacing 100m...")
        raster_layer = iface.addRasterLayer(zensus,"Zensus")
        raster_region = processing.runAndLoadResults("gdal:cliprasterbymasklayer", {'INPUT':raster_layer,'MASK':buffer_out,'SOURCE_CRS':None,'TARGET_CRS':QgsCoordinateReferenceSystem(crs),'TARGET_EXTENT':None,'NODATA':None,'ALPHA_BAND':False,'CROP_TO_CUTLINE':True,'KEEP_RESOLUTION':False,'SET_RESOLUTION':False,'X_RESOLUTION':None,'Y_RESOLUTION':None,'MULTITHREADING':False,'OPTIONS':'','DATA_TYPE':0,'EXTRA':'','OUTPUT':'TEMPORARY_OUTPUT'})
        raster_clip = QgsProject.instance().mapLayersByName("Clipped (mask)")[0]
        raster_extent = str(raster_clip.extent().xMinimum()) + ','+ str(raster_clip.extent().xMaximum())+ ','+ str(raster_clip.extent().yMinimum())+ ','+ str(raster_clip.extent().yMaximum()) + ' ['+str(raster_clip.crs().authid())+']'
        ew_points = processing.run("qgis:regularpoints", {'EXTENT':raster_extent,'SPACING':100,'INSET':50,'RANDOMIZE':False,'IS_SPACING':True,'CRS':QgsCoordinateReferenceSystem(crs),'OUTPUT':'TEMPORARY_OUTPUT'})
        ew_points = processing.run("native:rastersampling", {'INPUT':ew_points['OUTPUT'],'RASTERCOPY': raster_region['OUTPUT'],'COLUMN_PREFIX':'EW','OUTPUT':'TEMPORARY_OUTPUT'})
        processing.run("qgis:selectbyexpression", {'INPUT': ew_points['OUTPUT'],'EXPRESSION':' "EW1"  IS NOT NULL','METHOD':0}) # only points where inhabitants present
        ew_points = processing.run("native:saveselectedfeatures", {'INPUT':ew_points['OUTPUT'],'OUTPUT':points_ew_out})
    elif zensus_geomtype == "Point":
        print("> Zensus already as points.")
        ew_points = processing.run("native:savefeatures", {'INPUT':zensus,'OUTPUT':points_ew_out,'LAYER_NAME':'','DATASOURCE_OPTIONS':'','LAYER_OPTIONS':''})
    else:
        print("Zensus has incompatible data type, please provide polygons, points or raster layer.")
        break
    
    # Create voronoi polygons for road network points and get population sum within 
    print(datetime.now(), 'Get population sums for street points...')
    voronoi = processing.run("qgis:voronoipolygons", {'INPUT': points_out, 'BUFFER': 2, 'OUTPUT': 'TEMPORARY_OUTPUT'})
    voronoi_einw = processing.runAndLoadResults("qgis:joinbylocationsummary", {
        'INPUT': voronoi['OUTPUT'], 'JOIN': points_ew_out, 'PREDICATE': [1],
        'JOIN_FIELDS': [], 'SUMMARIES': [5], 'DISCARD_NONMATCHING': False, 'OUTPUT': 'TEMPORARY_OUTPUT'
    })
    
    # join summary values to points
    origin_einw = processing.runAndLoadResults("native:joinattributestable", {
        'INPUT': points_out, 'FIELD': 'id', 'INPUT_2': voronoi_einw['OUTPUT'],
        'FIELD_2': 'id', 'FIELDS_TO_COPY': [f'{ew_field}_sum'], 'METHOD': 1,
        'DISCARD_NONMATCHING': False, 'PREFIX': '', 'OUTPUT': 'TEMPORARY_OUTPUT'
    })
    
    # set points with less than 1 inhabitant to 0
    processing.runAndLoadResults("native:fieldcalculator", {
        'INPUT': origin_einw['OUTPUT'], 'FIELD_NAME': 'EW_2',
        'FIELD_TYPE': 0, 'FIELD_LENGTH': 10, 'FIELD_PRECISION': 3,
        'FORMULA': f' if("{ew_field}_sum" < 1,0, "{ew_field}_sum" )', 'OUTPUT': points_out_2
    })

end = datetime.now()
print("Ende:", end.strftime("%H:%M:%S"))
