library(readr)
library(dplyr)
library(sf)
library(qgisprocess)

indir_de <- file.path(basedata, "DE/Adressdaten")
indir_fr <- file.path(basedata, "FR")
outdir   <- file.path(procdata, child_env$subdir)
finalout <- file.path(resultdata, child_env$subdir, "00b_01_addresses.gpkg")

# make sure subdirectories exist
dir.create(file.path(outdir, "00b_01_input"), recursive = TRUE, showWarnings = FALSE)
dir.create(file.path(outdir, "00b_01a_csv_to_gpkg"), recursive = TRUE, showWarnings = FALSE)
dir.create(file.path(outdir, "00b_01b_merge"), recursive = TRUE, showWarnings = FALSE)
dir.create(file.path(outdir, "00b_01c_clip"), recursive = TRUE, showWarnings = FALSE)

pcrs <- child_env$CRS

# get communities buffer
communities.path <- file.path(resultdata, '01_AreaDefinition', '01b_communities.gpkg')
combuffer20_path <- file.path(outdir, "00b_01_input", "communities_buffer20km.gpkg")
combuffer20 <- st_read(communities.path) %>% 
  st_union() %>%
  st_buffer(20000) %>%
  st_write(combuffer20_path)


# --- Function for German CSVs ---
csv_to_gpkg_de <- function(state) {
  message(state, " ", Sys.time())
  adr_path <- file.path(indir_de, paste0("ga_", state, ".csv"))
  
  df <- read_csv2(adr_path, col_names = FALSE, locale = locale(decimal_mark = ",")) 
  
  gdf <- st_as_sf(
    df,
    coords = c(13, 14), # columns 13,14 are x,y
    crs = 25832
  )
  
  gdf <- gdf %>%
    mutate(
      AGS_INSEE = paste0("0", as.character(X4), X5, X6),
      number = as.integer(X11),
      street = X15
    ) %>%
    select(AGS_INSEE, street, number, geometry) %>%
    st_transform(pcrs)
  
  outpath <- file.path(outdir, "00b_01a_csv_to_gpkg", paste0(state, ".gpkg"))
  st_write(gdf, outpath, delete_dsn = TRUE, quiet = TRUE)
  outpath
}

# --- Function for French CSVs ---
csv_to_gpkg_fr <- function(dep) {
  message(dep, " ", Sys.time())
  adr_path <- file.path(indir_fr, paste0("adresses-", dep, ".csv"), paste0("adresses-", dep, ".csv"))
  
  df <- read_delim(adr_path)
  
  gdf <- st_as_sf(df, coords = c("x", "y"), crs = 2154) %>%
    rename(number = numero, street = nom_voie, AGS_INSEE = code_insee) %>%
    select(AGS_INSEE, street, number, geometry) %>%
    st_transform(pcrs)
  
  outpath <- file.path(outdir, "00b_01a_csv_to_gpkg", paste0("fr", dep, ".gpkg"))
  st_write(gdf, outpath, delete_dsn = TRUE, quiet = TRUE, append = FALSE)
  outpath
}

# --- Start ---
totalstart <- Sys.time()
print(totalstart)

outpaths <- c(
  lapply(c("rp", "bw", "he"), csv_to_gpkg_de),
  lapply(c(54, 57, 67, 68, 88), csv_to_gpkg_fr)
) |> unlist()

# --- Merge vector layers ---
message("merge vector layers ", Sys.time())
merged <- qgis_run_algorithm(
  "native:mergevectorlayers",
  LAYERS = outpaths,
  CRS = paste0("EPSG:", pcrs),
  OUTPUT = file.path(outdir, "00b_01b_merge", "addresses_merged.gpkg")
)

# --- Clip by buffer ---
message("extract by location ", Sys.time())
clipped <- qgis_run_algorithm(
  "native:extractbylocation",
  INPUT = merged$OUTPUT,
  PREDICATE = 0,
  INTERSECT = combuffer20_path,
  OUTPUT = file.path(outdir, "00b_01c_clip", "addresses_clip.gpkg")
)

# --- Drop columns ---
message("drop layer and path fields")
deletecols <- qgis_run_algorithm(
  "native:deletecolumn",
  INPUT = clipped$OUTPUT,
  COLUMN = c("layer", "path"),
  OUTPUT = file.path(outdir, "00b_01c_clip", "addresses_dropcolumns.gpkg")
)

# --- Delete duplicates ---
message("delete duplicates")
qgis_run_algorithm(
  "native:deleteduplicategeometries",
  INPUT = deletecols$OUTPUT,
  OUTPUT = finalout
)

print(Sys.time() - totalstart)
print("end")
