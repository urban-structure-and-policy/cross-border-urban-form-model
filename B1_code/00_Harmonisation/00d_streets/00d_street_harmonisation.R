# =============================================================================
# SCRIPT: Merge German and French street and river network into a single GeoPackage
# =============================================================================

library(lubridate)  # for timestamps and durations
library(dplyr)      # mutate, rename, select, filter
library(sf)         # for spatial vector data

# -----------------------------
# Start timer
# -----------------------------
totalstart <- now()
cat("Script start:", format(totalstart, "%H:%M:%S"), "\n")

# -----------------------------
# Directories and Parameters
# -----------------------------

rivers <- TRUE
outname <- ifelse(rivers, "streetriver", "street")

indir_de <- file.path(basedata, "DE/STRASSEN")           # German input folder
indir_fr <- file.path(basedata, "FR")                    # French input folder
outdir   <- file.path(procdata, child_env$subdir, outname)  # working output folder
finalout <- file.path(resultdata, child_env$subdir, paste0("00d_", outname, ".gpkg"))  # final merged file

# Make sure output subdirectory exists
dir.create(outdir, recursive = TRUE, showWarnings = FALSE)

pcrs <- child_env$CRS  # target CRS for all outputs

# Regions
reg_fr <- c(57, 67)       #, 54, 68, 88)    # French departements
reg_de <- c("rp", "bw")   #, "he")          # German states

# file names
fnames_fr <- c("itineraire_autre", "route_numerotee_ou_nommee", "troncon_de_route", "troncon_de_voie_ferree", "voie_ferree_nommee")
fnames_de <- c("ver01_l.shp", "ver02_l.shp")
if (rivers){
  fnames_fr <- c(fnames_fr, "troncon_hydrographique","cours_d_eau")
  fnames_de <- c(fnames_de, "gew01_l.shp", "gew03_l.shp")
}

# Load selected communities
communities.path <- file.path(resultdata, '01_AreaDefinition', '01b_communities.gpkg')
communities <- st_read(communities.path, quiet = TRUE) %>% select(geom, key, region)

# -----------------------------
# Functions: 
# -----------------------------

state_files <- list()  # list to store merged state-level sf objects

# layer transformation function
cleanlayer <- function(layer, statecode){
  st_geometry(layer) = "geometry"
  comm_sub <- filter(communities, region == statecode)
  shp <- layer %>%
    st_make_valid() %>%
    st_transform(crs = pcrs) %>%
    select(geometry) %>%
    st_filter(comm_sub, .pred = st_intersects) %>%
    st_intersection(comm_sub %>% st_buffer(20)) %>%
    st_join(comm_sub, largest = TRUE) %>%
    filter(st_is(., c("LINESTRING", "MULTILINESTRING")))
}

mergelayers <- function(single_files, statecode){
  state_merge_path <- file.path(outdir, paste0("00d_", statecode, ".gpkg"))
  merged_sf <- do.call(rbind, single_files)
  rm(single_files); gc()
  
  st_write(merged_sf, state_merge_path, append=FALSE, quiet = TRUE)
  return(merged_sf)
}

# Germany: --------------------
for (state in reg_de) {
  
  statecode <- state
  
  # Timer for this state
  statestart <- now()
  message("Processing region: ", statecode, "... — Start: ", format(statestart, "%H:%M:%S"))
  
  state_dir <- file.path(indir_de, state)

  single_files <- list()  # list to store individual state-level sf objects
  
  for (fname in fnames_de){
    layer <- file.path(state_dir, fname) %>%
      st_read(quiet = TRUE)
    shp <- cleanlayer(layer, statecode)
    single_files <- append(single_files, list(shp))
  }
  
  message(" >> Finished transformation.\n - Duration: ", now()-statestart, "\n" )
  
  merge_start <- now()
  message(" > Merging layers and exporting merged file...\n - Start: ", merge_start)
  
  merged_sf <- mergelayers(single_files, statecode)
  
  state_files <- append(state_files, list(merged_sf))
  rm(merged_sf); gc()
  
  message(" >> Finished merging and exporting. \n - Duration: ", now()-merge_start, "\n")
  }


# France: --------------------

for (state in reg_fr) {
  
  statecode <- paste0("fr", state)
  
  # Timer for this state
  statestart <- now()
  message("Processing region: ", statecode, "... — Start: ", format(statestart, "%H:%M:%S"))
  
  state_gpkg <- file.path(indir_fr, 
                          paste0("BDTOPO_3-0_TOUSTHEMES_GPKG_LAMB93_D0", state, "_2021-03-15"), 
                          "BDTOPO", 
                          "1_DONNEES_LIVRAISON_2021-04-00014", 
                          paste0("BDT_3-0_GPKG_LAMB93_D0", state, "-ED2021-03-15"), 
                          paste0("BDT_3-0_GPKG_LAMB93_D0", state, "-ED2021-03-15.gpkg"))
  
  single_files <- list()  # list to store individual state-level sf objects
  
  for (fname in fnames_fr){
    layer <- st_read(state_gpkg, layer = fname, quiet = TRUE)
    shp <- cleanlayer(layer, statecode)
    single_files <- append(single_files, list(shp))
  }
  
  message(" >> Finished transformation.\n - Duration: ", now()-statestart, "\n" )
  
  merge_start <- now()
  message(" > Merging layers and exporting merged file...\n - Start: ", merge_start)
  
  merged_sf <- mergelayers(single_files, statecode)
  
  state_files <- append(state_files, list(merged_sf))
  rm(merged_sf); gc()
  
  message(" >> Finished merging and exporting. \n - Duration: ", now()-merge_start, "\n")
}

# Merge regions: --------------------

merge_start <- now()
message("Merging all region layers and exporting merged file...\n - Start: ", merge_start)

merged_sf <- do.call(rbind, state_files) %>%
  distinct()
rm(state_files); gc()

st_write(merged_sf, finalout, append=FALSE, quiet = TRUE)

message("Finished!\n - Time: ", now())