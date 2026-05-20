library(sf)
library(dplyr)
library(lubridate)

accessibility_field = "CC_mean"

# Start timer
totalstart <- now()
print(format(totalstart, "%H:%M:%S"))

# read blocks

bblocks_path <- file.path(resultdata, '02c_DevelopmentBlockIdentification', '02c_03_DevelopmentBlocks.gpkg')
bblocks <- st_read(bblocks_path) %>%
  filter(!st_is_empty(.))

# join each points to building blocks for both regions

join_points_bblocks <- function(region) {
  folder = file.path(procdata, child_env$subdir, 'output', paste0(region,'_50perc'))

  # prepare point data
  centralityoA_path <- file.path(folder, paste0('centrality_',region,'_50perc_oA.gpkg'))
  centralityoA = st_read(centralityoA_path) %>%
    rename(accessibility_hkm_n = all_of(accessibility_field))

  if (st_crs(bblocks) != st_crs(centralityoA)) {
    centralityoA <- st_transform(centralityoA, st_crs(bblocks))
  }

  # crop building blocks
  region_shape <- read_sf(dsn = file.path(folder, paste0(region, '_communities.gpkg')))
  if (st_crs(region_shape) != st_crs(bblocks)) {
    region_shape <- st_transform(region_shape, st_crs(bblocks))
  }
  bblocks_cropped <- bblocks[region_shape, ]

  # join nearest point to bblocks
  bblocks_joined <- bblocks_cropped %>%
    st_join(subset(centralityoA, select = c(accessibility_hkm_n)), join = st_nearest_feature)

  st_write(bblocks_joined, file.path(folder, paste0('blocks_nn_pc_acc_',region,'.gpkg')), append=FALSE)
  plot(bblocks_joined %>% select(accessibility_hkm_n), border = NA)

  return (bblocks_joined)
}

cat("Join points to blocks for STR...", format(now(), "%H:%M:%S"), "\n")
bblocks_str <- join_points_bblocks('Iso_STR') %>% st_drop_geometry()

cat("Join points to blocks for KAR...", format(now(), "%H:%M:%S"), "\n")
bblocks_kar <- join_points_bblocks('Iso_KAR') %>% st_drop_geometry()

## join building blocks together

cat("Join blocks for regions together...", format(now(), "%H:%M:%S"), "\n")
bblocks_acc <- bblocks %>%
  left_join(subset(bblocks_str, select = c(block_id, accessibility_hkm_n)), by = join_by(block_id)) %>%
  left_join(subset(bblocks_kar, select = c(block_id, accessibility_hkm_n)), by = join_by(block_id), suffix = c("_STR", "_KAR")) %>%
  mutate(
    accessibility_hkm_n = pmax(accessibility_hkm_n_STR, accessibility_hkm_n_KAR, na.rm = TRUE),  # Take the max while ignoring NAs
    accessibility_hkm_n_center = if_else(
      !is.na(accessibility_hkm_n_STR) & accessibility_hkm_n == accessibility_hkm_n_STR, "STR",   # If STR is not NA and matches max column, return "STR"
      if_else(!is.na(accessibility_hkm_n_KAR), "KAR", NA_character_)   # otherwise return "KAR" if it is not NA
    )
  )

plot(bblocks_acc %>% select(accessibility_hkm_n), border = NA)

st_write(bblocks_acc, file.path(resultdata, child_env$subdir, "05a_03b_devblocks_accessibility.gpkg"), append=FALSE)

rm (list = c( "totalstart", "bblocks_path",  "bblocks",  "join_points_bblocks",  "bblocks_str",  "bblocks_kar",  "bblocks_acc"))
gc()
