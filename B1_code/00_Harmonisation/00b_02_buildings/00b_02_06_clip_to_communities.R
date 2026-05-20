library(lubridate)
library(qgisprocess)
library(fs)

totalstart <- now()
cat("Start:", format(totalstart, "%H:%M:%S"), "\n")

# --- Directories ---

# Inputs
bldg_in <- file.path(procdata, child_env$subdir, "00b_02_05_join_addr_to_bldg", "00b_02_05_buildings.gpkg")
parts_in <- file.path(procdata, child_env$subdir, "00b_02_04_parts_to_building", "00b_02_04b_parts.gpkg")
comms <- file.path(resultdata, "01_AreaDefinition", "01b_communities.gpkg")

# Outputs
bldg_out <- file.path(resultdata, child_env$subdir, "00b_02_buildings.gpkg")
parts_out <- file.path(resultdata, child_env$subdir, "00b_02_parts.gpkg")
bldg_gdb <- file.path(resultdata, child_env$subdir, "00b_02_buildings.gdb")
parts_gdb <- file.path(resultdata, child_env$subdir, "00b_02_parts.gdb")

# --- 1. Extract by location ---
cat("buildings: extract by location...", format(now(), "%H:%M:%S"), "\n")
qgis_run_algorithm(
  "native:extractbylocation",
  INPUT = bldg_in,
  PREDICATE = 0, # intersects
  INTERSECT = comms,
  OUTPUT = bldg_out
)

cat("parts: extract by location...", format(now(), "%H:%M:%S"), "\n")
qgis_run_algorithm(
  "native:extractbylocation",
  INPUT = parts_in,
  PREDICATE = 0, # intersects
  INTERSECT = comms,
  OUTPUT = parts_out
)

# --- 2. Save to GDB ---
cat("parts: add to gdb...", format(now(), "%H:%M:%S"), "\n")
qgis_run_algorithm(
  "native:savefeatures",
  INPUT = parts_out,
  OUTPUT = parts_gdb,
  LAYER_NAME = "parts",
  DATASOURCE_OPTIONS = "",
  LAYER_OPTIONS = ""
)

cat("buildings: add to gdb...", format(now(), "%H:%M:%S"), "\n")
qgis_run_algorithm(
  "native:savefeatures",
  INPUT = bldg_out,
  OUTPUT = bldg_gdb,
  LAYER_NAME = "buildings",
  DATASOURCE_OPTIONS = "",
  LAYER_OPTIONS = ""
)

cat("Finished at:", format(now(), "%H:%M:%S"),
    "\nTotal time:", format(now() - totalstart), "\n")
