#!/usr/bin/env python

'''Generic trip record class, plus some extra functions that will likely come up.
'''

import os
import random
import re
import sys
from time import time,localtime,strftime
import numpy
from dbfpy import dbf
from tables import IsDescription,Int32Col,Float32Col,openFile,Float32Atom,Filters

__author__ = "Lisa Zorn, San Francisco County Transportation Authority"
__license__= "GPL"
__email__  = "lisa@sfcta.org"
__date__   = "Jan 25, 2010"

__all__ = [ 'readDistrictsEqv', 'createExpressionForValue', 'Trip', 'SkimUtil', 'TIMEPERIODS' ]

recordKeys = list()  # Callers can access these by importing these variables

# Functionally constants
TIMEPERIODS     = { 1:"EA", 2:"AM", 3:"MD", 4:"PM", 5:"EV" }
OPCOST          = 0.12 # dollars/mile
WALKSPEED       = 3.0  # mph
BIKESPEED       = 10.0 # mph

PSEG            = { 1:"Worker", 2:"AdultStudent", 3:"Other", 4:"ChildStudent"}
PURPOSE         = { 1:"Work",    2:"GradeSchool", 3:"HighSchool",
                    4:"College", 5:"Other",       6:"WorkBased" }
TOURMODE        = { 1:"DA", 2:"SR2", 3:"SR3", 4:"TollDA", 5:"TollSR2", 6:"TollSR3",
                    7:"Walk", 8:"Bike", 9:"WalkToTransit", 10:"DriveToTransit" }
TRIPMODE        = { 1:"DA", 2:"SR2", 3:"SR3", 4:"TollDA", 5:"TollSR2", 6:"TollSR3",
                    7:"PaidDA", 8:"PaidSR2", 9:"PaidSR3", 10:"Walk", 11:"Bike",
                    12:"WalkToLocal", 13:"WalkToMUNI", 14:"WalkToPremium",
                    15:"WalkToBART", 16:"DriveToPremium", 17:"DriveToBART" }                
                
# key = trip mode, segdir
TRIPTRNSKIMMAP  = { (12,1):"WLW", (12,2):"WLW", (13,1):"WMW", (13,2):"WMW",
                    (14,1):"WPW", (14,2):"WPW", (15,1):"WBW", (15,2):"WBW",
                    (16,1):"APW", (16,2):"WPA", (17,1):"ABW", (17,2):"WBA" }
TOURTRNSKIMMAP = { (9,1):"WTW",  (9,2) :"WTW",
                   (10,1):"ATW", (10,2):"WTA" }

TOURSKIMS = ["ATW", "WTA", "WTW" ]
TRIPSKIMS = ["ABW", "APW", "WBA", "WPA", "WBW", "WPW", "WMW", "WLW" ]

NUMTTSKIMS      = { "ABW":8, "WBA":8, "WBW":8, "APW":7, "WPA":7, "WPW":7,
                    "WLW":5, "WMW":6 }
TRNSKIMKEY      = { "ABW":{"IVT_LOC":1, "IVT_MUN":2, "IVT_PRE":3, "IVT_BAR":4, "TIM_DAC":5,
                           "TIM_WEG":6, "TIM_IWT":7, "TIM_XWT":8, "DIS_TRN":9, "FAR_TOT":10,
                           "BOR_TOT":11,"DIS_DRV":12,"TIM_AUX":13},
                    "APW":{"IVT_LOC":1, "IVT_MUN":2, "IVT_PRE":3, "TIM_DAC":4, "TIM_WEG":5,
                           "TIM_IWT":6, "TIM_XWT":7, "DIS_TRN":8, "FAR_TOT":9, "BOR_TOT":10,
                           "DIS_DRV":11,"TIM_AUX":12},
                    "WBA":{"IVT_LOC":1, "IVT_MUN":2, "IVT_PRE":3, "IVT_BAR":4, "TIM_WAC":5,
                           "TIM_DEG":6, "TIM_IWT":7, "TIM_XWT":8, "DIS_TRN":9, "FAR_TOT":10,
                           "BOR_TOT":11,"DIS_DRV":12,"TIM_AUX":13},
                    "WPA":{"IVT_LOC":1, "IVT_MUN":2, "IVT_PRE":3, "TIM_WAC":4, "TIM_DEG":5,
                           "TIM_IWT":6, "TIM_XWT":7, "DIS_TRN":8, "FAR_TOT":9, "BOR_TOT":10,
                           "DIS_DRV":11,"TIM_AUX":12},
                    "WBW":{"IVT_LOC":1, "IVT_MUN":2, "IVT_PRE":3, "IVT_BAR":4, "TIM_WAC":5,
                           "TIM_WEG":6, "TIM_IWT":7, "TIM_XWT":8, "DIS_TRN":9, "FAR_TOT":10,
                           "BOR_TOT":11,"TIM_AUX":12},
                    "WPW":{"IVT_LOC":1, "IVT_MUN":2, "IVT_PRE":3, "TIM_WAC":4, "TIM_WEG":5,
                           "TIM_IWT":6, "TIM_XWT":7, "DIS_TRN":8, "FAR_TOT":9, "BOR_TOT":10,
                           "TIM_AUX":11},
                    "WMW":{"IVT_LOC":1, "IVT_MUN":2, "TIM_WAC":3, "TIM_WEG":4, "TIM_IWT":5,
                           "TIM_XWT":6, "DIS_TRN":7, "FAR_TOT":8, "BOR_TOT":9, "TIM_AUX":10},
                    "WLW":{"IVT_LOC":1, "TIM_WAC":2, "TIM_WEG":3, "TIM_IWT":4, "TIM_XWT":5,
                           "DIS_TRN":6, "FAR_TOT":7, "BOR_TOT":8, "TIM_AUX":9},
                    # Tour Skims
                    "ATW":{"IVT_LOC":1, "IVT_MUN":2, "IVT_PRE":3, "IVT_BAR":4, "TIM_DAC":5,
                           "TIM_WEG":6, "TIM_IWT":7, "TIM_XWT":8, "DIS_TRN":9, "FAR_TOT":10,
                           "BOR_TOT":11,"DIS_DRV":12,"TIM_AUX":13},
                    "WTA":{"IVT_LOC":1, "IVT_MUN":2, "IVT_PRE":3, "IVT_BAR":4, "TIM_WAC":5,
                           "TIM_DEG":6, "TIM_IWT":7, "TIM_XWT":8, "DIS_TRN":9, "FAR_TOT":10,
                           "BOR_TOT":11,"DIS_DRV":12,"TIM_AUX":13},
                    "WTW":{"IVT_LOC":1, "IVT_MUN":2, "IVT_PRE":3, "IVT_BAR":4, "TIM_WAC":5,
                           "TIM_WEG":6, "TIM_IWT":7, "TIM_XWT":8, "DIS_TRN":9, "FAR_TOT":10,
                           "BOR_TOT":11,"DIS_DRV":12,"TIM_AUX":13},
                }
TRN_TIMES = set(["IVT_LOC","IVT_MUN","IVT_PRE","IVT_BAR","TIM_DAC","TIM_WAC","TIM_DEG","TIM_WEG","TIM_IWT","TIM_XWT","TIM_AUX"])
TRN_DISTS = set(["DIS_TRN","DIS_DRV"])
TRN_COSTS = set(["FAR_TOT"])

