library(sf)
library(lubridate)

## INPUT

parts_in <- file.path(procdata, child_env$subdir, "00b_02_02_prepareforjoin", "00b_02_02a_clip_communitiesbuffer20")
function_harmonisation.p <- file.path(procdata, child_env$subdir, "00b_02_02ba_atkis_frz.csv")
function_harmonisation <- read.csv2(function_harmonisation.p, encoding = "latin1")


## OUTPUT

fieldcalc_out <- file.path(procdata, child_env$subdir, "00b_02_02_prepareforjoin", "00b_02_02b_fieldcalculation")
dir_create(fieldcalc_out)


## FUNCTION DEFINITION for field calculation

fieldcalc <- function (parts_region, region, function.f, partid.f, height.f, rooftype.f){
  parts <- parts_region %>%
    rename(bldg_function = function.f,
           part_id = partid.f,
           height = height.f,
           roof_type = rooftype.f) %>%
    filter(str_starts(bldg_function, "3")) %>%
    mutate(
      area = as.numeric(st_area(geom)),
      perimeter = as.numeric(st_length(st_boundary(geom))),
      volume = area * height,
      country = "de",
      region = region
    ) %>% 
    left_join(function_harmonisation %>% select(-function_name), by = "bldg_function") %>%
    select(part_id,area,perimeter,height,volume,building_function,country,region,roof_type)
  return(parts)
}

## MAIN LOOP over regions

for (region in c('rp', 'bw', 'he')) {
  cat("\n---\nProcessing:", region, format(now(), "%H:%M:%S"), "\n")
  parts_region.p <- file.path(parts_in, paste0(region, "_parts.gpkg"))
  parts_region <- read_sf(parts_region.p)
  parts_newfields <- fieldcalc(parts_region, region, function.f = "funktion", partid.f = "gml_id", height.f = "Gebaeude_Hoehe", rooftype.f = "citygml_roof_type")
  parts_out <- file.path(fieldcalc_out, paste0(region, "_parts.gpkg"))
  st_write(parts_newfields, parts_out, append = FALSE)
}

cat("\n---\nFinished at", format(now(), "%H:%M:%S"), "\n")

# free memory
rm(
  parts_in,
  function_harmonisation.p,
  function_harmonisation,
  fieldcalc_out,
  region,
  parts_region.p,
  parts_region,
  parts_newfields,
  parts_out
)
gc()
