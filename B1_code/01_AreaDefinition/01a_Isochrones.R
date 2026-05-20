
library("openrouteservice")
library("dplyr")
library("sf")

ors_url <- "http://url/ors"

# check ORS url
if (!exists("ors_url") || is.null(ors_url) || !nzchar(ors_url)) {
  stop("No ORS url provided. Please set `ors_url` to your local instance.")
}

# set up ORS
options(openrouteservice.url = ors_url)

# paths
coords_path <- file.path(procdata, child_env$subdir, "central_points.gpkg")  # created manually
iso_out <- file.path(resultdata, child_env$subdir, "01a_isochrones.gpkg")
  
# load coordinates and make into correct format
coord_sf  <- read_sf(coords_path) %>%
  st_transform(4326) 

coords_mat <- st_coordinates(coord_sf)

# calculate 45 minute range for each center point and merge isochrones
iso_separate <- ors_isochrones(coords_mat, profile = "driving-car", range_type = "time", range = 2700, output = "sf", smoothing = 0) %>%
  st_make_valid() %>%
  select(geometry) %>% 
  st_transform(crs = 32632) 

iso_separate$location <- coord_sf$location

iso_union <- iso_separate %>%
  st_union() %>%
  st_sf()

iso_union$location <- "union"

st_write(iso_separate, iso_out,
         layer = "isochrones_separate",
         delete_layer = TRUE)

st_write(iso_union, iso_out,
         layer = "isochrones",
         delete_layer = TRUE)
  