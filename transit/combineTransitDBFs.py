#!/usr/bin/env python

""" Combines DBFs from Cube TRNBUILD Output """

import getopt,logging,os,sys,traceback
WRANGLER_DIR = os.path.realpath(os.path.join(os.path.split(__file__)[0], "..", "lib"))
sys.path.insert(0, WRANGLER_DIR)
from Wrangler import TransitAssignmentData, TransitCapacity

__author__ = "Lisa Zorn, San Francisco County Transportation Authority"
__license__= "GPL"
__email__  = "lisa@sfcta.org"
__date__   = "2008-07-07"

USAGE            = """
Usage: 
  python combineTransitDBFs.py [-a] timeperiod input_dir [outputfile] champtype runType

  Opens local files SF[ABW,APW,WBA,WBW,WLW,WMW,WPA,WPW][timeperiod].dbf
     and outputs aggregate dbf file [outputfile]
  Uses local files transitLineToVehicle.csv and transitVehicleToCapacity.csv for capacity lookup.
     
  -a to add rows for "ALL" lines (e.g. aggregate for a given A,B)
  timeperiod can be AM,MD,PM,EV,EA, ALL or DAILY; 
                 If ALL then no outputfile need be specified they will be created in input_dir/transit_*.dbf
                 If DAILY then ALL will be created as described above, plus a DAILY version.
                     (DAILY NOT FUNCTIONAL YET!)
  champtype = "champ3" or "champ4"; default is champ4
  runType can be "muni" if we only care about muni, or 
                 "profile13735" to profile node 13735, or
                 "bigBA" for Muni, SamTrans, GGT, AC Transit, Caltrain, BART, Ferry,
                 "all" if we want to keep everything (including access/eggress)
                 
  Alack, alas, this now reads csv because of champ4.3 and I haven't backported to pre-4.3.  You can run
  dbf2csv to convert your transit assignment dbfs...  :(
"""

# REVISION HISTORY
# Revised 2009-12-17 to add loads
# Revised 2010-12-30 by ELO to:
#   (1) run more smoothly as an imported module (not from cmd args) 
#   (2) added a runAll function 
#   (3) had it pass the TAD the capacity info (previously it used a defunct default)
# Revised 2011-01-2011 by LMZ to:
#   Use CHAMP's TransitAssignmentData

class TransitDbfCombiner:
    
    def __init__(self, timeperiod,runDir,outFile,
                 champType='champ4',runType='',includeAll=False):
        """ 
        Interpret the args into my local variables.
        ALL CAPS class variables indicate arg-based constants.
        """
        self.timeperiod = timeperiod
        if self.timeperiod not in ["AM", "MD", "PM", "EV", "EA"]:
            print USAGE
            exit(1)
        if (self.timeperiod == "AM"):
            self.vtypeIdx = 2
        elif (self.timeperiod == "PM"):
            self.vtypeIdx = 3
        else:
            self.vtypeIdx = 4
            
        self.DIR        = runDir
        self.OUTFILE    = outFile
        self.runType    = runType
        self.includeAll=bool(includeAll)
        self.PROFILENODE= 0           
        
        if self.runType not in ["muni","bigBA","all"] and self.runType[0:7] != "profile":
            print "Don't understand runType %s" % self.runType
            print USAGE
            exit(1)
        if self.runType[0:7].lower() == "profile":
            self.PROFILENODE = int(self.runType[7:])
        self.CHAMPTYPE = champType
        if self.CHAMPTYPE not in ["champ3","champ4","champ3-sfonly"]:
            print "Don't understand CHAMPTYPE %s" % CHAMPTYPE
            print USAGE
            exit(1)
        
        logging.info("includeAll= " + str(self.includeAll))
        logging.info("timeperiod = " + self.timeperiod)
        logging.info("DIR        = " + self.DIR)
        logging.info("OUTFILE    = " + self.OUTFILE)
        logging.info("runType    = " + self.runType)
        logging.info("PROFILENODE= " + str(self.PROFILENODE))
        logging.info("CHAMPTYPE  = " + self.CHAMPTYPE)
        
    def readTransitNameMapping(self):
        if self.runType=="muni" or self.runType=="bigBA" or self.runType=="all":
            if self.runType == "muni": 
                system=["SF MUNI"]
                ignoreModes=[11,12,13,14,15,16,17]
            elif self.runType=="bigBA": 
                system = ["SF MUNI", "AC Transit", "SamTrans", "Caltrain", "BART", "Golden Gate Transit", "Ferry", "Presidigo"]
                ignoreModes=[11,12,13,14,15,16,17]
            else: # system == "all":
                system = []
                ignoreModes = []
            
            self.transitCapacity = TransitCapacity(self.DIR)
            self.tad = TransitAssignmentData(directory=self.DIR, 
                                             timeperiod=self.timeperiod,
                                             champtype=self.CHAMPTYPE,
                                             transitCapacity=self.transitCapacity,
                                             ignoreModes=ignoreModes,
                                             system=system)
        else:
            self.tad = TransitAssignmentData(directory=self.DIR, 
                                             timeperiod=self.timeperiod,
                                             champtype=self.CHAMPTYPE,
                                             transitCapacity=self.transitCapacity,
                                             profileNode=self.PROFILENODE)
        
        (aggdir, aggfile) = os.path.split(self.OUTFILE)
        aggfile = "agg_" + aggfile
        self.tad.writeDbfs(self.OUTFILE, os.path.join(aggdir,aggfile))
                
        # logging.debug(str(self.tad.linenameToAttributes))
        # logging.debug(str(self.tad.vehicleTypeToCapacity))

def runAll(runDir,champType='champ4',runType='bigBA',includeAll=False, includeDaily=False):
    
    print "Running all transit combiners"
    if 'transit' not in os.listdir(runDir):
        os.mkdir(os.path.join(runDir,"transit"))
    outDir = os.path.join(runDir,"transit")

    dailytdcs = {}
    for tp in ['AM','MD','PM','EV','EA']:
        print "Running ",tp
        outFile= os.path.join(outDir,'vehicles_'+tp+'.dbf')
        tdc = TransitDbfCombiner(timeperiod=tp, runDir=runDir, outFile=outFile,
                                 champType=champType, runType=runType, 
                                 includeAll=includeAll)
        tdc.readTransitNameMapping()
        
        if includeDaily:
            dailytdcs[tp] = tdc
    
    if not includeDaily: return
    
    # TODO make a daily!

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, 
                        format="%(asctime)s - %(levelname)s - %(message)s",
                        datefmt='%Y-%b-%d %H:%M:%S',)
    # python combineTransitDBFs.py [-a] timeperiod input_dir [outputfile] champtype runType

    opts, args = getopt.getopt(sys.argv[1:], "a")
    
    includeAll = False
    for o,a in opts:
        if o=="-a": includeAll = True
    
    if len(args) < 4: 
        print USAGE
        exit(1)
        
    if args[0] == "DAILY":
        print "DAILY not functional yet."
        exit(1)
        
    if args[0] == "ALL":
        runAll(runDir=args[1], champType=args[2], runType=args[3], includeAll=includeAll, 
               includeDaily=(args[0]=="DAILY"))

    else:
        tdc = TransitDbfCombiner(timeperiod=args[0], runDir=args[1], outFile=args[2],
                                 champType=args[3], runType=args[4], includeAll=includeAll)
        tdc.readTransitNameMapping()
    
    logging.info("DONE with the Whole thing!")

