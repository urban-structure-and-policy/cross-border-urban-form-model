library(sf)
library(dplyr)
library(tidyr)
library(readr)
library(scales)
library(lubridate)
library(purrr)
library(glue)
library(gstat)
library(terra)

keep_objects <- ls()  # variables to not delete in the end

# --- PARAMETERS ---

date <- format(Sys.Date(), "%y_%m_%d")  # if using matrix folder from today use this
#date <- "25_08_04"  # if using a folder from another date, set manually here

ew_field <- "EW1"
regionfield <- "location"
interpolation_field <- "CC_mean"

merge_matrix <- TRUE
new_accessibility <- TRUE
interpolation <- TRUE

crs = st_crs(child_env$CRS)

# --- FILE INPUTS ---
municipalities_path <- file.path(resultdata, '01_AreaDefinition', '01b_communities.gpkg')
municipalities <- read_sf(dsn = municipalities_path) 

isochrones_path <- file.path(resultdata, '01_AreaDefinition', '01a_isochrones_20240606.gpkg')
isochrones <- read_sf(dsn = isochrones_path, layer = 'isochrones_separated') 


# auxiliary fields not necessary to plot
notplot <- c("id", paste0(ew_field, "_sum"), "EW_2", paste0(ew_field, "_sum_2"))


# --- MAIN LOOP ---
# Start timer
totalstart <- now()
print(format(totalstart, "%H:%M:%S"))

regions <- unique(isochrones[[regionfield]])

final_files <- c()

