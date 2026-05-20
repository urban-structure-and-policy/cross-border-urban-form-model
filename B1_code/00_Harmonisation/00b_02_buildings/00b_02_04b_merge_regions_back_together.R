library(lubridate)
library(sf)

cat("\n---\nStart:", format(now(), "%H:%M:%S"), "\n")


# Define input and output directories
parts_in <- file.path(procdata, child_env$subdir, "00b_02_03_join_frde", "00b_02_03_parts.gpkg")
buildingsdir <- file.path(procdata, child_env$subdir, "00b_02_04_parts_to_building", "00b_02_04a_buildings")
buildings_out <- file.path(procdata, child_env$subdir, "00b_02_04_parts_to_building", "00b_02_04b_buildings.gpkg")
parts_out <- file.path(procdata, child_env$subdir, "00b_02_04_parts_to_building", "00b_02_04b_parts.gpkg")
temp_dir <- file.path(procdata, child_env$subdir, "00b_02_04_parts_to_building", "temp")
dir_create(temp_dir)

inpaths <- dir_ls(buildingsdir)

# Merge layers
cat("merge layers...", format(now(), "%H:%M:%S"), "\n")
merge <- qgis_run_algorithm(
  "native:mergevectorlayers",
  LAYERS = inpaths,
  CRS = glue("EPSG:{child_env$CRS}"),
  OUTPUT = file.path(temp_dir, "merged.gpkg")
)

# Drop fields
cat("drop fields...", format(now(), "%H:%M:%S"), "\n")
dropf <- qgis_run_algorithm(
  "native:deletecolumn",
  INPUT = merge[["OUTPUT"]],
  COLUMN = c("layer", "path"),
  OUTPUT = file.path(temp_dir, "dropfields.gpkg"),
  .quiet = TRUE
)

# Assign building ID
cat("assign building id...", format(now(), "%H:%M:%S"), "\n")
bldg04 <- qgis_run_algorithm(
  "native:fieldcalculator",
  INPUT = dropf[["OUTPUT"]],
  FIELD_NAME = "building_id",
  FIELD_TYPE = 1,
  FIELD_LENGTH = 0,
  FIELD_PRECISION = 0,
  FORMULA = "@id",
  OUTPUT = buildings_out,
  .quiet = TRUE
)

# Join building ID to parts
cat("join building id to parts...", format(now(), "%H:%M:%S"), "\n")

qgis_run_algorithm("native:createspatialindex", INPUT = bldg04[["OUTPUT"]])
qgis_run_algorithm("native:createspatialindex", INPUT = parts_in)

parts04 <- qgis_run_algorithm(
  "native:joinattributesbylocation",
  INPUT = parts_in,
  PREDICATE = 0,  # intersects
  JOIN = bldg04[["OUTPUT"]],
  JOIN_FIELDS = "building_id",
  METHOD = 2,  # one-to-one, keep all records
  DISCARD_NONMATCHING = FALSE,
  PREFIX = "",
  OUTPUT = parts_out
)

cat("\n---\nFinished at", format(now(), "%H:%M:%S"), "\n")