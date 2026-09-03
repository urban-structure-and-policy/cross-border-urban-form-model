library(reticulate)
library(dplyr)
library(lubridate)


## reticulate setup

# activate or create environment based on selection
if (python_env == "venv"){
  venv_path <- file.path(child_env$subdir, "venv") 
  
  if (!dir.exists(venv_path)) {
    message("Creating virtual environment at: ", venv_path)
    system(paste("python", "-m venv", venv_path))
  } else {
    message("Using virtual environment at: ", venv_path)
  }
  
  if (Sys.info()[["sysname"]] == "Windows") {
    py_exe <- file.path(venv_path, "Scripts", "python.exe")
  } else {
    py_exe <- file.path(venv_path, "bin", "python")
  }
} else if (python_env == "conda"){
  conda_env = "urbanmetrics"
  
  conda_list <- conda_list()
  if (conda_env %in% conda_list$name) {
    py_exe <- conda_list$python[conda_list$name == conda_env]
    cat("Using existing conda environment: ", conda_env)
  } else {
    cat("Creating new conda environment: ", conda_env)
    conda_create(envname = conda_env, conda = conda_exe)
    conda_list <- conda_list(conda = conda_exe)  # refresh list
    py_exe <- conda_list$python[conda_list$name == conda_env]
  }
} else {
  message("Please specify 'conda' or 'venv' for python environment.")
}

# tell reticulate to use this python 
use_python(py_exe, required = TRUE)

# Install packages if missing
missing_pkgs <- setdiff(
  c("geopandas", "momepy", "shapely", "numpy", "pandas", "tobler"),
  py_list_packages()$package
)
if (length(missing_pkgs) > 0) {
  message("Installing missing Python packages: ", paste(missing_pkgs, collapse = ", "))
  py_install(packages = missing_pkgs)
} else {
  message("All Python packages are already installed.")
}

## Running toolbox

# Pass configuration dictionaries as nested lists 
paths <- list(
  input = list(
    footprints = file.path(resultdata, '00_Harmonisation/00b_02_buildings/00b_02_buildings.gpkg'),
    municipalities = file.path(resultdata, '00_Harmonisation/00a_municipalities/00a_municipalities.gpkg'),
    blocks = file.path(resultdata, '02c_DevelopmentBlockIdentification/02c_03_DevelopmentBlocks.gpkg'),
    parcels = file.path(resultdata, '00_Harmonisation/00c_parcels/00c_parcels.gpkg'),
    addresses = file.path(resultdata, '00_Harmonisation/00b_01_addresses/00b_01_addresses.gpkg'),
    residential_lookup = file.path(procdata, child_env$subdir, '03_01b_list_residential.csv'),
    parts = file.path(resultdata, '00_Harmonisation/00b_02_buildings/00b_02_parts.gpkg')
  ),
  process = list(
    nghb_matrix_base = file.path(procdata, child_env$subdir, '03_01b_nghb_matrix')
  ),
  output = list(
    result = file.path(procdata, child_env$subdir, '03_01b_buildingmetrics.gpkg')
  )
)

renamefeatures <- list(
  FNC = 'function',
  PART_ID = 'part_id',
  BLOCK_ID = 'block_id',
  PRCL_ID = 'parcel_id',
  MUN_CODE = 'AGS_INSEE',
  STATE = 'region',
  COUNTRY = 'country'
)

config <- list(
  crs = 'EPSG:32632',
  nghb_r = 50,
  join_method = 'largest_overlap',
  skip_unspecified = TRUE,
  skip_unavailable = TRUE,
  check_overlaps = FALSE,
  footprints = list(
    height_col = 'height',
    function_col = 'function',
    id_col = 'building_id'
  ),
  municipalities = list(
    mun_col = 'key',
    state_col = 'region',
    country_col = 'country'
  ),
  blocks = list(
    id_col = 'block_id'
  ),
  parcels = list(
    id_col = 'parcel_id'
  ),
  parts = list(
    id_col = 'part_id',
    parent_id_col = 'building_id'
  )
)

source_python(file.path(scriptdir, child_env$subdir, "03_01a_urban_metrics_toolbox.py"), envir = globalenv(), convert = TRUE)

feature_class <- Features_on_building_level(
  paths = paths,
  config = config,
  renamefeatures = renamefeatures
)

featureset <- feature_class$calculate(tags=list("FFP")) %>% 
  select(-geometry) # geometry column does not translate well to R data.frame but write_features from class works fine for geometries


message("Export metrics as csv to result data...", format(now(), "%H:%M:%S"))
out_csv = file.path(resultdata, child_env$subdir, '03_01b_buildings_metrics.csv')
write.csv(featureset_no_geom, out_csv, row.names = FALSE)

rm(list = c("Features_on_building_level", "feature_class", "featureset", "out_csv", "config", "paths", "renamefeatures", "missing_pkgs"))

message("Finished at ", format(now(), "%H:%M:%S"))