# from sftripmc/persdata.cpp
#                   //----------+-------------------------------------------------
#                   //          |                     TDDEPART
#                   // TODEPART |        1         2         3         4         5
#                   //----------+-------------------------------------------------
DURATION_TRIP = [
                                [      0.3,       1.2,     8.4,      10.5,    14.1],
                                [      1.2,       0.3,     4.8,       8.9,    11.5],
                                [      8.4,       4.8,     0.8,       2.7,     7.7],
                                [     10.5,       8.9,     2.7,       0.4,     2.0],
                                [     14.1,      11.5,     7.7,       2.0,     1.1] ]

# from sfourmc/persdata.cpp
DURATION_TOUR = [
                                [      0.3,       1.5,     8.2,      10.2,    13.1],
                                [      1.5,       0.4,     5.1,       8.7,    10.9],
                                [      8.2,       5.1,     1.0,       3.1,     7.6],
                                [     10.2,       8.7,     3.1,       0.5,     2.1],
                                [      2.4,       6.8,     9.4,      13.8,     1.4] ]

eqvline_re      = re.compile("^DIST (\d+)=(\d+)\s*((.+)\s*)?$")

def readDistrictsEqv(eqvfile):
    """
    Reads eqv file, returns dictionary of { taz -> district num }, 
    dictionary of { district num -> [ list of TAZs ] },
    and dictionary of { district num -> district name }
    """
    tazToDist   = {}
    distToTaz   = {}
    distToName  = {}
    infile      = open(eqvfile, 'rU') # The U is for universal newline support
    for line in infile:
        m = eqvline_re.match(line)
        if (m == None):
            sys.stderr.write("Didn't understand line [" + line + "] in " + eqvfile)
        tazToDist[int(m.group(2))] = int(m.group(1))
        if not distToTaz.has_key(int(m.group(1))):
            distToTaz[int(m.group(1))] = []
        distToTaz[int(m.group(1))].append(int(m.group(2)))
        if (m.group(4) != None):
            # print "[%s]" % (m.group(4))
            distToName[int(m.group(1))] = m.group(4)
    infile.close()
    return (tazToDist, distToTaz, distToName)

def createExpressionForValue(tazmapping, var, value):
    """
    Creates an expression for a var (e.g. workstaz) and a mapping value (e.g. Cupertino).
    tazmapping should be a dictionary mapping tazes to names (including the given value)
    """
    retstr = '('
    tazes = tazmapping.keys()
    gtlt  = 0
    for i in range(len(tazes)):
        taz = tazes[i]
        v = tazmapping[taz]
        if (v == value):
            
            # within a gtlt clause
            if gtlt:
                # end it?
                if i==len(tazes)-1 or tazmapping[tazes[i+1]]!=value:
                    retstr += ' & '
                    retstr += '(' + var + ' <= ' + str(taz) + '))'
                    gtlt = 0
            # start one?
            elif (i < len(tazes)-2 and tazmapping[tazes[i+1]]==value and tazmapping[tazes[i+2]]==value):
                if (len(retstr)>1): retstr += ' | '
                retstr += '((' + var + ' >= ' + str(taz) + ')'
                gtlt = 1
            else:
                if (len(retstr)>1): retstr += ' | '
                retstr += '(' + var + ' == ' + str(taz) + ')'
    retstr += ')'
    return retstr


