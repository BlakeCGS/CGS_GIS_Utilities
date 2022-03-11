from arcgis.gis import GIS
from arcgis.features import FeatureLayerCollection
import arcpy
import os
import pandas as pd
import sys


def main():
    try:
        portal = arcpy.GetParameterAsText(0)
        user = arcpy.GetParameterAsText(1)
        password = arcpy.GetParameterAsText(2)
        in_report = arcpy.GetParameterAsText(3)
        itemId = arcpy.GetParameterAsText(4)
        ago_name = arcpy.GetParameterAsText(5)
        
        # Create the GIS connection
        gis = gisCon(portal,user,password)

        if itemId != "":
            arcpy.AddMessage ("Updating Report")
            updateCsvReport(gis, in_report, itemId)
        else:
            arcpy.AddMessage ("Publishing Report")
            publishCsvReport(gis, in_report, ago_name)
    except Exception as e:
        if type(e) is arcpy.ExecuteError:
            arcpy.AddMessage(arcpy.GetMessages(2))
        tb = sys.exc_info()[2]
        arcpy.AddMessage(f"ERROR @ Line {tb.tb_lineno} in file {__file__} with error: {sys.exc_info()[1]}")


def gisCon(portal, user, password):
    if portal.upper() == "PRO":
        return GIS("pro")
    else:
        return GIS(portal, user, password)


def publishCsvReport(gis, in_report, ago_name):
    thumbnail_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'images/thumb.png')
    in_report_name = (os.path.basename(in_report))

    # Create New CSV if ago_name is filled.
    if ago_name != "":
        report_loc = os.path.dirname(in_report)
        new_report = os.path.join(report_loc,f"{ago_name}.csv")
        with open(in_report, "r") as input:
            with open(new_report, "x") as output:
                for line in input:
                    output.write(line)
        in_report_name = (os.path.basename(new_report))
        in_report = new_report
    else:
        ago_name = f'{os.path.splitext(in_report_name)[0]}'
    
    csv_properties = {'type':'CSV', 'title':ago_name,
                    'description':f'This CSV is {ago_name}',
                    'tags':['cultivate','cgs','gis','automation','python'],
                    'overwrite':'true'}
    # Add the CSV to AGO
    arcpy.AddMessage("################################ Publishing ###############################")
    arcpy.AddMessage(f"Publishing {in_report_name} file...")
    csv_item = gis.content.add(item_properties=csv_properties, data=in_report, thumbnail=thumbnail_path)
    
    # Publish the CSV to a Feature Serv
    arcpy.AddMessage(f"Publishing {in_report_name} service...")
    publish_parameters={"type":"csv", "locationType":"none", "name":ago_name}
    csv_lyr = csv_item.publish(publish_parameters=publish_parameters)

    # Enable Editor Tracking
    flc = FeatureLayerCollection(csv_lyr.url,gis)
    edit_dict = {"editorTrackingInfo":{"enableEditorTracking":True}}
    flc.manager.update_definition(edit_dict)
    arcpy.AddMessage("########################## Publishing Complete ##########################")
    if in_report_name != "Script Information.csv":
        arcpy.AddMessage(f"Copy this itemId to set the itemId parameter for the next run.")
        arcpy.AddMessage("---------------------------------------------------")
        arcpy.AddMessage(f"----------{csv_lyr.itemid}---------")
        arcpy.AddMessage("---------------------------------------------------")

    # Delete the CSV file on AGO
    csv_item.delete()
    
    return csv_lyr.itemid


def updateCsvReport(gis, in_report, itemId):
    arcpy.AddMessage(f"Getting item: {itemId}...")
    fl = gis.content.get(itemId)
    if fl is None:
        arcpy.AddMessage ("Couldn't Find the Feature Layer with the provided ItemId.")
    else:
        table = fl.tables[0]
        # Delete All Records (Truncate)
        arcpy.AddMessage(f"Truncating item: {itemId}...")
        deletes = table.delete_features(where = "OBJECTID > 0")
        
        # Open the CSV report
        arcpy.AddMessage(f"Updating item: {itemId} with new report...")
        df = pd.read_csv(in_report)
        fs = df.spatial.to_featureset()
        table.edit_features(adds = fs)
        arcpy.AddMessage(f"Finished updating item: {itemId}.")

if __name__ == '__main__':
    main()