library(lubridate)
library(qgisprocess)
library(fs)

totalstart <- now()
cat("Start:", format(totalstart, "%H:%M:%S"), "\n")

# Define input and output directories
addr_in <- file.path(resultdata, "00_Harmonisation", "00b_01_addresses", "00b_01_addresses.gpkg")
bldg_in <- file.path(procdata, child_env$subdir, "00b_02_04_parts_to_building", "00b_02_04b_buildings.gpkg")
bldg_out <- file.path(procdata, child_env$subdir, "00b_02_05_join_addr_to_bldg", "00b_02_05_buildings.gpkg")

## temp files
temp_dir <- file.path(procdata, child_env$subdir, "00b_02_05_join_addr_to_bldg", "temp")
dir_create(temp_dir)
join   <- file.path(temp_dir, "joinbynearest.gpkg")
dupli  <- file.path(temp_dir, "deleteduplicates.gpkg")


# --- Join by nearest
cat("join by nearest...", format(now(), "%H:%M:%S"), "\n")
qgis_run_algorithm(
  "native:joinbynearest",
  INPUT = bldg_in,
  INPUT_2 = addr_in,
  FIELDS_TO_COPY = c("AGS_INSEE", "street", "number"),
  DISCARD_NONMATCHING = FALSE,
  PREFIX = "",
  NEIGHBORS = 1,
  MAX_DISTANCE = 20,
  OUTPUT = join
)

# Remove duplicates by building_id
cat("delete duplicate building ids...", format(now(), "%H:%M:%S"), "\n")
qgis_run_algorithm(
  "native:removeduplicatesbyattribute",
  INPUT = join,
  FIELDS = "building_id",
  OUTPUT = dupli
)

# Delete unwanted columns
cat("delete columns...", format(now(), "%H:%M:%S"), "\n")
qgis_run_algorithm(
  "native:deletecolumn",
  INPUT = dupli,
  COLUMN = c("n", "distance", "feature_x", "feature_y", "nearest_x", "nearest_y"),
  OUTPUT = bldg_out
)

cat("Finished at:", format(now(), "%H:%M:%S"), 
    "\nTotal time:", format(now() - totalstart), "\n")