for (region in regions) {
  cat("\n -------- Starting for:", region,  format(now(), "%H:%M:%S"), "\n")
  folder = file.path(child_env$procdata, child_env$subdir, 'output', paste0(region,'_50perc_', date))
  print(folder)

  if (new_accessibility){
    ## 1. Merge separate matrix files and delete rows with 0
    cat("1. Merge separate matrix files...", format(now(), "%H:%M:%S"), "\n")
    
    # set merge_matrix to true for this region if specified as false but file does not exist
    merge_matrix_region <- merge_matrix
    if (!merge_matrix_region && !file.exists(file.path(folder, "matrizen_merge.csv"))) {
      merge_matrix_region <- TRUE
    }
    
    if (merge_matrix_region){
      cat(" >> Loading and merging matrix files...\n")
      
      files <- list.files(path = file.path(folder, "Matrizen"), full.names = TRUE)
      df_list <- imap(files, function(x, i) {
        if (i %% 500 == 0) {
          cat(format(now(), "%H:%M:%S"), " - Processed", i, "files\n")
        }
        data <- read_csv(x, show_col_types = FALSE)
        data %>%
          mutate(
            across(1:2, as.integer),
            across(3:4, as.numeric)
          )
      })
      df <- bind_rows(df_list)
      df.0 <- filter(df,DURATION_H != 0)
      
      write.csv(df.0, file.path(folder, "matrizen_merge.csv"), row.names = FALSE, append = FALSE)
    } else {
      cat(" >> Loading merged matrix file...\n")
      df.0 <- read_csv(file.path(folder, "matrizen_merge.csv"), show_col_types = FALSE)
    }
    
    ## 2. Einwohnerzahl hinzufügen aus Zielgeometrien, Gewichtungsspalten berechnen
    cat("2. Add inhabitant info and calculate weigths...", format(now(), "%H:%M:%S"), "\n")
    
    destins <- read_sf(dsn = file.path(folder, paste0('destination_points_1000mgrid_',region,'50perc.gpkg')))
    
    # Add population-weighted variables using power exponential decay 
    # values from https://doi.org/10.1016/j.jtrangeo.2024.104061
    
    ## for power exponential -> better than negative exponential in paper
    b1_walk_km <- 1.174
    b2_walk_km <- 0.749
    
    b1_bike_km <- 0.333
    b2_bike_km <- 0.871
    
    b1_drive_h <- 0.019
    b2_drive_h <- 1.340
    
    powerexp <- function(b1,b2,x){
      exp(-b1 * x^b2)
    }
    
    
    joined <- df.0 %>%
      left_join(destins, join_by(TO_ID == id)) %>%
      mutate(
        weight_exp_h = powerexp(b1_drive_h, b2_drive_h, DURATION_H) * EW_10,
        exp_decay_km = (powerexp(b1_walk_km, b2_walk_km, DIST_KM) + powerexp(b1_bike_km, b2_bike_km, DIST_KM))/2,  # mean of walking and cycling for short distance weighting
        weight_exp_km = exp_decay_km * EW_10,
      )
    
    
    ## 3. Centrality calculation based on travel time and distance per origin point
    cat("3. Calculate centrality values based on duration and distance...", format(now(), "%H:%M:%S"), "\n")
    
    centrality <- joined %>%
      group_by(FROM_ID) %>%
      summarise(
        exp_h_w = sum(weight_exp_h, na.rm = TRUE),       # Decay-weighted reachable population
        exp_km_w = sum(weight_exp_km, na.rm = TRUE)     
      ) %>%
      mutate(
        # Apply scaling to avoid outlier distortion
        exp_h_w_s = scale(exp_h_w),
        exp_km_w_s = scale(exp_km_w)
      )
    
    
    ## 4. Join centrality values to origin points and save results
    cat("4. Join centrality values to points...", format(now(), "%H:%M:%S"), "\n")
    
    region_points <- read_sf(dsn = file.path(folder, paste0(region,'_10perc_ew.gpkg')))
    centrality_points <- left_join(region_points, centrality, join_by(id == FROM_ID))
    
    st_write(centrality_points,file.path(folder,paste0('centrality_', region, '_50perc_inBuffer.gpkg')), append = FALSE)
    plot(centrality_points %>% select(-any_of(notplot)), max.plot = 20)
    
    
    ## 5. Clip to region shape
    cat("5. Clip to city region...", format(now(), "%H:%M:%S"), "\n")
    
    region_iso <- isochrones %>%
      filter(.data[[regionfield]] == region) %>%
      st_transform(st_crs(centrality_points)) %>% 
      st_buffer(350)  # to catch communities not intersecting any community
    communities <-  municipalities %>%
      st_transform(st_crs(centrality_points))
    
    region_shape <- communities[lengths(st_intersects(communities, region_iso)) > 0, ]
    st_write(region_shape,file.path(folder, paste0(region, '_communities.gpkg')), append = FALSE)
    
    cropped <- centrality_points[region_shape, ] %>%
      select(-c(exp_h_w, exp_km_w, paste0(ew_field, "_sum"), EW_2, paste0(ew_field, "_sum_2"))) %>%
      mutate(exp_h_w_n = scales::rescale(exp_h_w_s),  # rescale to 0-1 for comparable units for composite index
             exp_km_w_n = scales::rescale(exp_km_w_s),  # rescale to 0-1
             accessibility_hkm_n = scales::rescale((exp_h_w_n + exp_km_w_n) / 2)  # calculate composite index as mean and rescale again to 0-1 to fill out range completely
      )
    
    # rename to field structure required for our visualisation scripts
    cropped_newnames <- cropped %>%
      mutate(iso_region = region) %>%  # Add region name
      rename(CC_mean = accessibility_hkm_n,
             CC_mean_car = exp_h_w_n,
             CC_mean_shortdist = exp_km_w_n) %>%
      drop_na(CC_mean) %>%
      select(id, EW_10, CC_mean, CC_mean_car, CC_mean_shortdist, iso_region)
    
    st_write(cropped_newnames, file.path(folder, paste0('centrality_',region,'_50perc_oA.gpkg')), append = FALSE)
    
    plot(cropped %>% select(-any_of(notplot)), max.plot = 20)
  } else {
    cropped_newnames <- read_sf(file.path(folder, paste0('centrality_',region,'_50perc_oA.gpkg')))
    region_shape <- read_sf(file.path(folder, paste0(region, '_communities.gpkg')))
  }


  if (interpolation){
    ## 7. Interpolate to raster
    cat("7. Interpolate to raster", format(now(), "%H:%M:%S"), "\n")
    
    # Define the extent and resolution of the output raster
    r <- rast( ext(region_shape), resolution = 500)  # cell size = 1 (adjust as needed)
    crs(r) <- crs(cropped_newnames)
    
    idw_model <- gstat(formula = as.formula(paste(interpolation_field, "~ 1")), locations = cropped_newnames, nmax = 7, set = list(idp = 4))
    
    interpolate_gstat <- function(model, x, crs, ...) {
      v <- st_as_sf(x, coords=c("x", "y"), crs=crs)
      p <- predict(model, v, ...)
      as.data.frame(p)[,1:2]
    }
    idw_result <- interpolate(r, idw_model, debug.level=0, fun=interpolate_gstat, crs=crs(r), index=1)
    idw_result <- mask(idw_result, region_shape)
    
    # Save as GeoTIFF
    interpolation_output <- file.path(child_env$procdata, child_env$subdir, 'output', "interpolation", interpolation_field)
    if (!dir.exists(interpolation_output)) {dir.create(interpolation_output, recursive = TRUE)}
    outraster <- file.path(interpolation_output, glue("interpolation_{region}_idp4.tif"))
    writeRaster(idw_result, filename = outraster, overwrite = TRUE)
    
    plot(idw_result)
  }
}

rm(list = setdiff(ls(), keep_objects))
gc()

cat("Finished!", format(now(), "%H:%M:%S"), "\n")