class Trip(IsDescription):
    """
    Class to represent the disaggregate trip data from SF-CHAMP.
    May also be modified to represent other disaggregate data.
    For use with pytables.  See TourDiary.cpp for more.
    
    All this stuff happens once, I think when the file is imported.
    """
    
    # Each item is a record
    global recordKeys
    recordKeys.append("hhid");          hhid        = Int32Col(pos=len(recordKeys))
    recordKeys.append("persid");        persid      = Int32Col(pos=len(recordKeys))
    recordKeys.append("homestaz");      homestaz    = Int32Col(pos=len(recordKeys))
    recordKeys.append("hhsize");        hhsize      = Int32Col(pos=len(recordKeys))
    recordKeys.append("hhadlt");        hhadlt      = Int32Col(pos=len(recordKeys))
    recordKeys.append("nage65up");      nage65up    = Int32Col(pos=len(recordKeys))
    recordKeys.append("nage5064");      nage5064    = Int32Col(pos=len(recordKeys))
    recordKeys.append("nage3549");      nage3549    = Int32Col(pos=len(recordKeys))
    recordKeys.append("nage2534");      nage2534    = Int32Col(pos=len(recordKeys))
    recordKeys.append("nage1824");      nage1824    = Int32Col(pos=len(recordKeys))
    recordKeys.append("nage1217");      nage1217    = Int32Col(pos=len(recordKeys))
    recordKeys.append("nage511");       nage511     = Int32Col(pos=len(recordKeys))
    recordKeys.append("nageund5");      nageund5    = Int32Col(pos=len(recordKeys))
    recordKeys.append("nfulltim");      nfulltim    = Int32Col(pos=len(recordKeys))
    recordKeys.append("nparttim");      nparttim    = Int32Col(pos=len(recordKeys))
    recordKeys.append("autos");         autos       = Int32Col(pos=len(recordKeys))
    recordKeys.append("hhinc");         hhinc       = Float32Col(pos=len(recordKeys))
    recordKeys.append("gender");        gender      = Int32Col(pos=len(recordKeys))
    recordKeys.append("age");           age         = Int32Col(pos=len(recordKeys))
    recordKeys.append("relat");         relat       = Int32Col(pos=len(recordKeys))
    recordKeys.append("race");          race        = Int32Col(pos=len(recordKeys))
    recordKeys.append("employ");        employ      = Int32Col(pos=len(recordKeys))
    recordKeys.append("educn");         educn       = Int32Col(pos=len(recordKeys)) # 23

    recordKeys.append("worksTwoJobs");  worksTwoJobs= Int32Col(pos=len(recordKeys))
    recordKeys.append("worksOutOfArea");worksOutOfArea    = Int32Col(pos=len(recordKeys))
    recordKeys.append("mVOT");          mVOT        = Float32Col(pos=len(recordKeys))
    recordKeys.append("oVOT");          oVOT        = Float32Col(pos=len(recordKeys))
    recordKeys.append("randseed");      randseed    = Int32Col(pos=len(recordKeys))
    recordKeys.append("workstaz");      workstaz    = Int32Col(pos=len(recordKeys))
    recordKeys.append("paysToPark");    paysToPark  = Int32Col(pos=len(recordKeys)) # 30

    # MC Logsums
    recordKeys.append("mcLogSumW0");    mcLogSumW0  = Float32Col(pos=len(recordKeys))
    recordKeys.append("mcLogSumW1");    mcLogSumW1  = Float32Col(pos=len(recordKeys))
    recordKeys.append("mcLogSumW2");    mcLogSumW2  = Float32Col(pos=len(recordKeys))
    recordKeys.append("mcLogSumW3");    mcLogSumW3  = Float32Col(pos=len(recordKeys)) # 34

    # DC Logsum outputs
    recordKeys.append("mcLogSumW");     mcLogSumW   = Float32Col(pos=len(recordKeys))
    recordKeys.append("dcLogSumPk");    dcLogSumPk  = Float32Col(pos=len(recordKeys))
    recordKeys.append("dcLogSumOp");    dcLogSumOp  = Float32Col(pos=len(recordKeys))
    recordKeys.append("dcLogSumAtWk");  dcLogSumAtWk= Float32Col(pos=len(recordKeys)) # 38
   
    # Day Pattern outputs
    recordKeys.append("pseg");          pseg        = Int32Col(pos=len(recordKeys))
    recordKeys.append("tour");          tour        = Int32Col(pos=len(recordKeys))
    recordKeys.append("daypattern");    daypattern  = Int32Col(pos=len(recordKeys))
    recordKeys.append("purpose");       purpose     = Int32Col(pos=len(recordKeys))
    recordKeys.append("ctprim");        ctprim      = Int32Col(pos=len(recordKeys))
    recordKeys.append("cttype");        cttype      = Int32Col(pos=len(recordKeys))
    recordKeys.append("tnstopsb");      tnstopsb    = Int32Col(pos=len(recordKeys))
    recordKeys.append("tnstopsa");      tnstopsa    = Int32Col(pos=len(recordKeys)) # 46

    # These are out of order with TourDiary.cpp
    recordKeys.append("alreadyPaid");   alreadyPaid = Int32Col(pos=len(recordKeys))
    recordKeys.append("priority");      priority    = Int32Col(pos=len(recordKeys))
    recordKeys.append("primdest");      primdest    = Int32Col(pos=len(recordKeys))

    recordKeys.append("todepart");      todepart    = Int32Col(pos=len(recordKeys))
    recordKeys.append("tddepart");      tddepart    = Int32Col(pos=len(recordKeys)) # 51
 
    # for MC
    recordKeys.append("stopBefTime1");  stopBefTime1= Int32Col(pos=len(recordKeys))
    recordKeys.append("stopBefTime2");  stopBefTime2= Int32Col(pos=len(recordKeys))
    recordKeys.append("stopBefTime3");  stopBefTime3= Int32Col(pos=len(recordKeys))
    recordKeys.append("stopBefTime4");  stopBefTime4= Int32Col(pos=len(recordKeys))
    recordKeys.append("stopAftTime1");  stopAftTime1= Int32Col(pos=len(recordKeys))
    recordKeys.append("stopAftTime2");  stopAftTime2= Int32Col(pos=len(recordKeys))
    recordKeys.append("stopAftTime3");  stopAftTime3= Int32Col(pos=len(recordKeys))
    recordKeys.append("stopAftTime4");  stopAftTime4= Int32Col(pos=len(recordKeys)) # 59

    recordKeys.append("tourmode");              tourmode             = Int32Col(pos=len(recordKeys))
    recordKeys.append("autoExpUtility");        autoExpUtility       = Float32Col(pos=len(recordKeys))
    recordKeys.append("walkTransitAvailable");  walkTransitAvailable = Int32Col(pos=len(recordKeys))
    recordKeys.append("walkTransitProb");       walkTransitProb      = Float32Col(pos=len(recordKeys))
    recordKeys.append("driveTransitOnly");      driveTransitOnly     = Int32Col(pos=len(recordKeys))
    recordKeys.append("driveTransitOnlyProb");  driveTransitOnlyProb = Float32Col(pos=len(recordKeys)) # 65
    
    # for ISTOP
    recordKeys.append("stopb1");        stopb1      = Int32Col(pos=len(recordKeys))
    recordKeys.append("stopb2");        stopb2      = Int32Col(pos=len(recordKeys))
    recordKeys.append("stopb3");        stopb3      = Int32Col(pos=len(recordKeys))
    recordKeys.append("stopb4");        stopb4      = Int32Col(pos=len(recordKeys))
    recordKeys.append("stopa1");        stopa1      = Int32Col(pos=len(recordKeys))
    recordKeys.append("stopa2");        stopa2      = Int32Col(pos=len(recordKeys))
    recordKeys.append("stopa3");        stopa3      = Int32Col(pos=len(recordKeys))
    recordKeys.append("stopa4");        stopa4      = Int32Col(pos=len(recordKeys))

    # Trip Mode Choice
    recordKeys.append("mcurrseg");      mcurrseg    = Int32Col(pos=len(recordKeys))
    recordKeys.append("mOtaz");         mOtaz       = Int32Col(pos=len(recordKeys))
    recordKeys.append("mDtaz");         mDtaz       = Int32Col(pos=len(recordKeys))
    recordKeys.append("mOdt");          mOdt        = Int32Col(pos=len(recordKeys))
    recordKeys.append("mChosenmode");   mChosenmode = Int32Col(pos=len(recordKeys))
    recordKeys.append("mNonMot");       mNonMot     = Int32Col(pos=len(recordKeys))
    recordKeys.append("mExpAuto");      mExpAuto    = Float32Col(pos=len(recordKeys))
    recordKeys.append("mWlkAvail");     mWlkAvail   = Int32Col(pos=len(recordKeys))
    recordKeys.append("mWlkTrnProb");   mWlkTrnProb = Float32Col(pos=len(recordKeys))
    recordKeys.append("mDriveOnly");    mDriveOnly  = Int32Col(pos=len(recordKeys))
    recordKeys.append("mDriveTrnProb"); mDriveTrnProb=Float32Col(pos=len(recordKeys))
    recordKeys.append("mSegDir");       mSegDir     = Int32Col(pos=len(recordKeys))

    recordKeys.append("prefTripTod");   prefTripTod = Int32Col(pos=len(recordKeys))
    recordKeys.append("tripTod");       tripTod     = Int32Col(pos=len(recordKeys))
    

