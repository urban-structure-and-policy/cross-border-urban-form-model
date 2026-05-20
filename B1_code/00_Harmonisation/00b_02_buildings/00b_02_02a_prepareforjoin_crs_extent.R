
# Load libraries

suppressPackageStartupMessages({
  library(sf)
  library(dplyr)
  library(purrr)
  library(glue)
  library(lubridate)
  library(fs)
})

# Start timer
total_start <- now()
cat("Start time:", format(total_start, "%H:%M:%S"), "\n")

# Define directories
in_dir <- basedata
out_dir <- file.path(procdata, child_env$subdir, "00b_02_02_prepareforjoin")

# Target CRS (UTM zone 32N)
target_crs <- st_crs(child_env$CRS)

# Create output subdirectories if they don't exist
dir_create(out_dir)
dir_create(file.path(out_dir, "00b_02_02a_clip_communitiesbuffer20"))

# Clip layer (communities + 20 km buffer)
buffdist <- if (test) 200 else 20000  # set buffer smaller for test data
comm_path <- file.path(resultdata, "01_AreaDefinition", "01b_communities.gpkg")
clip_layer <- st_read(comm_path, quiet = TRUE) %>%
  st_union() %>%
  st_buffer(dist = buffdist)

# Departments
dep = 67  # only need 67 dep layer because it has all other departments because they are adjacent 
dep_path <- glue("{in_dir}/FR/BDTOPO_3-0_TOUSTHEMES_SHP_LAMB93_D0{dep}_2021-03-15/BDTOPO_3-0_TOUSTHEMES_SHP_LAMB93_D0{dep}_2021-03-15/BDTOPO/1_DONNEES_LIVRAISON_2021-03-00272/BDT_3-0_SHP_LAMB93_D0{dep}-ED2021-03-15/ADMINISTRATIF/DEPARTEMENT.shp")
cat("\n---\nProcessing: Departements", format(now(), "%H:%M:%S"), "\n")
dep_layer <- st_read(dep_path, quiet = TRUE)
if (!st_crs(dep_layer) == st_crs(target_crs)) {
  cat("  Reprojecting department layer...\n")
  dep_layer <- st_transform(dep_layer, crs = target_crs)
} else {
  cat("  Already in taregt CRS.\n")
}
dep_reproj_path <- file.path(out_dir, "departements.gpkg")
st_write(dep_layer, dep_reproj_path, delete_dsn = TRUE, quiet = TRUE)
cat("  Done with departements", "\n")

# Helper functions
fr_paths <- function(dep) {
  # 2021
  path <- glue("{in_dir}/FR/BDTOPO_3-0_TOUSTHEMES_SHP_LAMB93_D0{dep}_2021-03-15/BDTOPO_3-0_TOUSTHEMES_SHP_LAMB93_D0{dep}_2021-03-15/BDTOPO/1_DONNEES_LIVRAISON_2021-03-00272/BDT_3-0_SHP_LAMB93_D0{dep}-ED2021-03-15/BATI/BATIMENT.shp")
  outname <- glue("fr{dep}_parts")
  list(path = path, name = outname)
}

de_paths <- function(state) {
  path <- file.path(in_dir, glue("DE/GEBÄUDE/{state}/{state}_lod{lodyear}_parts.gpkg"))
  outname <- glue("{state}_parts")
  list(path = path, name = outname)
}

# Define all input datasets
fr_inputs <- lapply(c(57, 67, 54, 68, 88), fr_paths)
de_inputs <- lapply(c("rp", "bw", "he"), de_paths)
all_inputs <- c(fr_inputs, de_inputs)

# Process each dataset
walk(all_inputs, function(input) {
  path <- input$path
  outname <- input$name
  
  cat("\n---\nProcessing:", outname, format(now(), "%H:%M:%S"), "\n")
  
  # Read the input
  layer <- tryCatch({
    st_read(path, quiet = TRUE)
  }, error = function(e) {
    cat("  ERROR reading:", path, "\n"); return(NULL)
  })
  
  if (is.null(layer)) return(NULL)
  
  # Reproject if needed
  if (!st_crs(layer) == st_crs(target_crs)) {
    cat("  Reprojecting...\n")
    layer <- st_transform(layer, crs = target_crs)
  } else {
    cat("  Already in target CRS.\n")
  }
  
  # Clip to buffer
  cat("  Clipping to communities buffer...\n")
  layer_clipped <- tryCatch({
    st_intersection(layer, clip_layer)
  }, error = function(e) {
    cat("  ERROR clipping:", outname, "\n"); return(NULL)
  })
  
  if (is.null(layer_clipped)) return(NULL)
  
  # Save clipped result
  clip_path <- file.path(out_dir, "00b_02_02a_clip_communitiesbuffer20", paste0(outname, ".gpkg"))
  st_write(layer_clipped, clip_path, append = FALSE, quiet = TRUE)
  cat("  Done with", outname, "\n")
})

# Total duration
cat("\nAll done.\nTotal processing time:", now() - total_start, "\n")


rm(list = c("dep_layer", "clip_layer", "fr_inputs", "de_inputs", "all_inputs", "layer", "layer_clipped"))