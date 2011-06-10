#!/usr/bin/env python

""" create maps for cube transit skims """

import gc,glob,os,re,sys,traceback
from time import time,localtime,strftime,sleep
from dbfpy import dbf

WRANGLER_DIR = os.path.realpath(os.path.join(os.path.split(__file__)[0], "..", "lib"))
sys.path.insert(0,WRANGLER_DIR )

from Wrangler import TransitNetwork, TransitParser, Supplink

try:
    import arcgisscripting
except ImportError:
    import win32com.client
    class arcgisscripting(object):
        @staticmethod
        def create():
            return win32com.client.Dispatch('esriGeoprocessing.GpDispatch.1')
            
__author__ = "Lisa Zorn, San Francisco County Transportation Authority"
__license__= "GPL"
__email__  = "lisa@sfcta.org"
__date__   = "Jan 25, 2010"

USAGE = r"""
usage: python createAccessEgressMaps.py FREEFLOW_nodes.dbf mapsdir skimTargetOut.mdb

  e.g. python createAccessEgressMaps.py Y:\champ\networks\RTP2009_CHAMP4.3plus\2000\hwy\Shapefile\FREEFLOW_nodes.dbf maps
  
  Creates mapAccessEgress.mdb in mapsdir

"""

def createAccessAndEgressShapefiles(gp, mapDir, geodbFile, nodeToCoords, skimTargetFile):
    # skimTargetFile is something like maps\FORJOIN_TRNWLWAM_ORIG657.DBF
    # from makeMaps.s
    fileonly = skimTargetFile[len(mapDir)+1:-4]
    mode = fileonly[11:14]
    timeperiod = fileonly[14:16]
    if timeperiod == "VI":
        mode = fileonly[11:17]
        timeperiod = fileonly[17:19]
        type= fileonly[20:24]
        target = int(fileonly[24:])
    else:
        type = fileonly[17:21]
        target = int(fileonly[21:])
    
    tazkey = None
    if type=="ORIG":
        tazkey = "DEST"
    else:
        tazkey = "ORIG"
    
    # print mode, timeperiod, type, target
    # if mode != "APW" and mode != "WPA": continue
    
    skimTargetDbf = dbf.Dbf(skimTargetFile, readOnly=True, new=False)

    try:
        shpfile = "%s_%s_%s_%d_access" % (mode, timeperiod, type, target)
        # alas, this doesn't work
        #if os.path.exists(os.path.join(geodbFile, shpfile)):
        #    print "%s exists, skipping" % shpfile
        #    continue
        
        print shpfile            
        gp.CreateFeatureClass(geodbFile, shpfile,"Polyline")
        shpfile = os.path.join(geodbFile, shpfile)
        gp.AddField(shpfile,"TAZ",    "short","6")
        gp.AddField(shpfile,"AccNode","long", "10")
        gp.AddField(shpfile,"AccTime","float","6","2")
        
        for rec in skimTargetDbf:

            if rec["ACCNODE"]==0: continue

            cur         = gp.InsertCursor(shpfile) #input cursor
            lineArray   = gp.CreateObject("Array")

            pnt1    = gp.CreateObject("Point")
            pnt1.id = str("1")
            if type=="DEST":
                pnt1.x  = nodeToCoords[rec[tazkey]][0]
                pnt1.y  = nodeToCoords[rec[tazkey]][1]
            elif type=="ORIG":
                pnt1.x  = nodeToCoords[target][0]
                pnt1.y  = nodeToCoords[target][1]
            lineArray.add(pnt1)
            pnt2    = gp.CreateObject("Point")
            pnt2.id = str("2")
            pnt2.x  = nodeToCoords[rec["ACCNODE"]][0]
            pnt2.y  = nodeToCoords[rec["ACCNODE"]][1]
            lineArray.add(pnt2)
            
            feat            = cur.NewRow()
            feat.shape      = lineArray
            if type=="DEST":
                feat.TAZ    = str(rec[tazkey])
            else:
                feat.TAZ    = str(target)
            feat.AccNode    = str(rec["ACCNODE"])
            feat.AccTime    = str(rec["ACCT"])
            cur.InsertRow(feat)
            
        shpfile = "%s_%s_%s_%d_egress" % (mode, timeperiod, type, target)
        print shpfile
        gp.CreateFeatureClass(geodbFile, shpfile,"Polyline")
        shpfile = os.path.join(geodbFile, shpfile)
        gp.AddField(shpfile,"TAZ",    "short","6")
        gp.AddField(shpfile,"EgrNode","long","10")
        gp.AddField(shpfile,"EgrTime","float","6","2")
        
        for rec in skimTargetDbf:
            
            if rec["EGRNODE"]==0: continue

            cur         = gp.InsertCursor(shpfile) #input cursor
            lineArray   = gp.CreateObject("Array")

            pnt1    = gp.CreateObject("Point")
            pnt1.id = str("1")
            pnt1.x  = nodeToCoords[rec["EGRNODE"]][0]
            pnt1.y  = nodeToCoords[rec["EGRNODE"]][1]
            lineArray.add(pnt1)

            pnt2    = gp.CreateObject("Point")
            pnt2.id = str("2")
            if type=="DEST":
                pnt2.x  = nodeToCoords[target][0]
                pnt2.y  = nodeToCoords[target][1]
            elif type=="ORIG":
                pnt2.x  = nodeToCoords[rec[tazkey]][0]
                pnt2.y  = nodeToCoords[rec[tazkey]][1]
            lineArray.add(pnt2)
            
            feat            = cur.NewRow()
            feat.shape      = lineArray
            if type=="DEST":
                feat.TAZ    = str(target)
            elif type=="ORIG":
                feat.TAZ    = str(rec[tazkey])
            feat.EgrNode    = str(rec["EGRNODE"])
            feat.EgrTime    = str(rec["EGRT"])                
            cur.InsertRow(feat)
        
    except: 
        print "GIS error:", gp.GetMessages()
        traceback.print_exc()
        print "Ignoring..."
        print ""
        print ""         
    skimTargetDbf.close()
 
if __name__ == '__main__':
    if len(sys.argv) < 3:
        print USAGE
        exit(1)
    
    if sys.argv[1]=="-?":
        print USAGE
        exit(1)
    
    nodesFile = sys.argv[1]
    mapDir    = sys.argv[2]
    geodbFile = "mapAccessEgress.mdb"

    try: # Make the geodatabase to illustrate our trips
        gp = arcgisscripting.create()
        if not os.path.exists(os.path.join(mapDir,geodbFile)):
            gp.CreatePersonalGDB(mapDir, geodbFile)
        geodbFile = os.path.join(mapDir, geodbFile)
        
    except:
        print "Unexpected error:", sys.exc_info()[0]        
        traceback.print_exc()
        print "GIS error:", gp.GetMessages()

    # Read the file of coords
    nodeToCoords = {}
    nodesdbf    = dbf.Dbf(nodesFile, readOnly=True, new=False)
    print "Reading ",nodesFile
    for rec in nodesdbf:
        nodeToCoords[rec["N"]] = ( rec["X"], rec["Y"])
    nodesdbf.close()
    
    # for each dbf file make the access/egress links
    for skimTargetFile in sorted(glob.glob(mapDir + "/*.dbf")):
        createAccessAndEgressShapefiles(gp, mapDir, geodbFile, nodeToCoords, skimTargetFile)


