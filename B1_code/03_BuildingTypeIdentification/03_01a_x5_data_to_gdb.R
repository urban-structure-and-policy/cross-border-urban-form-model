library(qgisprocess)
library(lubridate)

# Start timer
totalstart <- now()
print(format(totalstart, "%H:%M:%S"))

# Input paths
bloc <- file.path(resultdata, "02c_DevelopmentBlockIdentification", "02c_03_DevelopmentBlocks.gpkg")
addr <- file.path(resultdata, "00_Harmonisation", "00b_01_addresses", "00b_01_addresses.gpkg")
parc <- file.path(resultdata, "00_Harmonisation", "00c_parcels", "00c_parcels.gpkg")

# Output paths
outdir <- normalizePath(file.path(procdata, subdir, "03_01a_x5_data"), mustWork = FALSE)
if (!dir.exists(outdir)) dir.create(outdir, recursive = TRUE)
bloc_gdb <- file.path(outdir, "blocks.gdb")
addr_gdb <- file.path(outdir, "addresses.gdb")
parc_gdb <- file.path(outdir, "parcels.gdb")
bloc_temp <- file.path(outdir, "bloc_temp.gpkg")

# Ensure QGIS is loaded
qgis_configure()

# Save addresses
cat("addr: add to gdb...", format(now(), "%H:%M:%S"), "\n")
qgis_run_algorithm(
  "native:savefeatures",
  INPUT = addr,
  OUTPUT = addr_gdb,
  LAYER_NAME = "addresses",
  DATASOURCE_OPTIONS = "",
  LAYER_OPTIONS = ""
)

# Save parcels
cat("parc: add to gdb...", format(now(), "%H:%M:%S"), "\n")
qgis_run_algorithm(
  "native:savefeatures",
  INPUT = parc,
  OUTPUT = parc_gdb,
  LAYER_NAME = "parcels",
  DATASOURCE_OPTIONS = "",
  LAYER_OPTIONS = ""
)

# Retain fields from blocks
cat("bloc: retain fields...", format(now(), "%H:%M:%S"), "\n")
bloc_clean <- qgis_run_algorithm(
  "native:retainfields",
  INPUT = bloc,
  FIELDS = c("block_id", "street", "AGS_INSEE", "parcel_id", "region", "country"),
  OUTPUT = bloc_temp
)

# Save cleaned blocks
cat("bloc: add to gdb...", format(now(), "%H:%M:%S"), "\n")
qgis_run_algorithm(
  "native:savefeatures",
  INPUT = bloc_clean$OUTPUT,
  OUTPUT = bloc_gdb,
  LAYER_NAME = "blocks",
  DATASOURCE_OPTIONS = "",
  LAYER_OPTIONS = ""
)

file.remove(bloc_temp)

rm(list = c("bloc", "addr", "parc", "outdir", "bloc_gdb", "addr_gdb", "parc_gdb", "bloc_temp"))

cat("Finished at", format(now(), "%H:%M:%S"))
