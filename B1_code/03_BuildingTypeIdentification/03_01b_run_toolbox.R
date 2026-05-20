# >> Run script in an environment that has arcpy loaded

library(lubridate)

# allow overwriting
arcpy$env$overwriteOutput <- TRUE

# Start timer
totalstart <- now()

# Define paths
worksp <- file.path(procdata, subdir, "03_01b_metrics_workspace.gdb")
toolb <- file.path(scriptdir, subdir,"03_01_toolbox", "PE_toolbox_beta_ffp.atbx")
x5data <- file.path(procdata, subdir, "03_01a_x5_data")

# Import Toolbox
arcpy$ImportToolbox(toolb)

# Create workspace gdb if not exists
if (!arcpy$Exists(worksp)) {
  cat("Creating workspace gdb...", format(now(), "%H:%M:%S"), "\n")
  dir_path <- dirname(worksp)
  gdb_name <- basename(worksp)
  arcpy$management$CreateFileGDB(out_folder_path = dir_path, out_name = gdb_name)
}
cat(arcpy$GetMessages(), "\n")

# Step 1: Import toolbox and run LoD preparation
## 11:30 hours
cat("Step 1...", format(now(), "%H:%M:%S"), "\n")
arcpy$PEworkflowbeta$lodpreparation(
  workspace = worksp,
  fc_parts = file.path(resultdata, "00_Harmonisation", "00b_02_buildings", "00b_02_parts.gdb/parts"),
  fc_footprints = file.path(resultdata, "00_Harmonisation", "00b_02_buildings", "00b_02_buildings.gdb/buildings"),
  f_dissolve = "building_id",
  f_function = "function",
  f_volume = "volume",
  f_height = "height",
  f_selector = "volume",
  t_residential = file.path(procdata, subdir, "03_01b_list_residential.csv"),
  fc_out = file.path(worksp, "x1_buildings")
)
cat(arcpy$GetMessages(), "\n")

# Step 3: Basic geometric features
## 4:45 hours
cat("Step 3...", format(now(), "%H:%M:%S"), "\n"); flush.console()
arcpy$PEworkflowbeta$basicgeometricfeatures(
  workspace = worksp,
  fc_in = file.path(worksp, "x1_buildings"),
  f_area = "area",
  f_cir = "perimeter",
  f_height = "HEIGHT_IMPUTED",
  f_volume = "VOLUME_IMPUTED",
  f_wallarea = NULL,
  f_roofarea = NULL,
  fc_out = file.path(worksp, "x3_buildings")
)
cat(arcpy$GetMessages(), "\n")

# Step 4: Neighbour features
## 4:40 hours
cat("Step 4...", format(now(), "%H:%M:%S"), "\n"); flush.console()
arcpy$PEworkflowbeta$neighbourfeatures(
  workspace = worksp,
  fc_in = file.path(worksp, "x3_buildings"),
  radius = "50",
  fc_out = file.path(worksp, "x4_buildings")
)
cat(arcpy$GetMessages(), "\n")

# Step 5: Parcel analysis
cat("Step 5...", format(now(), "%H:%M:%S"), "\n"); flush.console()
arcpy$PEworkflowbeta$parcelanalysis(
  workspace = worksp,
  fc_in = file.path(worksp, "x4_buildings"),
  f_id = "building_id",
  fc_addresses = file.path(x5data, "addresses.gdb/addresses"),
  fc_blocks = file.path(x5data, "blocks.gdb/blocks"),
  f_block_id = "block_id",
  fc_parcels = file.path(x5data, "parcels.gdb/parcels"),
  f_parcel_id = "parcel_id",
  fc_out = file.path(worksp, "x5_buildings")
)
cat(arcpy$GetMessages(), "\n")

