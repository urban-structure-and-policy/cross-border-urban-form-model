suppressPackageStartupMessages({
  library(fs)
  library(glue)
  library(lubridate)
})

total_start <- now()
print(format(total_start, "%H:%M:%S"))

# Define input and output directories
in_dir <- file.path(procdata, child_env$subdir, "00b_02_02_prepareforjoin", "00b_02_02b_fieldcalculation")
out_dir <- file.path(procdata, child_env$subdir, "00b_02_03_join_frde")
temp_dir <- file.path(out_dir, "temp")

# Ensure temp directory exists
dir_create(c(temp_dir, out_dir))

# List all GPKG layers in input directory
in_paths <- dir_ls(in_dir, regexp = "\\.gpkg$", recurse = FALSE)

# Step 1: Merge layers
cat("merge layers...", format(now(), "%H:%M:%S"), "\n")
merged <- qgis_run_algorithm(
  "native:mergevectorlayers",
  LAYERS = in_paths,
  CRS = glue("EPSG:{child_env$CRS}"),
  OUTPUT = path(temp_dir, "merge.gpkg")
)

# Step 2: Delete duplicate geometries
cat("delete duplicates...", format(now(), "%H:%M:%S"), "\n")
dedup <- qgis_run_algorithm(
  "native:deleteduplicategeometries",
  INPUT = merged$OUTPUT,
  OUTPUT = path(temp_dir, "deleteduplicates.gpkg")
)

# Step 3: Drop 'layer' and 'path' fields
cat("drop fields...", format(now(), "%H:%M:%S"), "\n")
qgis_run_algorithm(
  "native:deletecolumn",
  INPUT = dedup$OUTPUT,
  COLUMN = c("layer", "path"),
  OUTPUT = path(out_dir, "00b_02_03_parts.gpkg")
)

# Print total time
total_time <- now() - total_start
cat("total time:", total_time, "\n")

rm(list = c("merged", "dedup"))