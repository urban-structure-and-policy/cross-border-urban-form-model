import geopandas as gpd
import momepy
import shapely
import numpy as np
import pandas as pd
import os
import time
import tobler


class Features_on_building_level:

    # 1. Initialization
    def __init__(self, paths, config=None, renamefeatures=None):
        """
        Intialization of the class

        assumes the building footprints are geopanads dataframe containing polygons (Not multipolygons )
        That do not overlapp

        config: dict with keys:
            general:
            - 'crs': str, coordinate reference system (default: 'EPSG:25832')
            - 'nghb_r': int, radius for neighbourhood features (m) (default: 50)
            - 'join_method': str, method for spatial join ('largest_overlap' or 'within', default: 'largest_overlap' because used in original toolbox)
            - 'skip_unavailable': bool, whether to skip features that have required columns specified but cannot be calculated (default: False)
            - 'skip_unspecified': bool, whether to skip features where required columns are not specified (default: True)

            - footprints: Dict with keys
                - 'height_col': str, column name for building height (default: 'height')
                - 'function_col': str, column name for building function (default: 'function')
                - 'id_col': str, column name for ID (default: 'id')
                - 'rooftype_col': str, column name for roof type
                - 'roofarea_col': str, column name for roof area
                - 'wallarea_col': str, column name for wall area

            - municipalities: Dict with keys
                - 'mun_col': str, column name for municipality code
                - 'planreg_col': str, column name for plan regulation code
                - 'state_col': str, column name for state code
                - 'country_col': str, column name for country code

            - spatial_typology: Dict with keys    
                - 'typology_col': str, column name for spatial typology code

            - blocks: Dict with keys
                - 'id_col': str, column name for block ID

            - parcels: Dict with keys
                - 'id_col': str, column name for parcel ID

            - parts: Dict with keys
                - 'id_col': str, column name for part ID
                - 'parent_id_col': str, column name for parent building ID

        paths: dict with keys:
            - 'input': dict with keys
                - 'footprints': str, path to building footprints file (geopackage)
                - 'municipalities': str, path to municipalities file (geopackage)
                - 'blocks': str, path to blocks file (geopackage)
                - 'parcels': str, path to parcels file (geopackage)
                - 'addresses': str, path to addresses file (geopackage)
                - 'spatial_typology': str, path to spatial typology file (geopackage)
                - 'residential_lookup': str, path to residential lookup table (csv)
                - 'parts': str, path to building parts file (geopackage)

            - 'process': dict with keys
                - 'nghb_matrix_base': str, base path for neighbourhood matrix files (csv), _r{}.csv will be added automatically for radius

            - 'output': dict with keys
                - 'result': str, path to output result file (geopackage)

        renamefeatures: dict, mapping of original feature names to new names (optional)
            - 'FEATURE' (str, key in feature registry): 'output_feature_name' (str, new name for the feature in output),
        """
        self._paths = paths
        self._renamefeatures = renamefeatures

        # Merge user config with default and ensure id column exist
        self._setup_config(config=config)

        # Create missing folders for process and output if they do not exist
        self._create_missing_paths()

        # Load and check footprints
        self.footprints = self._load_check_geoms(path=self._paths['input']['footprints'], geomtype="Polygon")

        # Ensure ID column from config is in footprints
        self._ensure_id_column()

        # Initialise feature set with base geometry metrics
        self._get_base_features()

        # Feature registry (centralized list of available features)
        self._register_features()

        # Rename feature names
        self._rename_features()
        

    def _setup_config(self, config=None):
        
        # Set default config
        default_config = {
            'crs' : 'EPSG:25832',
            'nghb_r': 50,
            'join_method': 'largest_overlap', 
            'skip_unspecified': True,
            'skip_unavailable': False,
            'check_overlaps': True,

            # footprint columns
            'footprints': {
                'height_col': 'height',
                'function_col': 'function',
                'id_col': 'fid',
                'rooftype_col': None,
                'roofarea_col': None,
                'wallarea_col': None
            },

            # residential lookup table columns
            'residential_lookup': {
                'original_col': 'ORIG_FKT',
                'fnc_code_col': 'FNC_CODE',
                'is_res_col': 'IS_RES'
            },

            # municipality columns
            'municipalities': {
                'mun_col':  None,
                'planreg_col': None,
                'state_col': None,
                'country_col': None
            },

            # spatial typology columns (REGIOSTAR)
            'spatial_typology': {
                'typology_col': None
            },

            # block columns
            'blocks': {
                'id_col': 'block_id'
            },

            # parcel columns
            'parcels': {
                'id_col': 'parcel_id'
            },

            # address columns
            'addresses': {
                # Not yet used, but can be used to get address
                'addr_street_col': None
            },

            # building part columns
            'parts': {
                'id_col': 'part_id',
                'parent_id_col': 'building_id'
            },
        }

        # Merge with user config
        def _deep_merge(dict1, dict2):
            """Merge two dictionaries, including nested dictionaries.
            (from https://www.sitepoint.com/python/dictionaries-nested/#deep-merging-nested-dictionaries)"""
            result = dict1.copy()
            for key, value in dict2.items():
                if key in result:
                    if isinstance(result[key], dict) and isinstance(value, dict):
                        result[key] = _deep_merge(result[key], value)
                    else:
                        result[key] = value
                else:
                    result[key] = value
            return result
        
        self.config = _deep_merge(default_config, config or {})
        print(f"Configuration: {self.config}")

        # default to largest_overlap if join_method not in options
        if self.config['join_method'] not in ['largest_overlap', 'within']:
            raise ValueError(f"Invalid join_method '{self.config['join_method']}'. Use 'largest_overlap' or 'within'.")

    def _create_missing_paths(self):
        # create missing folders for process and output if they do not exist
        for path in (os.path.dirname(subpath)
                    for key, p in self._paths.items() if key in ('process', 'output')
                    for subpath in p.values()):
            if path:
                os.makedirs(path, exist_ok=True)
    

    def _load_check_geoms(self, path, geomtype = None):
        ''' 
        Loads geographic input data as geodataframes, checks and repairs geometries 
        geomtype: Str (optional to check for a specific unique geom type, else just check if unique type)
        '''
        # Load file
        if not os.path.exists(path):
            raise ValueError(f"Input data does not exist at: {path}")
        data = gpd.read_file(path)

        # Ensure correct CRS
        try:
            data = data.to_crs(self.config['crs'])
        except Exception:
            print(f"⚠️ Warning: Invalid CRS '{self.config['crs']}', using EPSG:25832")
            data = data.to_crs('EPSG:25832') 

        # Repair geometries
        data.geometry = data.geometry.make_valid()

        # Check if geom type unique
        geom_types = set(data.geom_type.unique())
        caution = False
        if geomtype:
            if not (data.geom_type == geomtype).all():
                caution = True
                print(f"⚠️ Warning: Expected only '{geomtype}' geometries but found: {geom_types}")
                # compare as sets
                if geom_types == {f"Multi{geomtype}"} or geom_types == {f"Multi{geomtype}", geomtype}:
                    print(f"> All (other) geometries are Multi{geomtype}, trying to convert to {geomtype}")
                    exploded_geom = data.geometry.explode()
                    if len(exploded_geom) == len(data):
                        data.geometry = exploded_geom
                        caution = False
                        print(f"> All geometries consist of single parts, converted to {geomtype}")
                    else:
                        print(f"> Some geometries consist of multiple parts, cannot convert to {geomtype}")
                        # find geometries with multiple parts
                        part_counts = exploded_geom.groupby(exploded_geom.index).size()
                        multi_parts = data[data.index.isin(part_counts[part_counts > 1].index)]
                        if self._paths['process'].get('geometry_errors'):
                            multi_parts.to_file(self._paths['process']['geometry_errors'], driver='GPKG')
                            print(f"> Geometries with multiple parts saved to {self._paths['process']['geometry_errors']}")
                # export geometries with different types for inspection
                elif self._paths['process'].get('geometry_errors'):
                    data[data.geom_type != geomtype].to_file(self._paths['process']['geometry_errors'], driver='GPKG')
                    print(f"> Geometries with different types saved to {self._paths['process']['geometry_errors']}")
        else:
            if len(geom_types) > 1:
                caution = True
                print(f"⚠️ Warning: Multiple geometry types found: {geom_types}")
        if caution:
            print("> Continuing with geometry issues, some features may not be calculated correctly (e.g. CNT_HLS).")

        if self.config['check_overlaps']:
            # Check overlaps
            data_tmp = data.copy()
            data_tmp['_tmp_id'] = range(len(data_tmp))
            overlaps = gpd.overlay(data_tmp, data_tmp)
            overlaps = overlaps[overlaps['_tmp_id_1'] != overlaps['_tmp_id_2']]
            if len(overlaps) > 0:
                print(f"⚠️ Warning: Geometries have overlaps, please procceed with caution ")
                print('> Biggest overlap:', max(overlaps.area))
                print('> Number of overlaps:', len(overlaps))

                if self._paths['process'].get('overlaps'):
                    overlaps.to_file(self._paths['process']['overlaps'], driver='GPKG')
                    print(f"> Overlaps saved to {self._paths['process']['overlaps']}")

        return data

    def _ensure_id_column(self, data='footprints'):

        id_col = self.config[data]['id_col']

        if data == 'footprints':
            if id_col not in self.footprints.columns:
                print(f"⚠️ Warning: ID column '{id_col}' not found in footprints, using 1-based index as ID.")
                self.footprints[id_col] = self.footprints.index + 1
        else:
            if id_col not in self.loaded_data[data].columns:
                print(f"⚠️ Warning: ID column '{id_col}' not found in '{data}', using 1-based index as ID.")
                self.loaded_data[data][id_col] = self.loaded_data[data].index + 1

    def _get_base_features(self):
        # Compute base geometry metrics
        self.area = self.footprints.geometry.area
        self.circumference = self.footprints.geometry.length
        self.mbr = self.footprints.minimum_rotated_rectangle()

        # Initialize feature set
        self.featureset = self.footprints[[self.config['footprints']['id_col'], self.footprints.geometry.name]].copy()
        self.featureset['A'] =  self.area
        self.featureset['C'] = self.circumference

        # If Height column exists, calculate volume and height
        if self.config['footprints']['height_col'] in self.footprints.columns:
            self.featureset['H'] = self.footprints[self.config['footprints']['height_col']]
            self.volume = self.featureset['H']* self.area
            self.featureset['V'] = self.volume

    def _register_features(self):
        """ Register all implemented 2D features with metadata.

        Registration dict struture: 
        - 'func': function call,
        - 'description': Str,
        - 'requires_col': required columns in building footprints -- List[Dict{'source': Str (same as dict name with column names), 'colname': Str}],
        - 'requires_data': additional required input data -- List[Str],
        - 'tags': categories to call certain feature sets-- List[Str],
        - 'output_col': Str

        Tags in use:
        - Category: Density & Coverage, Geometry & Shape, Neighbourhood & Proximity, Physical appearance & Size, 
                    Road Network, Semantics, Socio-economic, Location & Accessibility
        - Dimension: 2D, 3D
        - Spatial Level: Building, Block, Neighbourhood, Raster, Parcel, Other
        - Complexity: Base, Simple, Complex
        - Application: Toolbox

        Template for adding new features:
        'FEATURE': {
            'func': self._calc_,
            'description': '',
            'requires_col': [],
            'requires_data': [],
            'tags': ['', '', '', '', ''],
            'output_col': 'FEATURE'
        },

        """
        self._feature_registry  = {
            ## Building features
            # Base features
            'FNC': {
                'func': self._calc_fnc,
                'description': 'Building function',
                'requires_col': [{'source': 'footprints', 'colname': 'function_col'}],
                'requires_data': [],
                'tags': ['Semantics', '2D', 'Building', 'Base', 'Toolbox', 'FFP'],
                'output_col': 'FNC'
            },
            'FNC_CODE': {
                'func': self._calc_fnc_code,
                'description': 'Functional code',
                'requires_col': [{'source': 'footprints', 'colname': 'function_col'}, 
                                 {'source': 'residential_lookup', 'colname': 'fnc_code_col'},
                                 {'source': 'residential_lookup', 'colname': 'original_col'}
                                 ],
                'requires_data': ['residential_lookup'],
                'tags': ['Semantics', '2D', 'Building', 'Base', 'Toolbox', 'FFP'],
                'output_col': 'FNC_CODE'
            },

            # Simple features
            'IS_RES': {
                'func': self._calc_is_res,
                'description': 'Is residential (based on function code)',
                'requires_col': [{'source': 'footprints', 'colname': 'function_col'}, 
                                 {'source': 'residential_lookup', 'colname': 'original_col'},
                                 {'source': 'residential_lookup', 'colname': 'is_res_col'}],
                'requires_data': ['residential_lookup'],
                'tags': ['Semantics', '2D', 'Building', 'Simple', 'Toolbox', 'FFP'],
                'output_col': 'IS_RES'
            },
            'CNT_HLS': {
                'func': self._calc_cnt_hls,
                'description': 'Number of holes',
                'requires_col': [],
                'requires_data': [],
                'tags': ['Geometry & Shape', '2D', 'Building', 'Simple', 'Toolbox'],
                'output_col': 'CNT_HLS'
            },            
            'CNT_NDS': {
                'func': self._calc_cnt_nds,
                'description': 'Number of nodes',
                'requires_col': [],
                'requires_data': [],
                'tags': ['Geometry & Shape', '2D', 'Building', 'Simple', 'Toolbox', 'FFP'],
                'output_col': 'CNT_NDS'
            },            
            'RATIO_C_A': {
                'func': self._calc_ratio_c_a,
                'description': 'Ratio Circumference-Area',
                'requires_col': [],
                'requires_data': [],
                'tags': ['Physical appearance & Size', '2D', 'Building', 'Simple', 'Toolbox', 'FFP'],
                'output_col': 'RATIO_C_A'
            },
            'CNT_PRTS': {
                'func': self._calc_cnt_prts,
                'description': 'Number of parts',
                'requires_col': [{'source': 'parts', 'colname': 'parent_id_col'}],
                'requires_data': ['parts'],
                'tags': ['Geometry & Shape', '3D', 'Building', 'Simple', 'Toolbox', 'FFP'],
                'output_col': 'CNT_PRTS'
            },
            'PART_ID': {
                'func': self._calc_part_id,
                'description': 'Part ID (any, for backtracing assignment)',
                'requires_col': [{'source': 'parts', 'colname': 'id_col'},
                                 {'source': 'parts', 'colname': 'parent_id_col'}],
                'requires_data': ['parts'],
                'tags': ['Geometry & Shape', '3D', 'Building', 'Simple', 'Toolbox', 'FFP'],
                'output_col': 'PART_ID'
            },

            # Complex features
            'RATIO_SW': {
                'func': self._calc_ratio_sw,
                'description': 'Ratio of shared walls',
                'requires_col': [],
                'requires_data': [],
                'tags': ['Neighbourhood & Proximity', '2D', 'Building', 'Complex', 'Toolbox', 'FFP'],
                'output_col': 'RATIO_SW'
            },
            'RATIO_MBR_A': {
                'func': self._calc_ratio_mbr_a,
                'description': 'Ratio of minimum bounding rectangle area to building area',
                'requires_col': [],
                'requires_data': [],
                'tags': ['Physical appearance & Size', '2D', 'Building', 'Complex', 'Toolbox', 'FFP'],
                'output_col': 'RATIO_MBR_A'
            },
            'RATIO_LW_MBR': {
                'func': self._calc_ratio_lw_mbr,
                'description': 'Ratio length-width of the minimum bounding rectangle',
                'requires_col': [],
                'requires_data': [],
                'tags': ['Physical appearance & Size', '2D', 'Building', 'Complex', 'Toolbox'],
                'output_col': 'RATIO_LW_MBR'
            },            
            'SHPX_2D': {
                'func': self._calc_shpx_2d,
                'description': 'Shape Index',
                'requires_col': [],
                'requires_data': [],
                'tags': ['Physical appearance & Size', '2D', 'Building', 'Complex', 'Toolbox', 'FFP'],
                'output_col': 'SHPX_2D'
            },
            'RF_TYPE': {
                'func': self._calc_rf_type,
                'description': 'Roof Type',
                'requires_col': [{'source': 'footprints', 'colname': 'rooftype_col'}],
                'requires_data': [],
                'tags': ['Semantics', '3D', 'Building', 'Complex', 'Toolbox'],
                'output_col': 'RF_TYPE'
            },
            'RATIO_HLL_V': {
                'func': self._calc_ratio_hll_v,
                'description': 'Ratio of hull area to volume',
                'requires_col': [{'source': 'footprints', 'colname': 'height_col'}, 
                                 {'source': 'footprints', 'colname': 'roofarea_col'},
                                 {'source': 'footprints', 'colname': 'wallarea_col'}],
                'requires_data': [],
                'tags': ['Physical appearance & Size', '3D', 'Building', 'Complex', 'Toolbox'],
                'output_col': 'RATIO_HLL_V'
            },

            ## Neighbourhood features
            # Simple features
            'CNT_NGHB_D': {
                'func': self._calc_cnt_nghb_d,
                'description': 'Number of direct neighbours',
                'requires_col': [],
                'requires_data': [],
                'tags': ['Neighbourhood & Proximity', '2D', 'Neighbourhood', 'Simple', 'Toolbox', 'FFP'],
                'output_col': 'CNT_NGHB_D'
            },
            'DIST_NGHB_D': {
                'func': self._calc_dist_nghb_d,
                'description': 'Distance to nearest building',
                'requires_col': [],
                'requires_data': [],
                'tags': ['Neighbourhood & Proximity', '2D', 'Neighbourhood', 'Simple', 'Toolbox', 'FFP'],
                'output_col': 'DIST_NGHB_D'
            },

            # Complex features
            f'CNT_NGHB_R{self.config["nghb_r"]}': {
                'func': self._calc_cnt_nghb_r,
                'description': 'Number of neighbours within specified radius (m)',
                'requires_col': [],
                'requires_data': [],
                'tags': ['Neighbourhood & Proximity', '2D', 'Neighbourhood', 'Complex', 'Toolbox', 'FFP'],
                'output_col': f'CNT_NGHB_R{self.config["nghb_r"]}'
            },
            f'DIST_NGHB_R{self.config["nghb_r"]}': {
                'func': self._calc_dist_nghb_r,
                'description': 'Mean distance to all buildings within specified radius (m)',
                'requires_col': [],
                'requires_data': [],
                'tags': ['Neighbourhood & Proximity', '2D', 'Neighbourhood', 'Complex', 'Toolbox', 'FFP'],
                'output_col': f'DIST_NGHB_R{self.config["nghb_r"]}'
            },

            ## Block features
            # Simple features
            'BLOCK_ID': {
                'func': self._calc_block_id,
                'description': 'Block ID',
                'requires_col': [{'source': 'blocks', 'colname': 'id_col'}],
                'requires_data': ['blocks'],
                'tags': ['Geometry & Shape', '2D', 'Block', 'Simple', 'FFP'],
                'output_col': 'BLOCK_ID'
            },
            'BLCK_A': {
                'func': self._calc_blck_a,
                'description': 'Block area',
                'requires_col': [],
                'requires_data': ['blocks'],
                'tags': ['Geometry & Shape', '2D', 'Block', 'Simple', 'FFP'],
                'output_col': 'BLCK_A'
            },

            # Complex features
            'A_MEAN_BLCK': {
                'func': self._calc_a_mean_blck,
                'description': 'Mean building area in block',
                'requires_col': [],
                'requires_data': ['blocks'],
                'tags': ['Density & Coverage', '2D', 'Block', 'Complex', 'Toolbox'],
                'output_col': 'A_MEAN_BLCK'
            },
            'A_STD_BLCK': {
                'func': self._calc_a_std_blck,
                'description': 'Standard deviation of building area in block',
                'requires_col': [],
                'requires_data': ['blocks'],
                'tags': ['Density & Coverage', '2D', 'Block', 'Complex', 'Toolbox'],
                'output_col': 'A_STD_BLCK'
            },
            'A_SUM_BLCK': {
                'func': self._calc_a_sum_blck,
                'description': 'Sum of building area in block',
                'requires_col': [],
                'requires_data': ['blocks'],
                'tags': ['Density & Coverage', '2D', 'Block', 'Complex', 'Toolbox'],
                'output_col': 'A_SUM_BLCK'
            },
            'CNT_BLCK': {
                'func': self._calc_cnt_blck,
                'description': 'Count of buildings in block',
                'requires_col': [],
                'requires_data': ['blocks'],
                'tags': ['Density & Coverage', '2D', 'Block', 'Complex', 'Toolbox'],
                'output_col': 'CNT_BLCK'
            },
            'A_MIN_BLCK': {
                'func': self._calc_a_min_blck,
                'description': 'Minimum building area in block',
                'requires_col': [],
                'requires_data': ['blocks'],
                'tags': ['Density & Coverage', '2D', 'Block', 'Complex'],
                'output_col': 'A_MIN_BLCK'
            },
            'A_MAX_BLCK': {
                'func': self._calc_a_max_blck,
                'description': 'Maximum building area in block',
                'requires_col': [],
                'requires_data': ['blocks'],
                'tags': ['Density & Coverage', '2D', 'Block', 'Complex'],
                'output_col': 'A_MAX_BLCK'
            }, 
            'RATIO_A_BLCK': {
                'func': self._calc_ratio_a_blck,
                'description': 'Ratio of building area to block area',
                'requires_col': [],
                'requires_data': ['blocks'],
                'tags': ['Physical appearance & Size', '2D', 'Building', 'Block', 'Complex', 'Toolbox'],
                'output_col': 'RATIO_A_BLCK'
            },
            'RATIO_A_MEAN': {
                'func': self._calc_ratio_a_mean_blck,
                'description': 'Ratio of building area to mean building area in block',
                'requires_col': [],
                'requires_data': ['blocks'],
                'tags': ['Physical appearance & Size', '2D', 'Building', 'Block', 'Complex', 'Toolbox'],
                'output_col': 'RATIO_A_MEAN'
            },
            'RATIO_A_SUM': {
                'func': self._calc_ratio_a_sum_blck,
                'description': 'Ratio of building area to total building area in block',
                'requires_col': [],
                'requires_data': ['blocks'],
                'tags': ['Physical appearance & Size', '2D', 'Building', 'Block', 'Complex', 'Toolbox'],
                'output_col': 'RATIO_A_SUM'
            },
            'V_MEAN_BLCK': {
                'func': self._calc_v_mean_blck,
                'description': 'Mean volume of buildings in block',
                'requires_col': [{'source': 'footprints', 'colname': 'height_col'}],
                'requires_data': ['blocks'],
                'tags': ['Density & Coverage', '3D', 'Block', 'Complex', 'Toolbox'],
                'output_col': 'V_MEAN_BLCK'
            },
            'V_STD_BLCK': {
                'func': self._calc_v_std_blck,
                'description': 'Standard deviation of volume of buildings in block',
                'requires_col': [{'source': 'footprints', 'colname': 'height_col'}],
                'requires_data': ['blocks'],
                'tags': ['Density & Coverage', '3D', 'Block', 'Complex', 'Toolbox'],
                'output_col': 'V_STD_BLCK'
            },
            'V_SUM_BLCK': {
                'func': self._calc_v_sum_blck,
                'description': 'Sum of volume of buildings in block',
                'requires_col': [{'source': 'footprints', 'colname': 'height_col'}],
                'requires_data': ['blocks'],
                'tags': ['Density & Coverage', '3D', 'Block', 'Complex', 'Toolbox'],
                'output_col': 'V_SUM_BLCK'
            },
            'RATIO_V_MEAN': {
                'func': self._calc_ratio_v_mean_blck,
                'description': 'Ratio of building volume to mean building volume in block',
                'requires_col': [{'source': 'footprints', 'colname': 'height_col'}],
                'requires_data': ['blocks'],
                'tags': ['Physical appearance & Size', '3D', 'Building', 'Block', 'Complex', 'Toolbox'],
                'output_col': 'RATIO_V_MEAN'
            },
            'RATIO_V_SUM': {
                'func': self._calc_ratio_v_sum_blck,
                'description': 'Ratio of building volume to total building volume in block',
                'requires_col': [{'source': 'footprints', 'colname': 'height_col'}],
                'requires_data': ['blocks'],
                'tags': ['Physical appearance & Size', '3D', 'Building', 'Block', 'Complex', 'Toolbox'],
                'output_col': 'RATIO_V_SUM'
            },
            #'BLCK_TYPE'

            ## Parcel features
            # Simple features
            'PRCL_ID': {
                'func': self._calc_parcel_id,
                'description': 'Parcel ID',
                'requires_col': [{'source': 'parcels', 'colname': 'id_col'}],
                'requires_data': ['parcels'],
                'tags': ['Geometry & Shape', '2D', 'Parcel', 'Simple', 'FFP'],
                'output_col': 'PRCL_ID'
            },
            'PRCL_A': {
                'func': self._calc_parcel_a,
                'description': 'Parcel area',
                'requires_col': [],
                'requires_data': ['parcels'],
                'tags': ['Geometry & Shape', '2D', 'Parcel', 'Simple', 'FFP'],
                'output_col': 'PRCL_A'
            },

            # Complex features
            'RATIO_A_PRCL': {
                'func': self._calc_ratio_a_prcl,
                'description': 'Building coverage ratio (Building footprint area/parcel area)',
                'requires_col': [],
                'requires_data': ['parcels'],
                'tags': ['Density & Coverage', '2D', 'Building', 'Parcel', 'Complex', 'FFP'],
                'output_col': 'RATIO_A_PRCL'
            },
            'RATIO_V_A_PRCL': {
                'func': self._calc_ratio_v_a_prcl,
                'description': 'Ratio of building volume sum in parcel to area of parcel',
                'requires_col': [{'source': 'footprints', 'colname': 'height_col'}],
                'requires_data': ['parcels'],
                'tags': ['Density & Coverage', '3D', 'Parcel', 'Complex'],
                'output_col': 'PRCL_RATIO_V_A'
            },

            ## Other
            # Simple
            'MUN_CODE': {
                'func': self._calc_mun_code,
                'description': 'Municipality code',
                'requires_col': [{'source': 'municipalities', 'colname': 'mun_col'}],
                'requires_data': ['municipalities'],
                'tags': ['Socio-economic', '2D', 'Building', 'Other', 'Simple', 'Toolbox', 'FFP'],
                'output_col': 'MUN_CODE'
            },
            'PLANREG': {
                'func': self._calc_planreg_code,
                'description': 'Planning region code',
                'requires_col': [{'source': 'municipalities', 'colname': 'planreg_col'}],
                'requires_data': ['municipalities'],
                'tags': ['Socio-economic', '2D', 'Building', 'Other', 'Simple', 'Toolbox'],
                'output_col': 'PLANREG'
            },
            'STATE': {
                'func': self._calc_state_code,
                'description': 'State code',
                'requires_col': [{'source': 'municipalities', 'colname': 'state_col'}],
                'requires_data': ['municipalities'],
                'tags': ['Socio-economic', '2D', 'Building', 'Other', 'Simple', 'Toolbox', 'FFP'],
                'output_col': 'STATE'
            },
            'COUNTRY': {
                'func': self._calc_country_code,
                'description': 'Country code',
                'requires_col': [{'source': 'municipalities', 'colname': 'country_col'}],
                'requires_data': ['municipalities'],
                'tags': ['Socio-economic', '2D', 'Building', 'Other', 'Simple', 'FFP'],
                'output_col': 'COUNTRY'
            },
            'STYPOLOGY': {
                'func': self._calc_stypology_code,
                'description': 'Spatial typology code (e.g. Regiostar)',
                'requires_col': [{'source': 'spatial_typology', 'colname': 'typology_col'}],
                'requires_data': ['spatial_typology'],
                'tags': ['Socio-economic', '2D', 'Building', 'Other', 'Simple', 'Toolbox'],
                'output_col': 'STYPOLOGY'
            },

            'CNT_ADD': {
                'func': self._calc_cnt_add,
                'description': 'Number of address points within 1m distance',
                'requires_col': [],
                'requires_data': ['addresses'],
                'tags': ['Semantics', '2D', 'Building', 'Simple', 'Toolbox', 'FFP'],
                'output_col': 'CNT_ADD'
            },

            #'DIST_STRT': {
            #    'func': self._calc_dist_strt,
            #    'description': 'Distance to nearest street',
            #    'requires_col': [],
            #    'requires_data': ['streets'],
            #    'tags': ['Road Network', '2D', 'Building', 'Simple', 'Toolbox'],
            #    'output_col': 'DIST_STRT'
            #}
        }

    def _rename_features(self):
        """Rename output columns of featureset if output_colnames specified."""
        if self._renamefeatures:
            for ogname, outname in self._renamefeatures.items():
                if ogname in self._feature_registry.keys():
                    self._feature_registry[ogname]['output_col'] = outname
        

    def _select_features(self, tags=None, features=None):
        """
        Select and validate feature list to calculate.

        Returns:
        - self._selected_features (list)
        - self._get_nghb_matrix (true if nghb features in list)
        """
        selected_features = set()

        # if tags provided:
        if tags:
            # take the keys of all features that have the tag(s)
            for k,v in self._feature_registry.items():
                if any(tag in v['tags'] for tag in tags):
                    selected_features.add(k)

        # if features provided, add to features from tags:
        if features is not None:
            if features == 'all':
                selected_features = selected_features | set(self._feature_registry.keys())
            else:
                selected_features = selected_features | set(features)

        # if neither tags or features provided, use all
        if not selected_features:
            selected_features = set(self._feature_registry.keys())

        # convert to list 
        selected_features = list(selected_features)

        # Validate feature names
        invalid_features = [f for f in selected_features if f not in self._feature_registry]
        if invalid_features:
            raise ValueError(f"Unknown features: {invalid_features}. Available: {list(self._feature_registry.keys())}")

        # Check if any feature requires neighborhood matrix
        taglist = [featuretag
                   for feature_name in selected_features
                   for featuretag in self._feature_registry[feature_name]['tags']]
        
        self._selected_tags = taglist
        self._selected_features = selected_features

    def _check_req_data(self):
        """Check that all required data paths exist"""
        self._required_data = {}
        for feature_name in list(self._selected_features):
            registry = self._feature_registry[feature_name]
            
            for in_key in registry.get('requires_data', []):
                if in_key in self._required_data:
                    continue
                
                data_path = self._paths['input'].get(in_key)

                if data_path is None:
                    message = f"Missing path '{in_key}' required for feature '{feature_name}'"
                    if self.config.get('skip_unspecified', True):
                        print(f"⚠️ Warning: {message}, skipping this feature.")
                        self._selected_features.remove(feature_name)
                        break
                    raise ValueError(message)

                if not os.path.exists(data_path):
                    message = f"Required input data '{in_key}' does not exist at: {data_path}"
                    if self.config.get('skip_unavailable', False):
                        print(f"⚠️ Warning: {message}, skipping this feature.")
                        self._selected_features.remove(feature_name)
                        break
                    raise ValueError(message)

                if not data_path.endswith(('.gpkg', '.csv')):
                    message = f"Unsupported file format for {in_key}: {data_path}. Only .gpkg (for geospatial data) and .csv (for lookup tables) are supported."
                    if self.config.get('skip_unavailable', False):
                        print(f"⚠️ Warning: {message}, skipping this feature.")
                        self._selected_features.remove(feature_name)
                        break
                    raise ValueError(message)
                
                self._required_data[in_key] = data_path        
                
    def _load_req_data(self):
        """Store loaded data in a dict for cleaner class"""
        self.loaded_data = {}
        for in_key, in_path in self._required_data.items():
            print(f"Loading {in_key}...")
            # if input is gpkg, load as geodataframe and check geometries
            if in_path.endswith('.gpkg'):
                self.loaded_data[in_key] = self._load_check_geoms(in_path)
                # if key 'id_col' in config for this data, ensure it exists (has a default where required in config)
                if in_key in self.config and 'id_col' in self.config[in_key]:
                    self._ensure_id_column(data=in_key)
            # if csv, load as table
            elif in_path.endswith('.csv'):
                try:
                    self.loaded_data[in_key] = pd.read_csv(in_path)
                except UnicodeDecodeError:
                    # Fallback for lookup tables saved with Windows encoding and ';' separator.
                    self.loaded_data[in_key] = pd.read_csv(in_path, sep=';', encoding='latin-1')
                
    def _check_req_cols(self):
        """Check that all required columns exist in loaded data"""
        for feature_name in list(self._selected_features):
            registry = self._feature_registry[feature_name]

            for col_key in registry.get('requires_col', []):
                col_source = col_key.get('source', 'footprints')
                col_name = self.config[col_source].get(col_key.get('colname'), col_key.get('colname'))
                data = self.footprints if col_source == 'footprints' else self.loaded_data.get(col_source)

                if data is None:
                    raise ValueError(f"Required data source '{col_source}' for feature '{feature_name}' was not loaded")

                # skip if column not specified and skip_unspecified is True else raise error
                if col_name is None:
                    message = f"No column name specified for required column '{col_key.get('colname')}' in '{col_source}' for feature '{feature_name}'"
                    if self.config.get('skip_unspecified', True):
                        print(f"⚠️ Warning: {message}, skipping this feature.")
                        self._selected_features.remove(feature_name)
                        break
                    raise ValueError(message)
                # skip if column not found and skip_unavailable is True
                elif col_name not in data.columns:
                    message = f"Required column '{col_key.get('colname')}' for feature '{feature_name}' not found as '{col_name}' in '{col_source}'"
                    if self.config.get('skip_unavailable', False):
                        print(f"⚠️ Warning: {message}, skipping this feature.")
                        self._selected_features.remove(feature_name)
                        break
                    raise ValueError(message)


    # inlcude block calculation if none provided
    # follow https://docs.momepy.org/stable/user_guide/elements/blocks.html 
    # requires street network
    
    def _calc_nghb_matrix(self):
        """
        Calculate sparse neighbourhood matrix for neighbourhoud features in specified radius.
        Returns:
        - self._nghb_matrix()
        - Saves nghbhood matrix
        """

        print(f"Calculating sparse neighbourhood distance matrix for radius {self.config['nghb_r']}...")
        
        start = time.perf_counter()
        # Check if matrix already exists as intermediate file
        intermediate_path = f"{self._paths['process']['nghb_matrix_base']}_r{self.config['nghb_r']}.csv"
        if os.path.exists(intermediate_path):
            self._nghb_matrix = pd.read_csv(intermediate_path)
            print(f"> Loaded from {intermediate_path} ({time.perf_counter() - start:.2f}s)")
            return 

        # calculate matrix
        left, right = self.footprints.geometry.sindex.query(
            self.footprints.geometry, 
            predicate="dwithin",
            distance=self.config['nghb_r'])

        mask = left != right
        left = left[mask]
        right = right[mask]

        dist = self.footprints.geometry.values[left].distance(
            self.footprints.geometry.values[right]
        )

        near_table = pd.DataFrame({
            "IN_FID": left,
            "NEAR_FID": right,
            "NEAR_DIST": dist
        })
        
        self._nghb_matrix = near_table

        print(f"> Calculation time {time.perf_counter() - start:.2f}s")

        # Save as intermediate file
        self._nghb_matrix.to_csv(intermediate_path, index=False)
        print(f"> Saved to {intermediate_path}")

    def _calc_sjoin(self, joindata):
        """Spatial join with additional data to get field values.
        joindata : Str with corresponding key in self.loaded_data and column name dictionary (e.g., 'municipalities') """

        print(f"Performing spatial join with {joindata}...")
        start = time.perf_counter()

        if joindata == 'blocks' or joindata == 'parcels':
            self.loaded_data[joindata]['_A_joined'] = self.loaded_data[joindata].geometry.area

        if joindata == "addresses":
            cols_needed = list(self.config[joindata].values()) + [self.loaded_data[joindata].geometry.name]
            cols_needed = [col for col in cols_needed if col is not None and col in self.loaded_data[joindata].columns]
            sjoin = gpd.sjoin(
                    self.footprints[[self.config['footprints']['id_col'], self.footprints.geometry.name]], 
                    self.loaded_data[joindata][cols_needed],
                    how='left',
                    predicate='dwithin',
                    distance=0.5)        

            return sjoin    

        if self.config['join_method'] == 'within':
            print(f"> Using 'within' method for spatial join (faster, but may result in NA for buildings intersecting multiple geometries)")
            # join only when building is completely within (NA for multiple intersections) (faster)
            # get cols needed from join data columns dicts; ensure 'geometry' is included
            cols_needed = list(self.config[joindata].values()) + ['_A_joined', self.loaded_data[joindata].geometry.name]
            # check if columns exist, A_joined will be filtered out if it wasnt created first
            cols_needed = [col for col in cols_needed if col is not None and col in self.loaded_data[joindata].columns]
            sjoin = gpd.sjoin(
                    self.footprints[[self.config['footprints']['id_col'], self.footprints.geometry.name]], 
                    self.loaded_data[joindata][cols_needed],
                    how='left',
                    predicate='within')
            print(f"> {len(sjoin) - sjoin[cols_needed[0]].notna().sum()} NA values present, use 'largest_overlap' method for definitive assignments.")
        
        elif self.config['join_method'] == 'largest_overlap':
            print(f"> Using 'largest_overlap' method for spatial join (slower, but definitive assignments for buildings intersecting multiple geometries)")
            # join based on largest intersection when multiple geometries found
            cols_needed = list(self.config[joindata].values()) + ['_A_joined']
            # check if columns exist, A_joined will be filtered out if it wasnt created first
            cols_needed = [col for col in cols_needed if col is not None and col in self.loaded_data[joindata].columns]
            sjoin = tobler.area_weighted.area_join(
                self.loaded_data[joindata],
                self.footprints[[self.config['footprints']['id_col'], self.footprints.geometry.name]],
                variables = cols_needed
                )
            
        print(f"> Calculation time {time.perf_counter() - start:.2f}s")
            
        return sjoin
    
    def _get_block_id_series(self):
        if not hasattr(self, '_block_sjoin'):
            self._block_sjoin = self._calc_sjoin('blocks')
        return self._block_sjoin[self.config['blocks']['id_col']]


    # Feature calculation functions
    '''
    # Feature calculation function template

    def _calc_(self):
        """Calculate feature."""
        try:
            return None
        except Exception as e:
            return None
    '''        
    def _calc_fnc(self):
        """Get building function."""
        try:
            return self.footprints[self.config['footprints']['function_col']]
        except Exception as e:
            return None
                
    def _calc_fnc_code(self):
        """Get building function code."""
        try:
            fnc_col = self.config['footprints']['function_col']
            original_col = self.config['residential_lookup']['original_col']
            fnc_code_col = self.config['residential_lookup']['fnc_code_col']

            # Build lookup from configured original function field to IS_RES.
            lookup = self.loaded_data['residential_lookup'][[original_col, fnc_code_col]].drop_duplicates(subset=[original_col], keep='first')
            fnc_code_map = lookup.set_index(original_col)[fnc_code_col]

            # map preserves input order; fill missing matches with 0.
            return self.footprints[fnc_col].map(fnc_code_map).fillna(0)
        except Exception as e:
            return None

    def _calc_is_res(self):
        """Determine if building is residential based on function code."""
        try:
            fnc_col = self.config['footprints']['function_col']
            original_col = self.config['residential_lookup']['original_col']
            is_res_col = self.config['residential_lookup']['is_res_col']

            # Build lookup from configured original function field to IS_RES.
            lookup = self.loaded_data['residential_lookup'][[original_col, is_res_col]].drop_duplicates(subset=[original_col], keep='first')
            is_res_map = lookup.set_index(original_col)[is_res_col]

            # map preserves input order; fill missing matches with 0.
            return self.footprints[fnc_col].map(is_res_map).fillna(0)
        except Exception as e:
            return None

    def _calc_cnt_hls(self):
        """Calculate number of holes."""
        try:
            cnt_hls = self.footprints.geometry.interiors.apply(len)
            return cnt_hls
        except Exception as e:
            return None
        
    def _calc_cnt_nds(self):
        """Calculate number of nodes (interior & exterior)."""
        try:
            return self.footprints.count_coordinates() - 1
        except Exception as e:
            return None
        
    def _calc_ratio_c_a(self):
        """Calculate ratio circumference-area."""
        try:
            return self.circumference/self.area
        except Exception as e:
            return None

    def _calc_cnt_prts(self):
        """Calculate number of parts (disconnected polygons) per building."""
        try:
            # Count parts per parent building ID
            parts_per_building = self.loaded_data['parts'].groupby(self.config['parts']['parent_id_col']).size()
            return self.footprints[self.config['footprints']['id_col']].map(parts_per_building).fillna(1)
        except Exception as e:
            return None

    def _calc_part_id(self):
        """Get one part ID per building (for backtracing assignments)."""
        try:
            first_part = self.loaded_data['parts'].groupby(self.config['parts']['parent_id_col'])[self.config['parts']['id_col']].first()
            return self.footprints[self.config['footprints']['id_col']].map(first_part)
        except Exception as e:
            return None
        
    def _calc_shpx_2d(self):
        """Calculate Shape Index."""
        try:
            return 4 * np.pi * self.area / self.circumference**2
        except Exception as e:
            return None

    def _calc_ratio_sw(self):
        """Calculate ratio of shared walls.
        Current problem: Does not work for overlapping edges, e.g. buidling_id 3573053 and 3415842 -> 0"""
        try:
            shared = momepy.shared_walls(self.footprints)
            return shared / self.circumference
        except Exception as e:
            return None
        
    def _calc_ratio_mbr_a(self):
        """Calculate ratio of minimum bounding rectangle area to building area."""
        try:
            return self.mbr.area/self.area
        except Exception as e:
            return None

    def _calc_ratio_lw_mbr(self):
        """Calculate length/width ratio of minimum bounding rectangle."""
        # logic reversed from momepy.elongation() (https://github.com/pysal/momepy/blob/main/momepy/shape.py)
        try:
            coords = shapely.get_coordinates(self.mbr)
            # d1, d2 represent distance of two sides of bbox
            d1 = np.linalg.norm(coords[1::5] - coords[0::5], axis=1)
            d2 = np.linalg.norm(coords[2::5] - coords[1::5], axis=1)
            return np.maximum(d1, d2) / np.minimum(d1, d2)
        except Exception as e:
            return None
        
    def _calc_rf_type(self):
        """Get roof type."""
        try:
            return self.footprints[self.config['footprints']['rooftype_col']]
        except Exception as e:
            return None

    def _calc_ratio_hll_v(self):
        """Calculate ratio of hull area to volume."""
        try:
            roof_area = self.footprints[self.config['footprints']['roofarea_col']]
            wall_area = self.footprints[self.config['footprints']['wallarea_col']]
            hull_area = self.area + roof_area + wall_area
            return hull_area/self.volume
        except Exception as e:
            return None
        
    def _calc_cnt_nghb_d(self):
        """Calculate number of direct neighbours."""
        try:
            nghb_d = self._nghb_matrix[self._nghb_matrix['NEAR_DIST'] == 0]
            nghb_d_n = nghb_d.groupby('IN_FID').size()
            return nghb_d_n.reindex(self.footprints.index, fill_value=0)
        except Exception as e:
            return None
        
    def _calc_dist_nghb_d(self):
        """Calculate distance to nearest building."""
        try:
            id_n, dist_n = self.footprints.geometry.sindex.nearest(
                self.footprints.geometry,
                return_distance=True,
                return_all = False,
                exclusive = True
            )
            return pd.Series(dist_n, index=id_n[0])
        except Exception as e:
            return None
        
    def _calc_cnt_nghb_r(self):
        """Calculate number of neighbours within specified radius."""
        try:
            nghb_r = self._nghb_matrix[self._nghb_matrix['NEAR_DIST'] <= self.config['nghb_r']]
            nghb_r_n = nghb_r.groupby('IN_FID').size()
            return nghb_r_n.reindex(self.footprints.index, fill_value=0)
        except Exception as e:
            return None
        
    def _calc_dist_nghb_r(self):
        """Calculate mean distance to all buildings within specified radius."""
        try:
            nghb_r = self._nghb_matrix[self._nghb_matrix['NEAR_DIST'] <= self.config['nghb_r']]
            nghb_r_m = nghb_r.groupby('IN_FID').mean()['NEAR_DIST']
            return nghb_r_m.reindex(self.footprints.index, fill_value=np.nan)
        except Exception as e:
            return None

    def _calc_mun_code(self):
        """Get municipality code by spatial join."""
        if not hasattr(self, '_mun_sjoin'):
            self._mun_sjoin = self._calc_sjoin('municipalities')
        try:
            return self._mun_sjoin[self.config['municipalities']['mun_col']]
        except Exception as e:
            return None
        
    def _calc_planreg_code(self):
        """Get planning region code by spatial join."""
        if not hasattr(self, '_mun_sjoin'):
            self._mun_sjoin = self._calc_sjoin('municipalities')
        try:
            return self._mun_sjoin[self.config['municipalities']['planreg_col']]
        except Exception as e:
            return None
        
    def _calc_state_code(self):
        """Get state code by spatial join."""
        if not hasattr(self, '_mun_sjoin'):
            self._mun_sjoin = self._calc_sjoin('municipalities')
        try:
            return self._mun_sjoin[self.config['municipalities']['state_col']]
        except Exception as e:
            return None

    def _calc_country_code(self):
        """Get country code by spatial join."""
        if not hasattr(self, '_mun_sjoin'):
            self._mun_sjoin = self._calc_sjoin('municipalities')
        try:
            return self._mun_sjoin[self.config['municipalities']['country_col']]
        except Exception as e:
            return None

    def _calc_stypology_code(self):
        """Get spatial typology code by spatial join."""
        if not hasattr(self, '_styp_sjoin'):
            self._styp_sjoin = self._calc_sjoin('spatial_typology')
        try:
            return self._styp_sjoin[self.config['spatial_typology']['typology_col']]
        except Exception as e:
            return None

    def _calc_cnt_add(self):
        """Calculate number of address points by spatial join with a distance tolerance of 1m. This is supposed to mimic ArcGIS 1.2m XY tolerance but not perfect"""
        if not hasattr(self, '_addr_sjoin'):
            self._addr_sjoin = self._calc_sjoin('addresses')
        try:
            return self._addr_sjoin.groupby(self.config['footprints']['id_col']).count().reindex(self.footprints[self.config['footprints']['id_col']], fill_value=0).reset_index()["index_right"]
        except Exception as e:
            return None

    def _calc_street_name(self):
        """Get street name by spatial join."""
        if not hasattr(self, '_street_sjoin'):
            self._addr_sjoin = self._calc_sjoin('addresses')
        try:
            return self._street_sjoin[self.config['streets']['name_col']]
        except Exception as e:
            return None
        
    def _calc_block_id(self):
        """Get block id by spatial join."""
        # calculate sjoin blocks included in function call _get_block_id_series()
        try:
            return self._get_block_id_series()
        except Exception as e:
            return None
        
    def _calc_blck_a(self):
        """Get block area by spatial join."""
        if not hasattr(self, '_block_sjoin'):
            self._block_sjoin = self._calc_sjoin('blocks')
        try:
            return self._block_sjoin['_A_joined']
        except Exception as e:
            return None
        
    def _calc_a_mean_blck(self):
        """Calculate mean building area in block."""
        try:
            # group buildings by block and calculate mean building area
            block_id = self._get_block_id_series()
            return self.area.groupby(block_id).transform('mean')
        except Exception as e:
            return None
        
    def _calc_a_std_blck(self):
        """Calculate Standard deviation of building area in block."""
        try:
            block_id = self._get_block_id_series()
            # fill na with 0 (blocks with only one building (std = nan))
            return self.area.groupby(block_id).transform('std').fillna(0)
        except Exception as e:
            return None

    def _calc_a_sum_blck(self):
        """Calculate Sum of building area in block."""
        try:
            block_id = self._get_block_id_series()
            return self.area.groupby(block_id).transform('sum')
        except Exception as e:
            return None

    def _calc_cnt_blck(self):
        """Calculate Number of buildings in block."""
        try:
            block_id = self._get_block_id_series()
            return self.area.groupby(block_id).transform('count')
        except Exception as e:
            return None    
        
    def _calc_a_min_blck(self):
        """Calculate Minimum building area in block."""
        try:
            block_id = self._get_block_id_series()
            return self.area.groupby(block_id).transform('min')
        except Exception as e:
            return None
        
    def _calc_a_max_blck(self):
        """Calculate Maximum building area in block."""
        try:
            block_id = self._get_block_id_series()
            return self.area.groupby(block_id).transform('max')
        except Exception as e:
            return None

    def _calc_ratio_a_blck(self):
        """Calculate ratio of building area to block area."""
        if not hasattr(self, '_block_sjoin'):
            self._block_sjoin = self._calc_sjoin('blocks')
        try:
            return self.area / self._block_sjoin['_A_joined']
        except Exception as e:
            return None
        
    def _calc_ratio_a_mean_blck(self):
        """Calculate ratio of building area to mean building area in block.
        mean_area is the same calculation as _calc_a_mean_blck, but we don't know if it already exists/will be calculated at all. 
        For optimisation, a check could be added, but we don't expect a huge difference."""
        try:
            block_id = self._get_block_id_series()
            mean_area = self.area.groupby(block_id).transform('mean')
            return self.area / mean_area
        except Exception as e:
            return None
        
    def _calc_ratio_a_sum_blck(self):
        """Calculate ratio of building area to total building area in block.
        sum_area is the same calculation as _calc_a_sum_blck, optimisation possible as above."""
        try:
            block_id = self._get_block_id_series()
            sum_area = self.area.groupby(block_id).transform('sum')
            return self.area / sum_area
        except Exception as e:
            return None
        
    def _calc_v_mean_blck(self):
        """Calculate mean building volume in block. Missing height values will be ignored in the mean calculation."""
        try:
            block_id = self._get_block_id_series()
            return self.volume.groupby(block_id).transform('mean')
        except Exception as e:
            return None
        
    def _calc_v_std_blck(self):
        """Calculate Standard deviation of building volume in block. Missing height values will be ignored in the std calculation."""
        try:
            block_id = self._get_block_id_series()
            # fill na with 0 (blocks with only one building (std = nan))    
            return self.volume.groupby(block_id).transform('std').fillna(0)
        except Exception as e:
            return None 
        
    def _calc_v_sum_blck(self):
        """Calculate Sum of building volume in block. Missing height values will be ignored in the sum calculation."""
        try:
            block_id = self._get_block_id_series()
            return self.volume.groupby(block_id).transform('sum')
        except Exception as e:
            return None
        
    def _calc_ratio_v_mean_blck(self):
        """Calculate ratio of building volume to mean building volume in block. Missing height values will be ignored in the mean calculation."""
        try:
            block_id = self._get_block_id_series()
            mean_volume = self.volume.groupby(block_id).transform('mean')
            return self.volume / mean_volume
        except Exception as e:
            return None
        
    def _calc_ratio_v_sum_blck(self):
        """Calculate ratio of building volume to total building volume in block. Missing height values will be ignored in the sum calculation."""
        try:
            block_id = self._get_block_id_series()
            sum_volume = self.volume.groupby(block_id).transform('sum')
            return self.volume / sum_volume
        except Exception as e:
            return None
        
    def _calc_parcel_id(self):
        """Get parcel id by spatial join."""
        if not hasattr(self, '_parcel_sjoin'):
            self._parcel_sjoin = self._calc_sjoin('parcels')
        try:
            return self._parcel_sjoin[self.config['parcels']['id_col']]
        except Exception as e:
            return None
        
    def _calc_parcel_a(self):
        """Get parcel area by spatial join."""
        if not hasattr(self, '_parcel_sjoin'):
            self._parcel_sjoin = self._calc_sjoin('parcels')
        try:
            return self._parcel_sjoin['_A_joined']
        except Exception as e:
            return None

    def _calc_ratio_a_prcl(self):
        """Calculate ratio of building area to parcel area."""
        if not hasattr(self, '_parcel_sjoin'):
            self._parcel_sjoin = self._calc_sjoin('parcels')
        try:
            return self.area / self._parcel_sjoin['_A_joined']
        except Exception as e:
            return None

    def _calc_ratio_v_a_prcl(self):
        """Calculate ratio of building volume sum in parcel to area of parcel."""
        if not hasattr(self, '_parcel_sjoin'):
            self._parcel_sjoin = self._calc_sjoin('parcels')
        try:
            prcl_id = self._parcel_sjoin[self.config['parcels']['id_col']]
            sum_volume = self.volume.groupby(prcl_id).transform('sum') 
            return sum_volume / self._parcel_sjoin['_A_joined']
        except Exception as e:
            return None


    # Public methods
    def calculate(self,  tags=None, features=None):
        """
        Calculate specified features.

        Parameters:
        - tags: list of tags that features should be calculated for.
                If provided, all features with any of these tags are selected.
                If None, proceed to `features`.
        - features: list of feature names (e.g., ['RATIO_SW', 'HEIGHT_RATIO']),
                    or 'all' to use all registered features.
                    Added to features selected by tag.
                    If None or 'all', use all features.

        Returns:
        - self.featureset (updated)
        """
        totalstart = time.perf_counter()

        # Select features
        self._select_features(tags=tags, features=features)

        # Check required input data
        self._check_req_data()

        # Load required input data
        self._load_req_data()

        # Check required columns
        self._check_req_cols()

        # Calculate neighborhood matrix if needed
        if 'Neighbourhood' in self._selected_tags:
            self._calc_nghb_matrix()

        print(self._selected_features)

        # Calculate each feature
        for feature_name in self._selected_features:
            spec = self._feature_registry[feature_name]
            start = time.perf_counter()
            try:
                result = spec['func']()
                elapsed = time.perf_counter() - start
                if result is not None:
                    self.featureset[spec['output_col']] = result
                    print(f"✅ Calculated {feature_name} → {spec['output_col']} ({elapsed:.2f}s)")
                else:
                    print(f"❌ Failed to calculate {feature_name} ({elapsed:.2f}s)")
            except Exception as e:
                elapsed = time.perf_counter() - start
                print(f"❌ Error calculating {feature_name}: {e} ({elapsed:.2f}s)")

        print(f"\nTotal calculation time: {time.perf_counter() - totalstart:.2f}s\n")
        return self.featureset

    def write_features(self, path):

        self.featureset.to_file(path)
        print(f"Exported featureset to {path}")
