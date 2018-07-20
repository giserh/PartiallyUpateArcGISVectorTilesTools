# -*- coding: utf-8 -*-
# !/usr/bin/python
__author__ = 'mu_xiaoyan'
# Version     : 1.1.0
# Start Time  : 2017-12-07
# Update Time : 2018-7-20
# Change Log  :
##      1. Repalced print() with arcpy.AddError() to make the tool more informational.
##      2. Added error reporting when the partial vector tile index has no feature.
##      3. Optimized Error handling mechanism in Function create_partial_vtpk().
##      4. Added LOD user defined parameter to this Tool and Updated tool UI.
##      5. Added timeStamp to the name of the new partial index polygons to keep the name unique.

import arcpy
import os
import shutil
import time
import zipfile
import sys


# uncompress the .zip file to folder
def unzip(newPartZipPath):
    try:
        file_zip = zipfile.ZipFile(newPartZipPath, 'r')
        for file in file_zip.namelist():
            # print "unziping..."
            extractFolder = os.path.splitext(newPartZipPath)[0]
            file_zip.extract(file, extractFolder)
        file_zip.close()
        os.remove(newPartZipPath)
        #arcpy.AddMessage("unzip succeed!")
        return extractFolder
    except:
        arcpy.AddError("unzip failed, please provde a validates path")
        return ""

# Analyzing Original vtpk file to get the tiling scheme and index polygon and also get the service type
def analysis_original_vtpk(origin_vtpk_path):

    origin_workspace = os.path.dirname(origin_vtpk_path)
    origin_vtpk_name = os.path.basename(origin_vtpk_path)
    # Create temp workspace
    timeStamp = time.strftime('%Y%m%d%H%M%S', time.localtime(time.time()))
    temp_workspace = os.path.join(origin_workspace, str(timeStamp))
    os.mkdir(temp_workspace)
    try:
        # copy original vtpk
        bak_original_vtpk = shutil.copy(origin_vtpk_path, temp_workspace)
        unzip(bak_original_vtpk)
        # Locate vtpk aux files
        tile_scheme_name = "customizedScheme.xml"
        index_polygon_name = "originMasterIndex.shp"
        vtpk_extract_dir = origin_vtpk_name.split(".")[0]
        arcpy.AddMessage(vtpk_extract_dir)
        aux_files_path = temp_workspace+ r"\\"+ vtpk_extract_dir+ r"\AdvVtpkAuxFiles"
        index_polygon = os.path.join(aux_files_path, index_polygon_name)
        tile_scheme = os.path.join(aux_files_path, tile_scheme_name)
        # get the service type
        if os.path.exists(tile_scheme):
            service_type = "EXISTING"
        else:
            tile_scheme = ""
            service_type = "ONLINE"
        aux_paras = [index_polygon, tile_scheme, service_type,temp_workspace]
        return aux_paras
    except:
        arcpy.AddError("Original vtpk does not exist.")

# Create Partial VTPK in AOI
def create_partial_vtpk(workspace, index_polygon, AOI, in_map, LOD, out_part_vtpk, service_type, tile_scheme):
    arcpy.AddMessage(service_type)
    arcpy.env.workspace = workspace
    arcpy.AddMessage("Current workspace: {0}".format(arcpy.env.workspace))
    AOI_lyr = arcpy.MakeFeatureLayer_management(AOI, "AOI_lyr")
    IndexPolygon_lyr = arcpy.MakeFeatureLayer_management(index_polygon, "IndexPolygon_lyr")
    # Finding indexed polygons overlaped AOI
    arcpy.SelectLayerByLocation_management(IndexPolygon_lyr, 'intersect', AOI_lyr)
    # Finding indexed polygons whose LOD not lower than specified
    arcpy.SelectLayerByAttribute_management(IndexPolygon_lyr, 'SUBSET_SELECTION', str(' "LOD" >= ' + str(LOD)))
    # Update at 2018-7-20
    # Added timeStamp to the name of the new partial index polygons.
    timeStamp = time.strftime('%Y%m%d%H%M%S', time.localtime(time.time()))
    partialIndex = 'PartialIndex_'+str(timeStamp)+'.shp'
    arcpy.CopyFeatures_management(IndexPolygon_lyr, partialIndex)
    IndexPolygon_lyr.visible = False
    AOI_lyr.visible = False
    try:
        # Update at 2018-7-20
        # Added error reporting when the partial vector tile index has no feature.
        flag = arcpy.GetCount_management(partialIndex)
        arcpy.AddMessage(partialIndex+" feature counts: "+str(flag[0]))
        if int(flag[0]) > 0:
            arcpy.AddMessage('New index layer has been generated.')
            arcpy.CreateVectorTilePackage_management(in_map=in_map,
                                                     output_file=out_part_vtpk,
                                                     service_type=service_type,
                                                     tiling_scheme=tile_scheme,
                                                     tile_structure="INDEXED",
                                                     index_polygons=partialIndex)
        else:
            arcpy.AddError("The LOD value is too large. Try to specify a smaller one.")

    # Update at 2018-7-20, optimized Error handling mechanism
    # Previous Code:
    ## except Exception as err:
    ##     arcpy.AddError(err)
    except arcpy.ExecuteError:
        severity = arcpy.GetMaxSeverity()
        if severity == 2:
            # If the tool returned an error
            arcpy.AddError("Error occurred \n{0}".format(arcpy.GetMessages(2)))
        elif severity == 1:
            # If the tool returned no errors, but returned a warning
            arcpy.AddWarning("Warning raised \n{0}".format(arcpy.GetMessages(1)))
        else:
            # If the tool did not return an error or a warning
            arcpy.AddMessage(arcpy.GetMessages())
    # arcpy.Delete_management('NewIndex.shp')
    return True

def main(argv=None):
    # Input map in the current project
    in_map = arcpy.GetParameterAsText(0)
    arcpy.AddMessage("Input map : {0}.".format(in_map))

    # Specify the area where the delta new part vtpk need to be created
    AOI = arcpy.GetParameterAsText(1)
    arcpy.AddMessage("AOI : {0}.".format(AOI))

    # Choose the existing original adv vtpk
    origin_vtpk = arcpy.GetParameterAsText(2)
    arcpy.AddMessage("Original vtpk : {0}.".format(origin_vtpk))

    # Specify name and workspace for new part vtpk
    out_part_vtpk = arcpy.GetParameterAsText(3)
    arcpy.AddMessage("New part vtpk : {0}.".format(out_part_vtpk))

    # Specify the LOD value, from which the vtpk begins to build
    # LOD = calculate_LOD()
    LOD = arcpy.GetParameterAsText(4)
    arcpy.AddMessage("LOD - beginning tile level: {0}.".format(LOD))

    execute(in_map, AOI, origin_vtpk, out_part_vtpk,LOD)

def execute(in_map, AOI, origin_vtpk_path, out_part_vtpk,LOD):
    workspace = os.path.dirname(out_part_vtpk)
    aux_paras = analysis_original_vtpk(origin_vtpk_path)
    index_polygon = aux_paras[0]
    tile_scheme = aux_paras[1]
    service_type = aux_paras[2]
    temp_workspace = aux_paras[3]
    arcpy.AddMessage(index_polygon + "/n"+tile_scheme+"/n"+service_type)
    # Excute create_partial_vtpk function
    create_partial_vtpk(workspace, index_polygon, AOI, in_map, LOD, out_part_vtpk, service_type, tile_scheme)
    if os.path.exists(out_part_vtpk):
        shutil.rmtree(temp_workspace)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
