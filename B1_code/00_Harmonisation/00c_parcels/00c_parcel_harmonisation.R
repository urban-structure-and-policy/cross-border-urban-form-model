# =============================================================================
# SCRIPT: Merge German and French cadastral parcels into a single GeoPackage
# =============================================================================

library(lubridate)  # for timestamps and durations
library(dplyr)      # mutate, rename, select, filter
library(stringr)    # str_detect
library(sf)         # for spatial vector data
library(fs)         # file system operations
library(tools)      # file_path_sans_ext
library(lwgeom)     # st_make_valid

# -----------------------------
# Start timer
# -----------------------------
totalstart <- now()
cat("Script start:", format(totalstart, "%H:%M:%S"), "\n")

# -----------------------------
# Directories and Parameters
# -----------------------------
indir_de <- file.path(basedata, "DE/FLURSTÜCKE")         # German input folder
indir_fr <- file.path(basedata, "FR")                    # French input folder
outdir   <- file.path(procdata, child_env$subdir)        # working output folder
finalout <- file.path(resultdata, child_env$subdir, "00c_parcels.gpkg")  # final merged file

# Make sure output subdirectory exists
dir.create(outdir, recursive = TRUE, showWarnings = FALSE)

pcrs <- 32632  # target CRS for all outputs

# Regions
reg_fr <- c(57, 67)       #, 54, 68, 88)    # French departements
reg_de <- c("rp", "bw")   #, "he")          # German states

# Load communities table
communities.path <- file.path(resultdata, '01_AreaDefinition', '01b_communities.gpkg')
communities <- st_read(communities.path, quiet = TRUE) %>% st_drop_geometry()
ags_field <- if ("key" %in% colnames(communities)) "key" else "AGS_INSEE" 

# Get AGS codes in communities layer and handle missing leading zeros in Germany (7 instead of 8 digits, France has 5 digits)
ags_codes <- as.character(communities[[ags_field]])  
ags_codes <- ifelse(nchar(ags_codes) == 7, paste0("0", ags_codes), ags_codes)

# -----------------------------
# Germany: process single zip files per community
# -----------------------------
state_files <- list()  # list to store state-level sf objects

for (state in reg_de) {
  
  # Timer for this state
  statestart <- now()
  message("Processing German state: ", state, " — Start: ", format(statestart, "%H:%M:%S"))
  
  ags_paths <- c()
  
  # Paths for zip files and extraction
  zip_dir <- file.path(indir_de, state)
  unzip_dir <- file.path(indir_de, "unzip_communities20", state)
  
  zip_files <- dir_ls(zip_dir, glob = "*.zip")
  
  # Loop over AGS codes for this state
  for (ags in ags_codes){
    
    # Find zip corresponding to this AGS
    match <- zip_files[str_detect(basename(zip_files), paste0("^", ags))]
    
    if(length(match) > 0) {
      zip_path <- match[1]
      zip_name <- file_path_sans_ext(basename(zip_path))
      
      target_dir <- file.path(unzip_dir, zip_name)
      ags_shp <- file.path(target_dir, "ALKIS-Vereinfacht", paste0(zip_name, ".shp"))
      
      # Skip if already unzipped
      if (dir_exists(target_dir) && file_exists(ags_shp)) {
        message(" - Skipping ", zip_name, " — already unzipped.")
        ags_paths <- c(ags_paths, ags_shp)
        next
      }
      
      # If not unzipped yet, create folder and unzip
      dir_create(target_dir)
      message(" - Unzipping: ", zip_name)
      unzip(zip_path, exdir = target_dir)
      
      ags_paths <- c(ags_paths, ags_shp)
    }
  }
  
  message("Finished unzipping for: ", state, "\n - Duration: ", now()-statestart, "\n" )
  
  # -----------------------------
  # Transform individual layers and reduce fields
  # -----------------------------
  transform_start <- now()
  message("Transforming individual layers for ", state, "\n - Start: ", transform_start)
  
  shp_list <- lapply(ags_paths, \(p) {  # anonymous function
    sf <- st_read(p, quiet = TRUE) %>%
      mutate(perimeter = sf::st_perimeter(.),
             area = st_area(.)) %>%
      rename(AGS_INSEE = gmdschl,
             parcel_id = idflurst) %>%
      select(perimeter, area, parcel_id, AGS_INSEE, geometry) %>%
      st_make_valid() %>%
      st_transform(crs = pcrs)
  })
  
  message("Finished transforming layers for ", state, "\n - Duration: ", now()-transform_start, "\n")
  
  # -----------------------------
  # Merge all community layers into a state layer
  # -----------------------------
  merge_start <- now()
  message("Merging layers and exporting merged file for ", state, "\n - Start: ", merge_start)
  
  state_merge_path <- file.path(outdir, paste0("00c_parcels_", state, ".gpkg"))
  merged_sf <- do.call(rbind, shp_list)
  rm(shp_list); gc()
  
  st_write(merged_sf, state_merge_path, append=FALSE, quiet = TRUE)
  
  state_files <- append(state_files, list(merged_sf))
  rm(merged_sf); gc()
  
  message("Finished merging and exporting for ", state, "\n - Duration: ", now()-merge_start, "\n")
}

# -----------------------------
# France: process shapefiles per departement
# -----------------------------
for (dep in reg_fr) {
  
  depstart <- now()
  message("Processing French departement: ", dep, " — Start: ", format(depstart, "%H:%M:%S"))
  
  dep_shp <- file.path(indir_fr, paste0("cadastre-", dep, "-parcelles-shp"), "parcelles.shp")
  
  # Transform layer and reduce fields
  transform_start <- now()
  message("Transforming French layer for departement ", dep, "\n - Start: ", transform_start)
  
  clean_sf <- st_read(dep_shp, quiet = TRUE) %>%
    mutate(perimeter = sf::st_perimeter(.),
           area = st_area(.)) %>%
    rename(AGS_INSEE = commune,
           parcel_id = id) %>%
    select(perimeter, area, parcel_id, AGS_INSEE, geometry) %>%
    filter(AGS_INSEE %in% ags_codes) %>%
    st_make_valid() %>%
    st_transform(crs = pcrs)
  
  message("Finished transforming French layer for departement ", dep, "\n - Duration: ", now()-transform_start, "\n")
  
  # Export French departement layer
  export_start <- now()
  dep_clean_path <- file.path(outdir, paste0("00c_parcels_fr", dep, ".gpkg"))
  st_write(clean_sf, dep_clean_path, append=FALSE, quiet = TRUE)
  
  state_files <- append(state_files, list(clean_sf))
  rm(clean_sf); gc()
  
  message("Finished exporting French layer for departement ", dep, "\n - Duration: ", now()-export_start, "\n")
}

# -----------------------------
# Merge all regions into final GeoPackage
# -----------------------------
merge_start <- now()
cat("\nMerging all regions into final GeoPackage\nStart: ", format(merge_start, "%H:%M:%S"), "\n")

merged_allregions <- do.call(rbind, state_files)
st_write(merged_allregions, finalout, append=FALSE, quiet = TRUE)
rm(merged_allregions, state_files); gc()

cat("Finished all regions\nTotal duration: ", now() - totalstart, "\n")
