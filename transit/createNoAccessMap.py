#!/usr/bin/env python

""" create map of cube transit skims that don't have access"""

import gc,glob,os,re,sys,traceback
from dbfpy import dbf
from time import time,localtime,strftime,sleep
WRANGLER_DIR = os.path.realpath(os.path.join(os.path.split(__file__)[0], "..", "lib"))
sys.path.insert(0,WRANGLER_DIR )
from Wrangler import TransitNetwork, TransitLine
 
__author__ = "Lisa Zorn, San Francisco County Transportation Authority"
__license__= "GPL"
__email__  = "lisa@sfcta.org"
__date__   = "April 28, 2011" 

USAGE = r"""
usage: python createNoAccessMap.py mapsdir timeperiod

  e.g. python createAccessEgressMaps.py maps_OMP15 AM
  
  Creates noAccess_{timeperiod}_{Local,LRT,Premium,BART}.dbf in mapsdir containing nodenum, lines

"""

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print USAGE
        exit(1)
    
    if sys.argv[1]=="-?":
        print USAGE
        exit(1)
    
    mapDir    = sys.argv[1]
    timeperiod= sys.argv[2]
    
    originalNet = TransitNetwork("4.3", "original")
    originalNet.parseFile(r"..\transitOriginal%s.lin" % timeperiod)

    currentNet = TransitNetwork("4.3", "current")
    currentNet.parseFile("transit%s.lin" % timeperiod)

    for modetype in TransitLine.MODETYPE_TO_MODES.keys():
        if len(TransitLine.MODETYPE_TO_MODES[modetype]) == 0: continue
        
        noAccessNodes = {} # nodenum -> [[modes],[linenames]].  both are arrays of strings  

        for line in currentNet:
            
            if int(line["MODE"]) not in TransitLine.MODETYPE_TO_MODES[modetype]: continue
            
            originalLine = originalNet.line(line.name)
            
            for nodeIdx in range(len(line.n)):
                if not line.n[nodeIdx].isStop(): continue
                                
                # boards disallowed from crowding
                if line.n[nodeIdx].boardsDisallowed() and not originalLine.n[nodeIdx].boardsDisallowed():

                    nodenum = abs(int(line.n[nodeIdx].num))
                    
                    if nodenum not in noAccessNodes:
                        noAccessNodes[nodenum] = [[], []]
                    
                    noAccessNodes[nodenum][0].append(line["MODE"])
                    noAccessNodes[nodenum][1].append(line.name)

        print "No access nodes for modetype %s: %4d" % (modetype, len(noAccessNodes))
        if len(noAccessNodes) > 0:
            outdbf = dbf.Dbf(os.path.join(mapDir,"noAccess_%s_%s.dbf" % (timeperiod, modetype)), 
                             readOnly=False, new=True)
            outdbf.addField(("NoAccNode", "N", 6, 0),
                            ("Modes",   "C", 20),
                            ("Lines",   "C", 40))
            
            for nodenum in noAccessNodes.keys():
                rec = outdbf.newRecord()
                rec["NoAccNode"] = nodenum
                rec["MODES"]     = ",".join(noAccessNodes[nodenum][0])
                rec["Lines"]     = ",".join(noAccessNodes[nodenum][1])
                rec.store()
            outdbf.close()
                    