# Final export
cat("Export metrics as csv to result data...", format(now(), "%H:%M:%S"), "\n")
fmap <- 'fid "fid" true true false 8 Double 0 0,First,#,x5_buildings,fid,-1,-1;function "function" true true false 65536 Text 0 0,First,#,x5_buildings,function,0,65535;country "country" true true false 2 Text 0 0,First,#,x5_buildings,country,0,1;region "region" true true false 4 Text 0 0,First,#,x5_buildings,region,0,3;perimeter "perimeter" true true false 8 Double 0 0,First,#,x5_buildings,perimeter,-1,-1;area "area" true true false 8 Double 0 0,First,#,x5_buildings,area,-1,-1;height "height" true true false 8 Double 0 0,First,#,x5_buildings,height,-1,-1;volume "volume" true true false 8 Double 0 0,First,#,x5_buildings,volume,-1,-1;part_id "part_id" true true false 50 Text 0 0,First,#,x5_buildings,part_id,0,49;building_id "building_id" true true false 4 Long 0 0,First,#,x5_buildings,building_id,-1,-1;parcel_id "parcel_id" true true false 65536 Text 0 0,First,#,x5_buildings,parcel_id,0,65535;block_id "block_id" true true false 4 Long 0 0,First,#,x5_buildings,block_id,-1,-1;AGS_INSEE "AGS_INSEE" true true false 65536 Text 0 0,First,#,x5_buildings,AGS_INSEE,0,65535;street "street" true true false 65536 Text 0 0,First,#,x5_buildings,street,0,65535;number "number" true true false 8 Double 0 0,First,#,x5_buildings,number,-1,-1;CNT_PRTS "CNT_PRTS" true true false 4 Long 0 0,First,#,x5_buildings,CNT_PRTS,-1,-1;FNC_CODE "FNC_CODE" true true false 4 Long 0 0,First,#,x5_buildings,FNC_CODE,-1,-1;IS_RES "IS_RES" true true false 4 Long 0 0,First,#,x5_buildings,IS_RES,-1,-1;A "A" true true false 4 Float 0 0,First,#,x5_buildings,A,-1,-1;C "C" true true false 4 Float 0 0,First,#,x5_buildings,C,-1,-1;H "H" true true false 4 Float 0 0,First,#,x5_buildings,H,-1,-1;V "V" true true false 4 Float 0 0,First,#,x5_buildings,V,-1,-1;SHPX_2D "SHPX_2D" true true false 4 Float 0 0,First,#,x5_buildings,SHPX_2D,-1,-1;RATIO_C_A "RATIO_C_A" true true false 4 Float 0 0,First,#,x5_buildings,RATIO_C_A,-1,-1;RATIO_MBR_A "RATIO_MBR_A" true true false 4 Float 0 0,First,#,x5_buildings,RATIO_MBR_A,-1,-1;CNT_NDS "CNT_NDS" true true false 2 Short 0 0,First,#,x5_buildings,CNT_NDS,-1,-1;DIST_NGHB_D "DIST_NGHB_D" true true false 8 Double 0 0,First,#,x5_buildings,DIST_NGHB_D,-1,-1;CNT_NGHB_D "CNT_NGHB_D" true true false 4 Long 0 0,First,#,x5_buildings,CNT_NGHB_D,-1,-1;RATIO_SW "RATIO_SW" true true false 4 Float 0 0,First,#,x5_buildings,RATIO_SW,-1,-1;CNT_NGHB_R50 "CNT_NGHB_R50" true true false 4 Long 0 0,First,#,x5_buildings,CNT_NGHB_R50,-1,-1;DIST_NGHB_R50 "DIST_NGHB_R50" true true false 8 Double 0 0,First,#,x5_buildings,DIST_NGHB_R50,-1,-1;CNT_ADD "CNT_ADD" true true false 8 Double 0 0,First,#,x5_buildings,CNT_ADD,-1,-1;BLCK_A "BLCK_A" true true false 4 Float 0 0,First,#,x5_buildings,BLCK_A,-1,-1;PRCL_A "PRCL_A" true true false 4 Float 0 0,First,#,x5_buildings,PRCL_A,-1,-1;RATIO_A_PRCL "RATIO_A_PRCL" true true false 4 Float 0 0,First,#,x5_buildings,RATIO_A_PRCL,-1,-1'
arcpy$conversion$ExportTable(
  in_table = file.path(worksp, "x5_buildings"),
  out_table = file.path(resultdata, subdir, "03_01b_buildings_metrics.csv"),
  where_clause = "",
  use_field_alias_as_name = "NOT_USE_ALIAS",
  field_mapping = fmap,
  sort_field = NULL
)
cat(arcpy$GetMessages(), "\n")

rm(list = c("worksp", "toolb", "x5data"), envir = child_env)

cat("Finished at", format(now(), "%H:%M:%S"))
