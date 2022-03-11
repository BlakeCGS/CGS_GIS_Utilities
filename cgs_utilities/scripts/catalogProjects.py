import arcpy
import os
import csv
import json
import sys


def main():
    try:
        folder_of_maps_and_projects = arcpy.GetParameterAsText(0)
        report_location = arcpy.GetParameterAsText(1)
        catalogFolder(folder_of_maps_and_projects, report_location)
    except Exception as e:
        if type(e) is arcpy.ExecuteError:
            arcpy.AddMessage(arcpy.GetMessages(2))
        tb = sys.exc_info()[2]
        arcpy.AddMessage(f"ERROR @ Line {tb.tb_lineno} in file {__file__} with error: {sys.exc_info()[1]}")

def catalogFolder(folder_of_maps_and_projects, report_location):
    pro_project_template = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'EmptyProProject/EmptyProProject.aprx')
    with open(report_location, mode='w+', newline='') as outCsv:
        writeCsv = csv.writer(outCsv)
        writeCsv.writerow(['FileName','FileType','FilePath','LayerOrTable', 'IsBroken', 'FullName','Type', 'Source', 'Workspace', 'WorkspaceType', 'Dataset','DefQuery'])
        for root, dirs, files in os.walk(folder_of_maps_and_projects):
            for fileName in [f for f in files if f.endswith('.mxd') or f.endswith('.aprx')]:
                fullPath = os.path.join(root, fileName)
                arcpy.AddMessage(f'Catalogging Document {fullPath}')
                #if fullPath == '\\gis-fs1\GISServerFiles\mxd\EMAOfflineBasemap.mxd':
                #    arcpy.AddMessage('Stop')
                if os.path.splitext(fullPath)[1] == '.mxd':
                    proProject = arcpy.mp.ArcGISProject(pro_project_template)
                    proProject.importDocument(fullPath, False)
                    fileType = "Map Document"
                else:
                    proProject = arcpy.mp.ArcGISProject(fullPath)
                    fileType = "Pro Project"
                
                for map in proProject.listMaps():
                    arcpy.AddMessage(f'Catalogging Map: {map.name}')
                    for lyr in map.listLayers():
                        if not lyr.isGroupLayer:
                            layerName = getPropIfAvailable(lyr, 'name')
                            arcpy.AddMessage(f'Layer: {layerName}')
                            props = getLayerOrTableProperties(lyr)
                            # Write the results to the CSV
                            writeCsv.writerow([fileName, fileType, fullPath, layerName, props.isBroken, props.fullName, props.itemType, props.dataSource, props.workspace, props.workspaceType, props.dataset, props.defQuery])

                    for tbl in map.listTables():
                        tableName = getPropIfAvailable(tbl, 'name')
                        arcpy.AddMessage(f'Table: {tableName}')
                        props = getLayerOrTableProperties(tbl)
                        # Write the results to the CSV
                        writeCsv.writerow([fileName, fileType, fullPath, tableName, props.isBroken, props.fullName, props.itemType, props.dataSource, props.workspace, props.workspaceType, props.dataset, props.defQuery])

def readConfig(filepath):
    # Open config file
    with open(filepath, 'r') as configFile:
        configData = configFile.read()
    config = json.loads(configData)
    return config

def getLayerOrTableProperties(layerOrTable):
    retProperties = layerOrTableProps()
    conProps = None
    conProps = getPropIfAvailable(layerOrTable, 'connectionProperties')
    if conProps is not None:
        retProperties.dataset = conProps['dataset'] if 'dataset' in conProps.keys() else 'None'
        retProperties.workspaceType = conProps['workspace_factory'] if 'workspace_factory' in conProps.keys() else 'None'
        if 'connection_info' in conProps.keys():
            retProperties.workspace = conProps['connection_info']['database'] if 'database' in conProps['connection_info'].keys() else 'None'
    retProperties.defQuery = getPropIfAvailable(layerOrTable, 'definitionQuery')
    retProperties.itemType = getMapItemType(layerOrTable)
    retProperties.dataSource = getPropIfAvailable(layerOrTable, 'dataSource')
    retProperties.name = getPropIfAvailable(layerOrTable, 'name')
    retProperties.fullName = getPropIfAvailable(layerOrTable, 'longName')
    retProperties.isBroken = getPropIfAvailable(layerOrTable, 'isBroken')
    return retProperties

def getPropIfAvailable(layerOrTable, objProperty):
    try:
        if hasattr(layerOrTable, objProperty):
            return getattr(layerOrTable, objProperty)
        else:
            return None
    except:
        return None

def getMapItemType(layerOrTable):
    if type(layerOrTable) is arcpy.mp.Table:
        return "Table"
    else:
        if layerOrTable.is3DLayer:
            return "3D Layer"
        elif layerOrTable.isBasemapLayer:
            return "Basemap Layer"
        elif layerOrTable.isFeatureLayer:
            return "Feature Layer"
        elif layerOrTable.isGroupLayer:
            return "Group Layer"
        elif layerOrTable.isNetworkAnalystLayer:
            return "Network Analyst Layer"
        elif layerOrTable.isNetworkDatasetLayer:
            return "Network Dataset Layer"
        elif layerOrTable.isRasterLayer:
            return "Raster Layer"
        elif layerOrTable.isSceneLayer:
            return "Scene Layer"
        elif layerOrTable.isWebLayer:
            return "Web Layer"

class layerOrTableProps():
    def __init__(self):
        self.workspace = None
        self.workspaceType = None
        self.dataset = None
        self.defQuery = None
        self.itemType = None
        self.dataSource = None
        self.name = None
        self.fullName = None
        self.isBroken = None

if __name__ == '__main__':
    main()

