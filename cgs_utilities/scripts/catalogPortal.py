from arcgis.gis import GIS
import arcpy
from arcgis.mapping import WebMap
import csv
import time
from datetime import datetime
import requests
from urllib.parse import urlparse
import sys

portalURL = arcpy.GetParameterAsText(0)
adminUser = arcpy.GetParameterAsText(1)
adminPassword = arcpy.GetParameterAsText(2)
testServices = arcpy.GetParameter(3)
bBox = arcpy.GetParameterAsText(4)
outCSVFile = arcpy.GetParameterAsText(5)


usersToSkip = ['esri_nav', 'esri_livingatlas']
maxItems = 10000000
maxUsers = 10000000


def main():
    try:
        start = datetime.now()
        catalogPortal(portalURL, adminUser, adminPassword, bBox, outCSVFile, testServices)
        end = datetime.now()
        print (f"Completed in: {end - start}")
    except Exception as e:
        if type(e) is arcpy.ExecuteError:
            arcpy.AddMessage(arcpy.GetMessages(2))
        tb = sys.exc_info()[2]
        arcpy.AddMessage(f"ERROR @ Line {tb.tb_lineno} in file {__file__} with error: {sys.exc_info()[1]}")

def catalogPortal(portalURL, adminUser, adminPassword, bBox, outCSVFile, testServices):
    gis = GIS(portalURL, adminUser, adminPassword)
    isArcGISOnline = gis._is_agol
    token = gis._con.token
    #arcpy.AddMessage(token)


    ## MODIFY ?? how we obtain the server ## OR DO WE EVEN NEED?
    user_result = gis.users.search("", max_users=maxUsers)
    with open(outCSVFile, mode='w', newline='') as outCsv:
        writeCsv = csv.writer(outCsv)
        writeCsv.writerow(["Folder", "Type", "Hosted", "Title", "SizeBytes", "SizeMB", "Owner", "OwnerFolder", "SharedWithEveryone", "SharedWithOrganization", "SharedWithGroups", "NotShared", "ID", "Created", "Modified", "LayerTitle", "LayerType", "Status", "LayerURL", "TestURL", "MXD", "SupportsEditorTracking", "CreationDateField", "CreatorField", "EditDateField", "EditorField"])
        for user in user_result:
            if user.username in usersToSkip : continue
            allUserFolders = [None]
            userFolders = allUserFolders + user.folders
            for fld in userFolders:
                try: folderTitle = fld.get('title')
                except: folderTitle = None
                fldItems = user.items(folder=folderTitle, max_items=maxItems)
                for item in fldItems:
                    iType = item.type
                    iTitle = item.title
                    iOwner = item.owner
                    arcpy.AddMessage(f"Checking item {iTitle}; owned by {iOwner}")
                    iId = item.id
                    isHosted = ''
                    sizeBytes = item.size
                    sizeMB = (sizeBytes / 1024) / 1024
                    createTime = time.strftime('%Y-%m-%d', time.localtime(item.created/1000)) 
                    modifiedTime = time.strftime('%Y-%m-%d', time.localtime(item.modified/1000)) 
                    groupSharingList = []
                    for grp in item.shared_with['groups']:
                        groupSharingList += [grp['title']]
                    grpShareString = "','".join(groupSharingList)
                    notShared = not item.shared_with['everyone'] and not item.shared_with['org'] and grpShareString == ''
                    try: itemUrl = item.url
                    except: itemUrl = ""
                    itemStatus = ["Not Tested", "Not Tested"]
                    if not item.type == "Web Map":
                        try:
                            mxdPath = ""
                            if iType == "Map Service":
                                itemStatus = testMapService(itemUrl, token, isArcGISOnline, testServices, portalURL, bBox)
                                mxdPath = getMXDForService(itemUrl, "MapServer", token, isArcGISOnline)
                            if iType == "Feature Service":
                                itemStatus = testFeatureService(itemUrl, token, isArcGISOnline, testServices)
                                if '/rest/services/Hosted/' in item.url:
                                    isHosted = True
                                    print(f'Hosted {item.url}')
                                mxdPath = getMXDForService(itemUrl, "MapServer", token, isArcGISOnline)
                            writeCsv.writerow([folderTitle, iType, isHosted, iTitle, sizeBytes, sizeMB, iOwner, item.ownerFolder, item.shared_with['everyone'], item.shared_with['org'], grpShareString, notShared, iId, createTime, modifiedTime, "", "", itemStatus[0],itemUrl, itemStatus[1], mxdPath])
                            try:
                                #Write service layers to CSV
                                serviceLayers = item.layers
                                for layer in serviceLayers:
                                    if hasattr(layer.properties, "editFieldsInfo"):
                                        writeCsv.writerow([folderTitle, iType, isHosted, iTitle, sizeBytes, sizeMB, iOwner, item.ownerFolder, item.shared_with['everyone'], item.shared_with['org'], grpShareString, notShared, iId, createTime, modifiedTime, layer.properties.name, layer.properties.type, itemStatus[0],layer.url, itemStatus[1], mxdPath, "Yes", layer.properties.editFieldsInfo.creationDateField, layer.properties.editFieldsInfo.creatorField, layer.properties.editFieldsInfo.editDateField, layer.properties.editFieldsInfo.editorField])
                                    else: 
                                        writeCsv.writerow([folderTitle, iType, isHosted, iTitle, sizeBytes, sizeMB, iOwner, item.ownerFolder, item.shared_with['everyone'], item.shared_with['org'], grpShareString, notShared, iId, createTime, modifiedTime, layer.properties.name, layer.properties.type, itemStatus[0],layer.url, itemStatus[1], mxdPath, "No"])
                            except Exception as e:
                                print (e)
                                pass
                        except Exception as e:
                            print (item.title)
                            print (e)
                            pass
                    else: 
                        web_map_obj = WebMap(item)
                        for lyr in web_map_obj.layers:
                            try: lyrTitle = lyr.title
                            except: lyrTitle = ""
                            try: lyrType = lyr.layerType
                            except: lyrType = ""
                            try: lyrUrl = lyr.url
                            except: lyrUrl = ""
                            itemStatus = ["Not Tested", "Not Tested"]
                            if lyrType in ["ArcGISMapServiceLayer", "ArcGISTiledMapServiceLayer"]:
                                itemStatus = testMapService(lyrUrl, token, isArcGISOnline, testServices, portalURL, bBox)
                            if lyrType == "ArcGISFeatureLayer":
                                itemStatus = testFeatureService(lyrUrl, token, isArcGISOnline, testServices)
                            try:
                                writeCsv.writerow([folderTitle, iType, isHosted, iTitle, sizeBytes, sizeMB, iOwner, item.ownerFolder, item.shared_with['everyone'], item.shared_with['org'], grpShareString, notShared, iId, createTime, modifiedTime, lyrTitle, lyrType, itemStatus[0], lyrUrl, itemStatus[1]])
                                #print([folderTitle, iType, iTitle, iOwner, iId, createTime, modifiedTime, lyrTitle, lyrType, lyrUrl])
                            except Exception as e:
                                print (item.title)
                                print (e)
                                pass
                        for base_layer in web_map_obj.basemap['baseMapLayers']:
                            try: lyrTitle = base_layer['title']
                            except: lyrTitle = ""
                            try: lyrType = base_layer['layerType']
                            except: lyrType = ""
                            try: lyrUrl = base_layer['url']
                            except: lyrUrl = ""
                            itemStatus = ["Not Tested", "Not Tested"]
                            #if lyrType in ["ArcGISMapServiceLayer", "ArcGISTiledMapServiceLayer"]:
                            if iType == "Map Service":
                                itemStatus = testMapService(lyrUrl, token, isArcGISOnline, testServices, portalURL, bBox)
                            #if lyrType == "ArcGISFeatureLayer":
                            if iType == "Feature Service":
                                itemStatus = testFeatureService(lyrUrl, token, isArcGISOnline, testServices)
                            try:
                                writeCsv.writerow([folderTitle, iType, isHosted, iTitle, sizeBytes, sizeMB, iOwner, item.ownerFolder, item.shared_with['everyone'], item.shared_with['org'], grpShareString, notShared, iId, createTime, modifiedTime, lyrTitle, lyrType, itemStatus[0], lyrUrl, itemStatus[1]])
                                #print([folderTitle, iType, iTitle, iOwner, iId, createTime, modifiedTime, lyrTitle, lyrType, lyrUrl])
                            except Exception as e:
                                print (item.title)
                                print (e)
                                pass


