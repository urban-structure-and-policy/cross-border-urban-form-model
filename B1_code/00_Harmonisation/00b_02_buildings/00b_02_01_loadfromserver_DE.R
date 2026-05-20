
# >> Run script in an environment that has arcpy loaded

library(lubridate)

# Allow overwriting
arcpy$env$overwriteOutput <- TRUE

# Set working directory
wd <- file.path(basedata, "DE", "GEBÄUDE")

# Start timer
totalstart <- now()
cat("Start time:", format(totalstart, "%H:%M:%S"), "\n")

# Define function
gdbtogpkg <- function(state, partsorbuildings) {
  starttime <- now()
  cat(state, format(starttime, "%H:%M:%S"), "\n")
  
  saveDir <- file.path(wd, state)
  if (!dir.exists(saveDir)) dir.create(saveDir, recursive = TRUE)
  
  fclass <- switch(
    partsorbuildings,
    "buildings" = "_Gebaeude",
    "parts" = "",
    stop("Invalid string: use 'parts' or 'buildings'")
  )
  
  out_gpkg <- file.path(saveDir, paste0(state, "_lod", lodyear, "_", partsorbuildings, ".gpkg"))
  
  # Create the GPKG
  cat("Creating GPKG...\n")
  arcpy$management$CreateSQLiteDatabase(out_database_name = out_gpkg, spatial_type = "GEOPACKAGE")
  
  # Set input feature class path
  in_gdb <- file.path(paste0("path/on/server", lodyear, "_LoD2-DE/gdb"),
                      paste0(state, ".gdb"), paste0("Umring_2D", fclass))
  
  # Define target layer name inside GPKG
  out_layer <- paste0(out_gpkg, "/", state, "_lod", lodyear)
  
  # Copy features
  cat("Copying features...\n")
  arcpy$management$CopyFeatures(in_features = in_gdb, out_feature_class = out_layer)
  
  cat("Iteration time:", now() - starttime, "\n")
}

# Run the function for several states
for (s in c("rp", "bw", "he")) {
  tryCatch({
    gdbtogpkg(s, "parts")
  }, error = function(e) cat("Error in parts for", s, ":", e$message, "\n"))
  
  tryCatch({
    gdbtogpkg(s, "buildings")
  }, error = function(e) cat("Error in buildings for", s, ":", e$message, "\n"))
}

cat("Total time:", now() - totalstart, "\n")