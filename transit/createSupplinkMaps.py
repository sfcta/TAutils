#!/usr/bin/env python

""" Create a map of cube transit skims supp links """

import gc,glob,os,re,sys,traceback
from dbfpy import dbf
from time import time,localtime,strftime,sleep

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

def createSupplinkShapefile(gp, geodbFile, nodeToCoords, type, supplinks):
    """
    Just do AM for now
    """
    

    print "Processing %d supplinks" % len(supplinks)
    sys.stdout.flush()

    try:
        shpfile = "supplinks_%s" % type        
        gp.CreateFeatureClass(geodbFile, shpfile,"Polyline")
        print "Feature class created"
        sys.stdout.flush()
        shpfile = os.path.join(geodbFile, shpfile)
        gp.AddField(shpfile,"Mode",    "text","20")        
        gp.AddField(shpfile,"Anode",   "long","10")
        gp.AddField(shpfile,"Bnode",   "long","10")
        gp.AddField(shpfile,"Dist",    "float","4","2")
        gp.AddField(shpfile,"DistOrigi","float","4","2")
        gp.AddField(shpfile,"DistNetco","float","4","2")
        gp.AddField(shpfile,"DistCross","float","4","2")
        gp.AddField(shpfile,"DistVital","float","4","2")
        gp.AddField(shpfile,"DistSlope","float","4","2")
        gp.AddField(shpfile,"DistScale","float","4","3")

        count = 0

        for supplink in supplinks:

            cur         = gp.InsertCursor(shpfile) #input cursor
            lineArray   = gp.CreateObject("Array")

            pnt1    = gp.CreateObject("Point")
            pnt1.id = str("1")
            pnt1.x  = nodeToCoords[supplink.Anode][0]
            pnt1.y  = nodeToCoords[supplink.Anode][1]
            lineArray.add(pnt1)
            
            pnt2    = gp.CreateObject("Point")
            pnt2.id = str("2")
            pnt2.x  = nodeToCoords[supplink.Bnode][0]
            pnt2.y  = nodeToCoords[supplink.Bnode][1]
            lineArray.add(pnt2)
            
            feat            = cur.NewRow()
            feat.shape      = lineArray
            feat.Mode       = str(Supplink.MODES[supplink.mode])
            feat.Anode      = str(supplink.Anode)
            feat.Bnode      = str(supplink.Bnode)
            feat.Dist       = str(0.01*float(supplink["DIST"]) if "DIST" in supplink else 0)
            
            if supplink.comment and len(supplink.comment) > 1:
                commentdict = {}
                for item in supplink.comment[1:].split(','):
                    keyval = item.split(":") 
                    commentdict[keyval[0].strip()] = keyval[1]
                     
                feat.DistOrigi = str(0.01*float(commentdict["orig"    ]) if "orig"     in commentdict else 0)
                feat.DistNetco = str(0.01*float(commentdict["netconn" ]) if "netconn"  in commentdict else 0)
                feat.DistCross = str(0.01*float(commentdict["cross"   ]) if "cross"    in commentdict else 0)
                feat.DistVital = str(0.01*float(commentdict["vitality"]) if "vitality" in commentdict else 0)
                feat.DistSlope = str(0.01*float(commentdict["slope"   ]) if "slope"    in commentdict else 0)
                feat.DistScale = str(1.00*float(commentdict["scale"   ]) if "scale"    in commentdict else 0)

            cur.InsertRow(feat)
            count +=1
            
            if count % 5000 == 0:
                print "Added %d polylines: %5d-%5d" % (count, supplink.Anode, supplink.Bnode)
                sys.stdout.flush()           
    except:
        traceback.print_exc()
        
        print "GIS error:", gp.GetMessages()
        print "Ignoring..."
        print ""
        print ""
    
if __name__ == '__main__':
    if len(sys.argv) < 3:
        print USAGE
        exit(1)
    
    if sys.argv[1]=="-?":
        print USAGE
        exit(1)
    
    nodesFile = sys.argv[1]
    mapDir    = sys.argv[2]
    geodbFile = "supplinks.mdb"
    try: # Make the geodatabase to illustrate our trips
        gp = arcgisscripting.create()        
        if not os.path.exists(os.path.join(mapDir,geodbFile)):
            gp.CreatePersonalGDB(mapDir, geodbFile)
        geodbFile = os.path.join(mapDir, geodbFile)
    except:
        print "Unexpected error:", sys.exc_info()[0]        
        traceback.print_exc()

    # Read the file of coords
    nodeToCoords = {}
    nodesdbf    = dbf.Dbf(nodesFile, readOnly=True, new=False)
    print "Reading ",nodesFile
    for rec in nodesdbf:
        nodeToCoords[rec["N"]] = ( rec["X"], rec["Y"])
    nodesdbf.close()
    
    # Read and visualize supplinks
    supplinksFile = "AM_Transit_walk_drive_supplinks.dat"
    print "Reading %s" % supplinksFile
    
    supplinks = None
    try:
        parser = TransitParser(verbosity=0)
        f = open(supplinksFile, 'r')
        success, children, nextcharacter = parser.parse(f.read(), production="transit_file")
        f.close()
    
        supplinks = parser.convertSupplinksData()
        del parser
        
        for x in supplinks: x.setMode()
    except:
        traceback.print_exc()
        raise
    
    # only process the given type for now -- too many otherwise
    accessSupplinks = [x for x in supplinks if Supplink.MODES[x.mode]=="WALK_ACCESS"]
    egressSupplinks = [x for x in supplinks if Supplink.MODES[x.mode]=="WALK_EGRESS"]
    
    del supplinks 
    gc.collect()
    
    # look I don't know if gc.collect or sleep or what is required but I was having trouble
    # getting CreateFeatureClass to not mysteriously fail
    print "Supplinks read"
    sys.stdout.flush()
    sleep(5)
    
    
    createSupplinkShapefile(gp, geodbFile, nodeToCoords, "WALK_ACCESS", accessSupplinks)
    createSupplinkShapefile(gp, geodbFile, nodeToCoords, "WALK_EGRESS", egressSupplinks)