def getMXDForService(serviceURL, serviceType, token, isArcGISOnline):
    servicePathParts = serviceURL[serviceURL.find('rest/services') + 14:].split("/")
    parsedURL = urlparse(serviceURL)
    host = parsedURL.netloc
    webAdaptorName = parsedURL.path.split('/')[1]
    if len(servicePathParts) == 3:
        manifestURL = addToken(f"https://{host}/{webAdaptorName}/admin/services/{servicePathParts[0]}/{servicePathParts[1]}.{serviceType}/iteminfo/manifest/manifest.json", token, isArcGISOnline)
    else:
        manifestURL = addToken(f"https://{host}/{webAdaptorName}/admin/services/{servicePathParts[0]}.{serviceType}/iteminfo/manifest/manifest.json", token, isArcGISOnline) 
    try:
        resquestResult = requests.get(manifestURL)
        jsonResult = resquestResult.json()
        return jsonResult["resources"][0]["onPremisePath"]
    except:
        return f'Unable to retrieve file.'
    

def addToken(testURL, token, isArcGISOnline):
    if isArcGISOnline:
        if urlparse(testURL)[1].split('.')[1] == 'arcgis':
            print (f"found arcgis: {testURL}")
            testURL = concatToken(testURL, token)
            if urlparse(testURL)[0] == 'http':
                testURL = 'https:' + testURL.split(':')[1]
        else:
            testURL = f'{testURL}' 
    else:
        testURL = concatToken(testURL, token) #f'{testURL}&token={token}'
    return testURL