class SkimUtil:
    """
    Helper class to read Skim files and lookup time/cost/distance for given O-D pairs.
    This class is written for low-memory, not for speed.  So it'll take forever to go
    through a trip file and do the skim lookups but you won't be hitting memory limits.
    """
    
    def __init__(self, skimdir, useTempTrn = True,
                 timeperiods=TIMEPERIODS.keys(), trnskims=TRIPSKIMS, skimtype="trip", skimprefix=""):
        '''
        Opens all the skim files for use.  skimtype="trip" or "tour".
        If makeTemp is specified, then makes temporary transit versions with just time/cost/distance. 
        timeperiods can be specified to limit the time periods loaded (an array of numbers).
        trnskims likewise.
        Note: tazdata.dbf is also read from the skimdir.
        '''
        self.skimtype = skimtype
        if useTempTrn:
            self.useTempTrn = True
            if skimtype=="trip":
                self.tempTrnFile = os.path.join(skimdir, "TRN_temp.h5")
            else:
                self.tempTrnFile = os.path.join(skimdir, "TRN_tourtemp.h5")

            self.trnDist = { 1:{}, 2:{}, 3:{}, 4:{}, 5:{} }
            self.trnTime = { 1:{}, 2:{}, 3:{}, 4:{}, 5:{} }
            self.trnFare = { 1:{}, 2:{}, 3:{}, 4:{}, 5:{} } # fare
            self.trnDrvDist = { 1:{}, 2:{}, 3:{}, 4:{}, 5:{} } # opcost
            self.filters = Filters(complevel=5, complib='zlib')
            self.shape = (2475, 2475) # todo: base this on the skim file
            self.atom = Float32Atom()
            self.tempTrnFileExists = False
            if os.path.exists(self.tempTrnFile):
                print "Using existing temp transit skim %s" % (self.tempTrnFile)
                self.tempTrnFileExists = True
                self.trnTemp = openFile(self.tempTrnFile, 'r')
            else:
                self.trnTemp = openFile(self.tempTrnFile, 'w')
        else:
            self.trnTemp = False
            
        self.skimdir         = skimdir
        self.trnskims        = { 1:{}, 2:{}, 3:{}, 4:{}, 5:{} }
        self.hwyskims        = { 1:{}, 2:{}, 3:{}, 4:{}, 5:{} }
        for tkey in timeperiods:
            for sval in trnskims:
                if sval not in self.trnskims[tkey]:
                    if useTempTrn and self.tempTrnFileExists:
                        self.readTempSkims(tkey,TIMEPERIODS[tkey],sval)
                    else:
                        # open skims
                        self.trnskims[tkey][sval] = openFile(os.path.join(skimdir,skimprefix+"TRN" + sval + TIMEPERIODS[tkey] + ".h5"),mode="r")
                    
                        if useTempTrn:
                            self.makeTempSkims(tkey,TIMEPERIODS[tkey],sval)
                            # we're done with the big-skim - close it
                            self.trnskims[tkey][sval].close()
                            del self.trnskims[tkey][sval]
        
            self.hwyskims[tkey] = openFile(os.path.join(skimdir,skimprefix+"HWYALL" + TIMEPERIODS[tkey] + ".h5"), mode="r")

        # print trnskims[3]["APW"].root._f_getChild("1")[0,:]
        self.nonmotskims     = openFile(os.path.join(skimdir,"NONMOT.h5"), mode="r")
        self.termtime        = openFile(os.path.join(skimdir,"OPTERM.h5"), mode="r")
        
        # read tazdata for parking costs
        tazdatadbf    = dbf.Dbf(os.path.join(skimdir,"tazdata.dbf"), readOnly=True, new=False)
        self.prkcstwh  = {}
        self.prkcstoh  = {}
        self.ppaying   = {}
        print "Reading tazdata.dbf"
        for rec in tazdatadbf:
            self.prkcstwh[rec["SFTAZ"]] = rec["PRKCSTWH"]
            self.prkcstoh[rec["SFTAZ"]] = rec["PRKCSTOH"]
            self.ppaying[rec["SFTAZ"]]  = rec["PPAYING"]
        tazdatadbf.close()
        
        if useTempTrn and not self.tempTrnFileExists: self.trnTemp.flush()

        print "SkimUtil initialized for %s" % (skimdir)
    
    def __del__(self):
        """
        Close the skim files we opened
        """
        if self.trnTemp:
            self.trnTemp.close()
        else:
           for tkey in self.trnskims.iterkeys():
                for skey in self.trnskims[tkey].iterkeys():
                    self.trnskims[tkey][skey].close()
                self.trnskims[tkey].clear()

        for key in self.hwyskims.keys():
            self.hwyskims[key].close()
        
        self.nonmotskims.close()
        self.termtime.close()

                
    def readTempSkims(self, tkey, tval, sval):
        ''' tkey is for timeperiod, one of 1,2,3,4,5
            sval is for the submode, one of ABW, WPA, etc
        '''
        self.trnDist[tkey][sval] = self.trnTemp.root._f_getChild(sval + tval + "_dist")
        self.trnTime[tkey][sval] = self.trnTemp.root._f_getChild(sval + tval + "_time")
        self.trnFare[tkey][sval] = self.trnTemp.root._f_getChild(sval + tval + "_fare")
        self.trnDrvDist[tkey][sval] = self.trnTemp.root._f_getChild(sval + tval + "_drvdist")
        
    def makeTempSkims(self, tkey, tval, sval):
        ''' tkey is for timeperiod, one of 1,2,3,4,5
            sval is for the submode, one of ABW, WPA, etc
        '''
        print strftime("%x %X", localtime()) + ": Making temp skim for %s %s" % (tval, sval)
        self.trnDist[tkey][sval] = self.trnTemp.createCArray(self.trnTemp.root, sval + tval + "_dist", self.atom, self.shape, filters=self.filters)
        self.trnTime[tkey][sval] = self.trnTemp.createCArray(self.trnTemp.root, sval + tval + "_time", self.atom, self.shape, filters=self.filters)
        self.trnFare[tkey][sval] = self.trnTemp.createCArray(self.trnTemp.root, sval + tval + "_fare", self.atom, self.shape, filters=self.filters)
        self.trnDrvDist[tkey][sval] = self.trnTemp.createCArray(self.trnTemp.root, sval + tval + "_drvdist", self.atom, self.shape, filters=self.filters)
        
        # zero it out
        self.trnDist[tkey][sval][0:self.shape[0], 0:self.shape[1]] = numpy.zeros((self.shape[0],self.shape[1]))
        self.trnTime[tkey][sval][0:self.shape[0], 0:self.shape[1]] = numpy.zeros((self.shape[0],self.shape[1]))
        self.trnFare[tkey][sval][0:self.shape[0], 0:self.shape[1]] = numpy.zeros((self.shape[0],self.shape[1]))
        self.trnDrvDist[tkey][sval][0:self.shape[0], 0:self.shape[1]] = numpy.zeros((self.shape[0],self.shape[1]))

        # go through each of the matrices
        for matname,matnum in TRNSKIMKEY[sval].iteritems():
            print strftime("%x %X", localtime()) + ":   %s" % (matname)

            if matname in TRN_TIMES:
                self.trnTime[tkey][sval][0:self.shape[0],0:self.shape[1]] = \
                    self.trnTime[tkey][sval][0:self.shape[0], 0:self.shape[1]] + \
                    self.trnskims[tkey][sval].root._f_getChild(str(matnum))[0:self.shape[0], 0:self.shape[1]]
            elif matname in TRN_DISTS:
                self.trnDist[tkey][sval][0:self.shape[0],0:self.shape[1]] = \
                    self.trnDist[tkey][sval][0:self.shape[0], 0:self.shape[1]] + \
                    self.trnskims[tkey][sval].root._f_getChild(str(matnum))[0:self.shape[0], 0:self.shape[1]]
            elif matname in TRN_COSTS:
                self.trnFare[tkey][sval][0:self.shape[0],0:self.shape[1]] = \
                    self.trnFare[tkey][sval][0:self.shape[0], 0:self.shape[1]] + \
                    self.trnskims[tkey][sval].root._f_getChild(str(matnum))[0:self.shape[0], 0:self.shape[1]]
            else:
                print "Ignoring %s" % (matname)

        # operating cost from auto
        if "DIS_DRV" in TRNSKIMKEY[sval]:
            matnum = TRNSKIMKEY[sval]["DIS_DRV"]
            self.trnDrvDist[tkey][sval][0:self.shape[0],0:self.shape[1]] = \
                self.trnDrvDist[tkey][sval][0:self.shape[0], 0:self.shape[1]] + \
                self.trnskims[tkey][sval].root._f_getChild(str(matnum))[0:self.shape[0], 0:self.shape[1]]

        # walk egress and access times aren't included in the distance
        if "TIM_WAC" in TRNSKIMKEY[sval]:
            matnum = TRNSKIMKEY[sval]["TIM_WAC"]
            print "TIM_WAC before: tkey=%d tval=%s sval=%s trnDIST[1255,22] = %d" % (tkey, tval, sval, self.trnDist[tkey][sval][1254,21])
            self.trnDist[tkey][sval][0:self.shape[0],0:self.shape[1]] = \
                self.trnDist[tkey][sval][0:self.shape[0], 0:self.shape[1]] + \
                (self.trnskims[tkey][sval].root._f_getChild(str(matnum))[0:self.shape[0], 0:self.shape[1]]*WALKSPEED/60.0)
            print "TIM_WAC after: tkey=%d tval=%s sval=%s trnDIST[1255,22] = %d" % (tkey, tval, sval, self.trnDist[tkey][sval][1254,21])

        if "TIM_WEG" in TRNSKIMKEY[sval]:
            matnum = TRNSKIMKEY[sval]["TIM_WEG"]
            print "TIM_WEG before: tkey=%d tval=%s sval=%s trnDIST[1255,22] = %d" % (tkey, tval, sval, self.trnDist[tkey][sval][1254,21])
            self.trnDist[tkey][sval][0:self.shape[0],0:self.shape[1]] = \
                self.trnDist[tkey][sval][0:self.shape[0], 0:self.shape[1]] + \
                (self.trnskims[tkey][sval].root._f_getChild(str(matnum))[0:self.shape[0], 0:self.shape[1]]*WALKSPEED/60.0)
            print "TIM_WEG after: tkey=%d tval=%s sval=%s trnDIST[1255,22] = %d" % (tkey, tval, sval, self.trnDist[tkey][sval][1254,21])

    def getMaxTAZnum(self):
        return self.shape[0]
        
    def getTripTravelTime(self, tripmode, segdir, otaz, dtaz, timeperiod):
        """
        Dumbed down version of getTripTravelAttr.  Assumes you have trip skims open!
        Units: minutes
        """
        if tripmode <= 6:
            # this is ok because of the PNR zones            
            if (otaz >= self.termtime.root._f_getChild("1").shape[0] or
                dtaz >= self.termtime.root._f_getChild("1").shape[0]):
                termtime = 0               
            elif segdir == 1:
                termtime = self.termtime.root._f_getChild("1")[otaz-1][dtaz-1]
            else:
                termtime = self.termtime.root._f_getChild("1")[dtaz-1][otaz-1]
            
            if tripmode == 1:
                return self.hwyskims[timeperiod].root._f_getChild("1")[otaz-1,dtaz-1] + termtime
            if tripmode == 2:
                return self.hwyskims[timeperiod].root._f_getChild("4")[otaz-1,dtaz-1] + termtime
            if tripmode == 3:
                return self.hwyskims[timeperiod].root._f_getChild("7")[otaz-1,dtaz-1] + termtime
            if tripmode == 4:
                return self.hwyskims[timeperiod].root._f_getChild("10")[otaz-1,dtaz-1] + termtime
            if tripmode == 5:
                return self.hwyskims[timeperiod].root._f_getChild("14")[otaz-1,dtaz-1] + termtime
            if tripmode == 6:
                return self.hwyskims[timeperiod].root._f_getChild("18")[otaz-1,dtaz-1] + termtime
            
        if tripmode == 10:
            d = self.nonmotskims.root._f_getChild("1")[otaz-1][dtaz-1]
            return d/WALKSPEED
        if (tripmode == 11):
            d = self.nonmotskims.root._f_getChild("1")[otaz-1][dtaz-1]
            return d/BIKESPEED

        if tripmode >= 12:
            return self.trnTime[timeperiod][TRIPTRNSKIMMAP[(tripmode,segdir)]][otaz-1,dtaz-1]/100.0

        return 0
    
    def getTripTravelDist(self, tripmode, segdir, otaz, dtaz, timeperiod):
        """
        Dumbed down version of getTripTravelAttr.  Assumes you have trip skims open!
        Units: miles
        """
        if tripmode <= 6:
            
            if tripmode == 1:
                return self.hwyskims[timeperiod].root._f_getChild("2")[otaz-1,dtaz-1]
            if tripmode == 2:
                return self.hwyskims[timeperiod].root._f_getChild("5")[otaz-1,dtaz-1]
            if tripmode == 3:
                return self.hwyskims[timeperiod].root._f_getChild("8")[otaz-1,dtaz-1]
            if tripmode == 4:
                return self.hwyskims[timeperiod].root._f_getChild("11")[otaz-1,dtaz-1]
            if tripmode == 5:
                return self.hwyskims[timeperiod].root._f_getChild("15")[otaz-1,dtaz-1]
            if tripmode == 6:
                return self.hwyskims[timeperiod].root._f_getChild("19")[otaz-1,dtaz-1]
            
        if tripmode == 10:
            return self.nonmotskims.root._f_getChild("1")[otaz-1][dtaz-1]
        if (tripmode == 11):
            return self.nonmotskims.root._f_getChild("1")[otaz-1][dtaz-1]

        if tripmode >= 12:
            return self.trnDist[timeperiod][TRIPTRNSKIMMAP[(tripmode,segdir)]][otaz-1,dtaz-1]/100.0        # hundredths of miles

        return 0
    
    def getTripTravelToll(self, tripmode, segdir, otaz, dtaz, timeperiod):
        """
        Dumbed down version of getTripTravelAttr.  Assumes you have trip skims open!
        Returns bridge tolls / value tolls and fares.  No operating costs or parking etc.
        Units: 1989 dollars.
        """
       # Roadway                
        if tripmode == 1: # drive alone
            return self.hwyskims[timeperiod].root._f_getChild("3")[otaz-1,dtaz-1]/100.0
        if tripmode == 2: # shared ride 2
            return self.hwyskims[timeperiod].root._f_getChild("6")[otaz-1,dtaz-1]/(100.0*2.0)
        if tripmode == 3: # shared ride 3
            return self.hwyskims[timeperiod].root._f_getChild("9")[otaz-1,dtaz-1]/(100.0*3.5)          
        if tripmode == 4: # toll-paying drive alone
            return  (self.hwyskims[timeperiod].root._f_getChild("12")[otaz-1,dtaz-1] + \
                     self.hwyskims[timeperiod].root._f_getChild("13")[otaz-1,dtaz-1])/100.0
        if tripmode == 5: # toll-paying SR2
            return (self.hwyskims[timeperiod].root._f_getChild("16")[otaz-1,dtaz-1] + \
                    self.hwyskims[timeperiod].root._f_getChild("17")[otaz-1,dtaz-1])/(100.0*2.0)
        if tripmode == 6: # toll-paying SR3
            return (self.hwyskims[timeperiod].root._f_getChild("20")[otaz-1,dtaz-1] + \
                    self.hwyskims[timeperiod].root._f_getChild("21")[otaz-1,dtaz-1])/(100.0*3.5)
        if tripmode <= 9:
            print "Don't know how to handle mode " + str(tripmode)
            return (0,0,0,0,0)       
        # Walk
        if tripmode == 10:
            return 0
        if (tripmode == 11):
            return 0
        
        skimname = TRIPTRNSKIMMAP[(tripmode,segdir)]
        return self.trnFare[timeperiod][skimname][otaz-1,dtaz-1]


    def getTourTravelAttr(self, tourmode, segdir, otaz, dtaz, timeperiod,
                          paysToPark, purpose, todepart, tddepart):
        """ Returns distance, time, out-of-pocket cost (fares, bridge & value tolls),
            operating cost, parking cost.  Units: miles, minutes, 1989 dollars.
        """
        if self.skimtype != "tour": 
            errorstr= "Getting tour travel attributes without opening tour skims..."
            raise Exception(errorstr)
            
        (d,t,f, opc, trippkcst) = (0,0,0,0,0)
        termtime                = 0

        # some roadway specific stuff
        if tourmode <= 6:
            # this is ok because of the PNR zones
            if (otaz >= self.termtime.root._f_getChild("1").shape[0] or
                dtaz >= self.termtime.root._f_getChild("1").shape[0]):
                termtime = 0            
            elif segdir == 1:
                termtime = self.termtime.root._f_getChild("1")[otaz-1][dtaz-1]
            else:
                termtime = self.termtime.root._f_getChild("1")[dtaz-1][otaz-1]
        
            tdur = DURATION_TOUR[todepart-1][tddepart-1]
            tdur = min(tdur, 8.0)
            
            # this is out of sftourmc\ModeChoiceModel.cpp
            pkcst = 0
            if paysToPark==1 and purpose==1:
                pkcst = self.prkcstwh[dtaz]
            elif purpose!=1:
                pkcst = self.prkcstoh[dtaz]
            trippkcst = pkcst*tdur
            
        if tourmode == 1: # drive alone
            t = self.hwyskims[timeperiod].root._f_getChild("1")[otaz-1,dtaz-1] + termtime
            d = self.hwyskims[timeperiod].root._f_getChild("2")[otaz-1,dtaz-1]
            f = self.hwyskims[timeperiod].root._f_getChild("3")[otaz-1,dtaz-1]/100.0
            opc = d*OPCOST
            if d < 0.01: # toll-paying?
                tourmode += 3
            else:
                return (d,t,f,opc,trippkcst)
        if tourmode == 2: # shared ride 2
            t = self.hwyskims[timeperiod].root._f_getChild("4")[otaz-1,dtaz-1] + termtime
            d = self.hwyskims[timeperiod].root._f_getChild("5")[otaz-1,dtaz-1]
            f = self.hwyskims[timeperiod].root._f_getChild("6")[otaz-1,dtaz-1]/(100.0*2.0)
            opc = d*OPCOST
            if d < 0.01: # toll-paying?
                tourmode += 3
            else:
                return (d,t,f,opc,trippkcst)
            
        if tourmode == 3: # shared ride 3
            t = self.hwyskims[timeperiod].root._f_getChild("7")[otaz-1,dtaz-1] + termtime
            d = self.hwyskims[timeperiod].root._f_getChild("8")[otaz-1,dtaz-1]
            f = self.hwyskims[timeperiod].root._f_getChild("9")[otaz-1,dtaz-1]/(100.0*3.5)
            opc = d*OPCOST
            if d < 0.01: # toll-paying?
                tourmode += 3
            else:
                return (d,t,f,opc,trippkcst)
            
        if tourmode == 4: # toll-paying drive alone
            t = self.hwyskims[timeperiod].root._f_getChild("10")[otaz-1,dtaz-1] + termtime
            d = self.hwyskims[timeperiod].root._f_getChild("11")[otaz-1,dtaz-1]
            f = (self.hwyskims[timeperiod].root._f_getChild("12")[otaz-1,dtaz-1] + \
                 self.hwyskims[timeperiod].root._f_getChild("13")[otaz-1,dtaz-1])/100.0
            opc = d*OPCOST
            return (d,t,f,opc,trippkcst)
        if tourmode == 5: # toll-paying SR2
            t = self.hwyskims[timeperiod].root._f_getChild("14")[otaz-1,dtaz-1] + termtime
            d = self.hwyskims[timeperiod].root._f_getChild("15")[otaz-1,dtaz-1]
            f = (self.hwyskims[timeperiod].root._f_getChild("16")[otaz-1,dtaz-1] + \
                 self.hwyskims[timeperiod].root._f_getChild("17")[otaz-1,dtaz-1])/(100.0*2.0)
            opc = d*OPCOST
            return (d,t,f,opc,trippkcst)
        if tourmode == 6: # toll-paying SR3
            t = self.hwyskims[timeperiod].root._f_getChild("18")[otaz-1,dtaz-1] + termtime
            d = self.hwyskims[timeperiod].root._f_getChild("19")[otaz-1,dtaz-1]
            f = (self.hwyskims[timeperiod].root._f_getChild("20")[otaz-1,dtaz-1] + \
                 self.hwyskims[timeperiod].root._f_getChild("21")[otaz-1,dtaz-1])/(100.0*3.5)
            opc = d*OPCOST
            return (d,t,f,opc,trippkcst)

        # Walk
        if tourmode == 7:
            d = self.nonmotskims.root._f_getChild("1")[otaz-1][dtaz-1]
            return (d, (d/WALKSPEED)*60, 0, 0, 0);
        if (tourmode == 8):
            d = self.nonmotskims.root._f_getChild("1")[otaz-1][dtaz-1]
            return (d, (d/BIKESPEED)*60, 0, 0, 0)

        # Transit
        if not self.useTempTrn:
            print "Not implemented"
            raise
        
        skimname = TOURTRNSKIMMAP[(tourmode,segdir)]
        d = self.trnDist[timeperiod][skimname][otaz-1,dtaz-1]              # hundredths of miles
        f = self.trnFare[timeperiod][skimname][otaz-1,dtaz-1]              # cents
        opc = self.trnDrvDist[timeperiod][skimname][otaz-1,dtaz-1]*OPCOST  # hundredths of miles x dollars = cents
        t = self.trnTime[timeperiod][skimname][otaz-1,dtaz-1]              # hundredths of minutes
            
        return (d/100.0, t/100.0, f/100.0, opc/100.0, 0)
        
    def getTripTravelAttr(self, tripmode, segdir, otaz, dtaz, timeperiod, lasttimeperiod,
                            curr_seg, paysToPark, purpose, totalstops, todepart, tddepart, primdest):
        """ Returns the distance, time, out-of-pocket cost (fares, bridge & value tolls), 
            operating cost, parking cost.  Units: miles, minutes, 1989 dollars.
            lasttimeperiod is the time of the last trip (same tour)
        """

        (d,t,f, opc, trippkcst) = (0,0,0,0,0)
        termtime                = 0

        
        # some roadway specific stuff
        if tripmode <= 6:
            # this is ok because of the PNR zones
            if (otaz >= self.termtime.root._f_getChild("1").shape[0] or
                dtaz >= self.termtime.root._f_getChild("1").shape[0]):
                termtime = 0            
            elif segdir == 1:
                termtime = self.termtime.root._f_getChild("1")[otaz-1][dtaz-1]
            else:
                termtime = self.termtime.root._f_getChild("1")[dtaz-1][otaz-1]

            # based on persdata.cpp. Uses the duration at the last stop, it seems to me...
            if segdir == 1:
                if curr_seg == 0:   segdur = DURATION_TRIP[todepart-1][timeperiod-1]
                else:               segdur = DURATION_TRIP[lasttimeperiod-1][timeperiod-1]
            else:
                segdur = DURATION_TRIP[lasttimeperiod-1][timeperiod-1]

            # this is straight out of sftripmc.  BOO.
            # TODO: put this in the disaggregate file.  and trip duration while
            # we're at it.
            
            # reroll paysToPark -- the passed one is for tours
            paysToPark = 0
            if purpose<=4:
                rnum = random.random()
                if rnum < self.ppaying[primdest]:
                    paysToPark = 1
            
            if paysToPark ==0: # technically sftripmc rolls the dice again rather than using tour paysToPark
                pkcst = 0
            elif purpose <= 4:   # school and work trips
                oPkcst=0
                dPkcst=0
                if curr_seg>0:      # not the first trip
                    oPkcst = self.prkcstwh[otaz]/2.0
                if curr_seg<(totalstops+2)-1:  # not the last trip
                    dPkcst = self.prkcstwh[dtaz]/2.0
                pkcst = oPkcst + dPkcst;
            else:                   # all other trips
                oPkcst=0
                dPkcst=0
                if curr_seg>0:      # not the first trip
                    oPkcst = self.prkcstoh[otaz]/2.0;
                if curr_seg<(totalstops+2)-1:   # not the last trip
                    dPkcst = self.prkcstoh[dtaz]/2.0;
                pkcst = oPkcst + dPkcst;
            
            # jef 10/03  capped parking cost for trip at $20
            trippkcst = pkcst*segdur
            if trippkcst>20.0:
                trippkcst = 20.0
                
            # print "segdur=%f trppkcst = %f" % (segdur, trippkcst)
                        
        # Roadway                
        if tripmode == 1: # drive alone
            t = self.hwyskims[timeperiod].root._f_getChild("1")[otaz-1,dtaz-1] + termtime
            d = self.hwyskims[timeperiod].root._f_getChild("2")[otaz-1,dtaz-1]
            f = self.hwyskims[timeperiod].root._f_getChild("3")[otaz-1,dtaz-1]/100.0
            opc = d*OPCOST
            if d < 0.01: # toll-paying?
                tripmode += 3
            else:
                return (d,t,f,opc,trippkcst)
        if tripmode == 2: # shared ride 2
            t = self.hwyskims[timeperiod].root._f_getChild("4")[otaz-1,dtaz-1] + termtime
            d = self.hwyskims[timeperiod].root._f_getChild("5")[otaz-1,dtaz-1]
            f = self.hwyskims[timeperiod].root._f_getChild("6")[otaz-1,dtaz-1]/(100.0*2.0)
            opc = d*OPCOST
            if d < 0.01: # toll-paying?
                tripmode += 3
            else:
                return (d,t,f,opc,trippkcst)
            
        if tripmode == 3: # shared ride 3
            t = self.hwyskims[timeperiod].root._f_getChild("7")[otaz-1,dtaz-1] + termtime
            d = self.hwyskims[timeperiod].root._f_getChild("8")[otaz-1,dtaz-1]
            f = self.hwyskims[timeperiod].root._f_getChild("9")[otaz-1,dtaz-1]/(100.0*3.5)
            opc = d*OPCOST
            if d < 0.01: # toll-paying?
                tripmode += 3
            else:
                return (d,t,f,opc,trippkcst)
            
        if tripmode == 4: # toll-paying drive alone
            t = self.hwyskims[timeperiod].root._f_getChild("10")[otaz-1,dtaz-1] + termtime
            d = self.hwyskims[timeperiod].root._f_getChild("11")[otaz-1,dtaz-1]
            f = (self.hwyskims[timeperiod].root._f_getChild("12")[otaz-1,dtaz-1] + \
                 self.hwyskims[timeperiod].root._f_getChild("13")[otaz-1,dtaz-1])/100.0
            opc = d*OPCOST
            return (d,t,f,opc,trippkcst)
        if tripmode == 5: # toll-paying SR2
            t = self.hwyskims[timeperiod].root._f_getChild("14")[otaz-1,dtaz-1] + termtime
            d = self.hwyskims[timeperiod].root._f_getChild("15")[otaz-1,dtaz-1]
            f = (self.hwyskims[timeperiod].root._f_getChild("16")[otaz-1,dtaz-1] + \
                 self.hwyskims[timeperiod].root._f_getChild("17")[otaz-1,dtaz-1])/(100.0*2.0)
            opc = d*OPCOST
            return (d,t,f,opc,trippkcst)
        if tripmode == 6: # toll-paying SR3
            t = self.hwyskims[timeperiod].root._f_getChild("18")[otaz-1,dtaz-1] + termtime
            d = self.hwyskims[timeperiod].root._f_getChild("19")[otaz-1,dtaz-1]
            f = (self.hwyskims[timeperiod].root._f_getChild("20")[otaz-1,dtaz-1] + \
                 self.hwyskims[timeperiod].root._f_getChild("21")[otaz-1,dtaz-1])/(100.0*3.5)
            opc = d*OPCOST
            return (d,t,f,opc,trippkcst)
        if tripmode <= 9:
            print "Don't know how to handle mode " + str(tripmode)
            return (0,0,0,0,0)       
        # Walk
        if tripmode == 10:
            d = self.nonmotskims.root._f_getChild("1")[otaz-1][dtaz-1]
            return (d, (d/WALKSPEED)*60, 0, 0, 0);
        if (tripmode == 11):
            d = self.nonmotskims.root._f_getChild("1")[otaz-1][dtaz-1]
            return (d, (d/BIKESPEED)*60, 0, 0, 0)
        
        # Transit
        if not self.useTempTrn:
            print "Not implemented"
            raise
        
        while (t<0.01 and tripmode >= 12):
            skimname = TRIPTRNSKIMMAP[(tripmode,segdir)]
            d = self.trnDist[timeperiod][skimname][otaz-1,dtaz-1]
            f = self.trnFare[timeperiod][skimname][otaz-1,dtaz-1]
            opc = self.trnDrvDist[timeperiod][skimname][otaz-1,dtaz-1]*OPCOST
            t = self.trnTime[timeperiod][skimname][otaz-1,dtaz-1]
            
            if t>0.01:
                return (d/100.0, t/100.0, f/100.0, opc/100.0, 0)
            
            # print "Switching transit mode: Got zero time for O=%d D=%d mode=%d time=%d segdir=%d skim=%s d=%f t=%f f=%f opc=%f" \
            #     % (otaz, dtaz, tripmode, timeperiod, \
            #       segdir, self.skimdir, d, t, f, opc/100.0)
            tripmode -= 1

        return (d/100.0, t/100.0, f/100.0, opc, 0)
        # skimname = TRIPTRNSKIMMAP[(tripmode,segdir)]
        # numtt = NUMTTSKIMS[skimname]
        # t = 0
        # for i in range(1,numtt+1):
        #    t += self.trnskims[timeperiod][skimname].root._f_getChild(str(i))[otaz-1][dtaz-1]
        #d = self.trnskims[timeperiod][skimname].root._f_getChild(str(numtt+1))[otaz-1][dtaz-1]
        #f = self.trnskims[timeperiod][skimname].root._f_getChild(str(numtt+2))[otaz-1][dtaz-1]
        #return (d/100.0, t/100.0, f)
        
    def getTripTravelAttr2(self, tripmode, segdir, otaz, dtaz, timeperiod, lasttimeperiod,
                      curr_seg, paysToPark, purpose, totalstops, todepart, tddepart, primdest):
        """ separates OVT and IVT and combines cost to return d,ivt,ovt,c
        """

        (d,ivt,ovt,c) = (0,0,0,0)
        termtime                = 0

        
        # some roadway specific stuff
        if tripmode <= 6:
            # this is ok because of the PNR zones
            if (otaz >= self.termtime.root._f_getChild("1").shape[0] or
               dtaz >= self.termtime.root._f_getChild("1").shape[0]):
                termtime = 0
            elif segdir == 1:
                termtime = self.termtime.root._f_getChild("1")[otaz-1][dtaz-1]
            else:
                termtime = self.termtime.root._f_getChild("1")[dtaz-1][otaz-1]

            # based on persdata.cpp. Uses the duration at the last stop, it seems to me...
            if segdir == 1:
                if curr_seg == 0:   segdur = DURATION_TRIP[todepart-1][timeperiod-1]
                else:               segdur = DURATION_TRIP[lasttimeperiod-1][timeperiod-1]
            else:
                segdur = DURATION_TRIP[lasttimeperiod-1][timeperiod-1]

            # this is straight out of sftripmc.  BOO.
            # TODO: put this in the disaggregate file.  and trip duration while
            # we're at it.
            
            # reroll paysToPark -- the passed one is for tours
            paysToPark = 0
            if purpose<=4:
                rnum = random.random()
                if rnum < self.ppaying[primdest]:
                    paysToPark = 1
                                
            if paysToPark ==0:
                pkcst = 0
            elif purpose <= 4:   # school and work trips
                oPkcst=0
                dPkcst=0
                if curr_seg>0:      # not the first trip
                    oPkcst = self.prkcstwh[otaz]/2.0
                if curr_seg<(totalstops+2)-1:  # not the last trip
                    dPkcst = self.prkcstwh[dtaz]/2.0
                pkcst = oPkcst + dPkcst;
            else:                   # all other trips
                oPkcst=0
                dPkcst=0
                if curr_seg>0:      # not the first trip
                    oPkcst = self.prkcstoh[otaz]/2.0;
                if curr_seg<(totalstops+2)-1:   # not the last trip
                    dPkcst = self.prkcstoh[dtaz]/2.0;
                pkcst = oPkcst + dPkcst;
            
            # jef 10/03  capped parking cost for trip at $20
            trippkcst = pkcst*segdur
            if trippkcst>20.0:
                trippkcst = 20.0
                
            # print "segdur=%f trppkcst = %f" % (segdur, trippkcst)
                        
        # Roadway                
        if tripmode == 1: # drive alone
            ivt = self.hwyskims[timeperiod].root._f_getChild("1")[otaz-1,dtaz-1]
            ovt = termtime
            d = self.hwyskims[timeperiod].root._f_getChild("2")[otaz-1,dtaz-1]
            f = self.hwyskims[timeperiod].root._f_getChild("3")[otaz-1,dtaz-1]/100.0
            opc = d*OPCOST
            c = f + opc + trppkcst
            if d < 0.01: # toll-paying?
                tripmode += 3
            else:
                return (d,ivt,ovt,c)
        if tripmode == 2: # shared ride 2
            ivt = self.hwyskims[timeperiod].root._f_getChild("4")[otaz-1,dtaz-1]
            ovt = termtime
            d = self.hwyskims[timeperiod].root._f_getChild("5")[otaz-1,dtaz-1]
            f = self.hwyskims[timeperiod].root._f_getChild("6")[otaz-1,dtaz-1]/(100.0*2.0)
            opc = d*OPCOST
            c = f + opc + trppkcst
            if d < 0.01: # toll-paying?
                tripmode += 3
            else:
                return (d,ivt,ovt,c)
            
        if tripmode == 3: # shared ride 3
            ivt = self.hwyskims[timeperiod].root._f_getChild("7")[otaz-1,dtaz-1]
            ovt = termtime
            d = self.hwyskims[timeperiod].root._f_getChild("8")[otaz-1,dtaz-1]
            f = self.hwyskims[timeperiod].root._f_getChild("9")[otaz-1,dtaz-1]/(100.0*3.5)
            opc = d*OPCOST
            c = f + opc + trppkcst
            if d < 0.01: # toll-paying?
                tripmode += 3
            else:
                return (d,ivt,ovt,c)
            
        if tripmode == 4: # toll-paying drive alone
            ivt = self.hwyskims[timeperiod].root._f_getChild("10")[otaz-1,dtaz-1] 
            ovt = termtime
            d = self.hwyskims[timeperiod].root._f_getChild("11")[otaz-1,dtaz-1]
            f = (self.hwyskims[timeperiod].root._f_getChild("12")[otaz-1,dtaz-1] + \
                 self.hwyskims[timeperiod].root._f_getChild("13")[otaz-1,dtaz-1])/100.0
            opc = d*OPCOST
            c = f + opc + trppkcst
            return (d,ivt,ovt,c)
        if tripmode == 5: # toll-paying SR2
            ivt = self.hwyskims[timeperiod].root._f_getChild("14")[otaz-1,dtaz-1] 
            ovt = termtime
            d = self.hwyskims[timeperiod].root._f_getChild("15")[otaz-1,dtaz-1]
            f = (self.hwyskims[timeperiod].root._f_getChild("16")[otaz-1,dtaz-1] + \
                 self.hwyskims[timeperiod].root._f_getChild("17")[otaz-1,dtaz-1])/(100.0*2.0)
            opc = d*OPCOST
            c = f + opc + trppkcst
            return (d,ivt,ovt,c)
        if tripmode == 6: # toll-paying SR3
            ivt = self.hwyskims[timeperiod].root._f_getChild("18")[otaz-1,dtaz-1] 
            ovt = termtime
            d = self.hwyskims[timeperiod].root._f_getChild("19")[otaz-1,dtaz-1]
            f = (self.hwyskims[timeperiod].root._f_getChild("20")[otaz-1,dtaz-1] + \
                 self.hwyskims[timeperiod].root._f_getChild("21")[otaz-1,dtaz-1])/(100.0*3.5)
            opc = d*OPCOST
            c = f + opc + trppkcst
            return (d,ivt,ovt,c)
        if tripmode <= 9:
            print "Don't know how to handle mode " + str(tripmode)
            return (0,0,0,0,0)       
        # Walk
        if tripmode == 10:
            d = self.nonmotskims.root._f_getChild("1")[otaz-1][dtaz-1]
            return (d, 0, (d/WALKSPEED)*60, 0);
        if (tripmode == 11):
            d = self.nonmotskims.root._f_getChild("1")[otaz-1][dtaz-1]
            return (d, 0, (d/BIKESPEED)*60, 0)
        
        # Transit
        if not self.useTempTrn:
            print "Not implemented"
            raise
        
        while (t<0.01 and tripmode >= 12):
            skimname = TRIPTRNSKIMMAP[(tripmode,segdir)]
            d = self.trnDist[timeperiod][skimname][otaz-1,dtaz-1]
            f = self.trnFare[timeperiod][skimname][otaz-1,dtaz-1]
            opc = self.trnDrvDist[timeperiod][skimname][otaz-1,dtaz-1]*OPCOST
            t = self.trnTime[timeperiod][skimname][otaz-1,dtaz-1]
            c = f + opc + trppkcst
            if t>0.01:
                return (d/100.0, ivt/100.0, ovt/100.0, c/100.0)
            
            # print "Switching transit mode: Got zero time for O=%d D=%d mode=%d time=%d segdir=%d skim=%s d=%f t=%f f=%f opc=%f" \
            #     % (otaz, dtaz, tripmode, timeperiod, \
            #       segdir, self.skimdir, d, t, f, opc/100.0)
            tripmode -= 1

        return  (d/100.0, ivt/100.0, ovt/100.0, c/100.0)