def concatToken(inUrl, inToken):
    urlDelimiter = "&" if inUrl.find("?") > 0 else "?"
    return f'{inUrl}{urlDelimiter}token={inToken}'
     

def testMapService(itemUrl, token, isArcGISOnline, testServices, portalURL, bBox):
    if not testServices:
        return ["Not Tested", "Not Tested"]
    else:
        status = "Broken"
        testURL = ""
        try:
            testURL = f'{itemUrl}/export?bbox={bBox}&f=json'
            itemDomain = urlparse(itemUrl).netloc.upper()
            serverDomain = urlparse(portalURL).netloc.upper()
            if itemDomain == serverDomain or serverDomain == '': #It is the same server that we got the token from
                testURL = addToken(testURL, token, isArcGISOnline)
            r = requests.get(testURL)
            jsonResult = r.json()
            status = 'Broken' if 'error' in jsonResult else 'Working'
        except: pass
        #print(f'Status: {status} for {testURL}')
        return [status, testURL]


def testFeatureService(itemUrl, token, isArcGISOnline, testServices):
    if not testServices:
        return ["Not Tested", "Not Tested"]
    else:
        status = ""
        testURL = ""
        try:
            brokenLayers = 0
            testURL = addToken(f'{itemUrl}?f=json', token, isArcGISOnline)
            r = requests.get(testURL)
            jsonResult = r.json()
            if 'error' in jsonResult:
                status = 'Broken'
            else:
                #print(f'Testing {testURL}')
                brokenLayers = 0
                for l in jsonResult.layers:
                    r = requests.get(addToken(f'{itemUrl}/{l.id}/query?where="1=1"&f=json', token, isArcGISOnline))
                    brokenLayers = brokenLayers + 1 if 'error' in r.json() else brokenLayers
        except: pass
        if status != "Broken":
            if brokenLayers == 0:
                status = 'Working'
            else:
                status = f'{brokenLayers} broken layers'
        #print(f'Status: {status} for {testURL}')
        return [status, testURL]

if __name__ == "__main__":
    main()