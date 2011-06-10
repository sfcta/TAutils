#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Creates shapefiles of transit with lots of variables about overcrowding """

import getopt,os,sys,time,traceback
import cube
from dbfpy import dbf

__author__ = "Elizabeth Sall and Lisa Zorn, San Francisco County Transportation Authority"
__license__= "GPL"
__email__  = "elizabeth@sfcta.org"
__date__   = "2008-07-07"

USAGE=r"""

python overcrowdedTransit_gis.py [-d nodes.dbf|-n netfile.net] [-f freeflow.dbf] [-s output.mdb] [-r output.xls] 
  selection timeperiod trnAssign.dbf

e.g. python overcrowdedTransit_gis.py 
        -s X:\Projects\ATG\round4\410p2009.Target\transitCrowding2\tc3.mdb
        -n X:\Projects\ATG\round4\410p2009.Target\TMP_TP2_pm.tmp
        MUNI AM X:\Projects\ATG\round4\410p2009.NoProject\SFALLMSAAM.dbf 

Exactly one of the following must be passed:
-n *netfile.net* is a cube network with the transit nodes (e.g. tmp_tp2_pm.tmp)
-d *nodes.dbf* is a mapping of nodes to x,y coords

Also pass in freeflow.dbf information to calculate delay from freeflow:
-f *freeflow.dbf*

At least one of the following must be passed:
-s *output.mdb* (can be full path or relative) is the geodatabase to create
-r *output.xls* (can be full path or relative) is the reportfile to create

*selection* is one of ['SF', 'MUNI', 'crowded', 'overCapacity', 'crowdedInSF', 'overCapacityInSF', 'test']
*timeperiod* is one of ['AM', 'MD', 'PM', 'EV', 'EA']
*trnAssign.dbf* (can be full path or relative) is the aggregated assignment

Creates an *output.mdb* and/or an *output.xls* depending on *selection*:
 *all*              :all lines (not including access/egress, etc)
 *SF*               :all lines with any links in SF
 *MUNI*             :all MUNI lines
 *crowded*          :max load > 0.8
 *overCapacity*     :max load > 1.0
 *crowdedInSF*      :max load > 0.8 for a link in SF
 *overCapacityInSF* :max load > 1.0 for a link in SF
 *test*             :for hand edits...

"""    

import win32com.client
class arcgisscripting(object):
    @staticmethod
    def create():
        return win32com.client.Dispatch('esriGeoprocessing.GpDispatch.1')

HWYEXPORTSCRIPT = r"Y:\champ\util\exportHwyFromPy.s"

def createGDB(gp,dir,GDBname):
    """
    Creates the a personal geodatabase called *GDBname* in the given *dir*, if it doesn't exist already
    """
    if not os.path.exists(dir):
        os.mkdir(dir)
    if not os.path.exists(os.path.join(dir,GDBname)):
        gp.CreatePersonalGDB(dir,GDBname)
        print "Created GeoDataBase: %s" % (os.path.join(dir,GDBname))
    else:
        print "Geodatabase %s already exists" % (GDBname)


class TransitCrowding():

    def __init__(self, timePeriod, trnAssgnFile, selection=None):
        self.timePeriod     = timePeriod
        self.geodbFile      = None
        
        self.readDBF(trnAssgnFile) 
        
        self.selectedLines=self.selectLines(selection)
        #self.asShapefile(self.selectedLines,name=name)

        
    def readDBF(self,trnAssgnFile):
        """
        Reads the given transit assignment dbf
        Fills in *self.lines* and references them by name in *self.linesByName*
        """
        self.lines          = []
        self.linesByName    = {}  # name -> Line object        
        infile = dbf.Dbf(trnAssgnFile,readOnly=True)
        for rec in infile:
            if rec['NAME'] not in self.linesByName.keys(): 
                l=Line(self.timePeriod, rec)
                #print "adding line ",rec['NAME']                
                self.lines.append(l)
                self.linesByName[rec['NAME']]=l
                
            l = self.linesByName[rec['NAME']]
            l.addLink(rec)

        infile.close()
        print "Read %d lines from %s"  % (len(self.lines),trnAssgnFile)

    def selectLines(self,selection):
        print "selecting lines to display"
        selectedLines=[]
        for line in self.lines:
            if line.isin(selection): 
                selectedLines.append(line)
        return selectedLines
                
    def reportSelectedLinesIntoShapefile(self,gp,geodbFile,name,individualLines=False):
        """
        If individualLines, each line is a shapefile
        otherwise, each line goes into the single named shapefile
        """
        self.geodbFile = geodbFile
        if individualLines:
            count = 0
            for line in self.selectedLines:
                line.asShapefile(gp,self.geodbFile,self.nodeToCoords)
                count += 1

                if count % 100 == 0:
                    print "Wrote %d of %d lines into shapefile" % (count, len(self.selectedLines))
                
        else:
            self.createShapefile(gp,name)
            count = 0
            for line in self.selectedLines:
                line.addToShapefile(self.shapeFile)
                count += 1
                
                if count % 100 == 0:
                    print "Wrote %d of %d lines into shapefile" % (count, len(self.selectedLines))
    
    def createShapefile(self,gp,name):
        shapeFileName= "transit_%s%s" % (name if name else "all",self.timePeriod)
        time.sleep(3)      
        try:
            gp.CreateFeatureClass(self.geodbFile, shapeFileName,"POLYLINE")
        except:
            print "GIS error:", gp.GetMessages()
            raise
            
        self.shapeFile = os.path.join(self.geodbFile, shapeFileName)
        print "created ", self.shapeFile 
        
        try:
            gp.AddField(self.shapeFile,"lineAB",    "TEXT","25")
            gp.AddField(self.shapeFile,"a",         "long","8")
            gp.AddField(self.shapeFile,"b",         "long","8")
            gp.AddField(self.shapeFile,"line",      "TEXT","15")
            gp.AddField(self.shapeFile,"timePeriod","TEXT","3")
            gp.AddField(self.shapeFile,"freq",      "float","6","2")
            gp.AddField(self.shapeFile,"perCap",    "float","6","2")
            gp.AddField(self.shapeFile,"vehCap",    "float","6","2")
            gp.AddField(self.shapeFile,"vehType",   "TEXT","30")
            gp.AddField(self.shapeFile,"load",      "float","6","2")
            gp.AddField(self.shapeFile,"vol",       "float","8","2")
            gp.AddField(self.shapeFile,"traveltime","float","8","2")
            gp.AddField(self.shapeFile,"delayVsFF", "float", "8", "2")
            gp.AddField(self.shapeFile,"dist",      "float","6","2")
            gp.AddField(self.shapeFile,"speed",     "float","6","2")
            gp.AddField(self.shapeFile,"inSF",      "short","2")
        except:
            print "GIS error:", gp.GetMessages()
            raise

    def createReport(self,reportFile):
        import xlwt, xlrd
        from xlutils.copy import copy
        
        if os.path.exists(reportFile):
            curworkbook = xlrd.open_workbook(filename=reportFile, formatting_info=True)
            workbook = copy(curworkbook)
        else:
            workbook = xlwt.Workbook()
            
        fields=['Line','System','Time Period','Frequency','Vehicle','Vehicle Capacity','Period Capacity',
                'Boardings','Impossible Boardings','PMT','Impossible PMT','Max Load',
                'SF Boardings','SF Impossible Boardings','SF PMT','SF Impossible PMT','SF Max Load']
    

        worksheet= workbook.add_sheet(self.timePeriod)
        row = 0
        col = 0
        for item in fields:
            worksheet.write(row,col,item)
            col+=1
        row+=1
        
        for line in self.selectedLines:
            col = 0
            data={}
            data["Line"]                    = line.name
            data["System"]                  = line.system
            data["Time Period"]             = line.timePeriod
            data["Frequency"]               = line.freq
            data["Vehicle"]                 = line.vehType
            data["Vehicle Capacity"]        = line.vehicleCap
            data["Period Capacity"]         = line.periodCap
            data["Max Load"]                = line.maxLoad
            data["SF Max Load"]             = line.maxLoadSF
            data["Boardings"]               = line.boards
            data["SF Boardings"]            = line.boardsSF
            data["PMT"]                     = line.pmt
            data["SF PMT"]                  = line.pmtSF
            data["Impossible Boardings"]    = line.impossBoards
            data["SF Impossible Boardings"] = line.impossBoardsSF
            data["Impossible PMT"]          = line.impossPmt
            data["SF Impossible PMT"]       = line.impossPmtSF
            for item in fields:
                worksheet.write(row,col,data[item])
                col +=1
            row +=1
    
        
        workbook.save(reportFile) 
    
class Line(object):
    def __init__(self, timeperiod, rec):
        self.geodbFile      = ''
        self.name           = rec['NAME']
        self.system         = rec['SYSTEM']
        self.timePeriod     = timeperiod
        self.freq           = float(rec['FREQ'])
        self.periodCap      = float(rec['PERIODCAP'])
        self.vehicleCap     = float(rec['VEHCAP'])
        self.vehType        = rec['VEHTYPE']
        self.linkList       = []
        self.maxLoad        = 0.0
        self.maxLoadSF      = 0.0
        self.boards         = 0.0
        self.boardsSF       = 0.0
        self.pmt            = 0.0
        self.pmtSF          = 0.0
        self.impossBoards   = 0.0
        self.impossBoardsSF = 0.0
        self.impossPmt      = 0.0
        self.impossPmtSF    = 0.0
        self.shapeFile      =''
        self.inSF           = False

    def addLink(self,rec):
        newLink=Link(self,rec)
        self.linkList.append(newLink)
        
        if newLink.load > self.maxLoad: 
            if newLink.vol > 1: #placeholder work around for some sort of DBF bug that sets all vols to 1.0 for some first links...and the loads are ridic crazy
                self.maxLoad = newLink.load
        if newLink.inSF>0: 
            self.inSF=True
            if newLink.load>self.maxLoadSF: 
                self.maxLoadSF=newLink.load
                
        self.boards   += newLink.boardA
        self.boardsSF += newLink.boardA*newLink.startSF
        self.pmt      += newLink.pmt
        self.pmtSF    += newLink.pmt*newLink.inSF
        self.impossBoards   += newLink.impossBoardsB + newLink.impossBoardsA
        self.impossBoardsSF += newLink.impossBoardsA*newLink.startSF + newLink.impossBoardsB*(newLink.startSF*newLink.endSF)
        self.impossPmt      += newLink.impossPmt
        self.impossPmtSF    += newLink.impossPmt*newLink.inSF

    def isin(self,selection):
        
        if not selection:
            if self.name[0] == "*":
                return False
            else:
                return True
            
        if selection.upper() in ['SF','SAN FRANCISCO','IN SF','INSF']:
            if self.inSF>0 and self.name[0] != "*": 
                return True
            else: return False
        if selection == 'crowded':
            if self.maxLoad>0.8: 
                return True
            else:
                return False
        elif selection.upper() in ['MUNI','SF MUNI']:
            if self.system == 'SF MUNI':
                return True
            else: 
                return False
        elif selection in ['crowded']:
            if self.maxLoad>0.8:
                return True
            else:
                return False
        elif selection in ['overCapacity','overCap']:
            if self.maxLoad>1.0: 
                return True
            else:
                return False
        elif selection.upper() in  ['CROWDEDINSF','CROWDED IN SF','SFCROWDED']:
            if self.maxLoadSF>0.8:
                return True
            else: 
                return False
        elif selection.upper() in  ['OVERCAPACITYINSF','OVERCAPINSF','OVER CAPACITY IN SF','OVER CAP IN SF','SFOVERCAPACITY','SFOVERCAP']:
            if self.maxLoadSF>1.0:
                return True
            else: 
                return False
        elif selection.upper() is ['TEST']:
            if self.name in ['MUNKI','100_BART_BLU']:
                return True
            else:
                return False
        else:
            print "DONT UNDERSTAND SELECTION %s" % (selection)
    
    def addToShapefile(self,shapeFile):
        for link in self.linkList:
            link.addToShapefile(shapeFile)
        # print "added %s to %s" % (self.name, shapeFile)
    
    def asShapefile(self,gp,geodbFile):
        self.geodbFile = geodbFile
        self.createLineShapefile(gp,geodbFile)
        for link in self.linkList:
            link.addToShapefile(self.shapeFile)
    
    def createLineShapefile(self,gp,geodbFile):
        shapeFileName= "line%s_%s" % (self.name.replace('.','_').replace('-','_'), self.timePeriod)
        self.geodbFile = geodbFile
        
        try:
            gp.CreateFeatureClass(self.geodbFile, shapeFileName,"POLYLINE")
        except:
            print "GIS error:", gp.GetMessages()
            raise
            
        self.shapeFile = os.path.join(self.geodbFile, shapeFileName)
        print "created ", self.shapeFile 
        
        try:
            gp.AddField(self.shapeFile,"lineAB",    "TEXT","25")
            gp.AddField(self.shapeFile,"a",         "long","8")
            gp.AddField(self.shapeFile,"b",         "long","8")
            gp.AddField(self.shapeFile,"line",      "TEXT","15")
            gp.AddField(self.shapeFile,"timePeriod","TEXT","3")
            gp.AddField(self.shapeFile,"freq",      "float","6","2")
            gp.AddField(self.shapeFile,"perCap",    "float","6","2")
            gp.AddField(self.shapeFile,"vehCap",    "float","6","2")
            gp.AddField(self.shapeFile,"vehType",   "TEXT","30")
            gp.AddField(self.shapeFile,"load",      "float","6","2")
            gp.AddField(self.shapeFile,"vol",       "float","8","2")
            gp.AddField(self.shapeFile,"traveltime","float","8","2")
            gp.AddField(self.shapeFile,"delayVsFF", "float", "8", "2")
            gp.AddField(self.shapeFile,"dist",      "float","6","2")
            gp.AddField(self.shapeFile,"speed",     "float","6","2")
            gp.AddField(self.shapeFile,"inSF",      "short","2")
        except:
            print "GIS error:", gp.GetMessages()
            raise
       
        
class Link():
    # static
    warned = []
    nodeToCoords = None
    freeflowTime = {}
    UNKNOWN = 999
    
    @staticmethod
    def initializeNodeToCoords(netFile, nodeDbfFile):
        if netFile:
            Link.nodeToCoords=cube.import_nodes_from_csv(networkFile=netFile)
            print "Read %d nodes and their coordinates from %s" % (len(Link.nodeToCoords), netFile)
        elif nodeDbfFile:
            Link.nodeToCoords = {}
            dbfin = dbf.Dbf(nodeDbfFile, readOnly=True, new=False)
            for rec in dbfin:
                Link.nodeToCoords[rec["N"]] = (rec["X"],rec["Y"])
            dbfin.close()
            print "Read %d nodes and their coordinates from %s" % (len(Link.nodeToCoords), nodeDbfFile)
        else:
            raise
            
    @staticmethod
    def initializeFreeflowTimes(freeflowFile):
        """
        Read the freeflowFile and keep attributes
        """
        Link.freeflowTime = {}
        dbfin = dbf.Dbf(freeflowFile, readOnly=True, new=False)
        for rec in dbfin:
            Link.freeflowTime[(rec["A"],rec["B"])] = rec["TIME"]
        dbfin.close()
        
    def __init__(self,lineInstance,rec):
        """
        Initialize with the given record and line instance.
        *nodeToCoords* maps node numbers to (x,y) and is used to determine if nodes are in SF
        """
        self.lineRef    = lineInstance
        self.a          = int(float(rec['A']))
        self.b          = int(float(rec['B']))
        self.lineAB     = "%s %d %d" % (self.lineRef.name, self.a, self.b)
        self.vol        = float(rec['AB_VOL'])
        if self.lineRef.periodCap > 0: 
            self.load   = self.vol/self.lineRef.periodCap
        else:
            self.load   = -1.0
        self.seq        = int(rec['SEQ'])
        self.boardA     = float(rec['AB_BRDA'])
        self.boardB     = float(rec['AB_BRDB'])
        self.exitB      = float(rec['AB_XITB'])
        self.dist       = float(rec['DIST'])/100.0
        self.time       = float(rec['TIME'])/100.0
        
        # delay over freeflow
        if Link.freeflowTime and Link.freeflowTime.has_key((self.a,self.b)):
            self.delayFromFF = self.time - Link.freeflowTime[(self.a,self.b)]
        else:
            self.delayFromFF = Link.UNKNOWN
        
        try:
            self.speed  = self.dist*60/self.time
        except:
            self.speed  = -1
        self.pmt        = self.vol*self.dist
        self.pht        = self.vol*self.time/60
        self.overCapVol = max(0,self.vol-self.lineRef.periodCap)
        self.impossPmt  = self.overCapVol*self.dist

        self.impossBoardsB = 0
        self.impossBoardsA = 0
        if self.vol-self.exitB > self.lineRef.periodCap: #no room
            self.impossBoardsB = self.boardB
            #print self.impossBoards,"=",self.boardB,"   ---all!",self.vol,"-",self.exitB," > ",self.periodCap
        
        elif (self.vol-self.exitB+self.boardB)>self.lineRef.periodCap:
            self.impossBoards = self.boardB - (self.lineRef.periodCap - self.vol + self.exitB)
            #print self.impossBoards,"=",self.boardB,"- (",self.periodCap,"-",self.vol,"+",self.exitB,")"

        # account for boardings at first node exceeding total capacity
        if self.seq==1:
            self.impossBoardsA=max(0,self.boardA-self.lineRef.periodCap)

        
        try:
            (self.ax,self.ay)  = Link.nodeToCoords[self.a]
            (self.bx,self.by)  = Link.nodeToCoords[self.b]
            
            self.inSF    = 0
            self.startSF = 0
            self.endSF   = 0
            if cube.nodeInBoundBox((self.ax,self.ay),cube.SFBOUNDBOX):
                self.inSF += 0.5
                self.startSF = 1
            if cube.nodeInBoundBox((self.bx,self.by),cube.SFBOUNDBOX):
                self.inSF  += 0.5
                self.endSF = 1
        except:
            if str(sys.exc_info()[1]) not in Link.warned:
                print "Unexpected error looking up node coordinates:", str(sys.exc_info()[1])
                print "Assuming non-SF."
                Link.warned.append(str(sys.exc_info()[1]))
            self.inSF   = 0
            self.startSF= 0
            self.endSF  = 0
        
    def addToShapefile(self,shapefile):
        
        cur                 = gp.InsertCursor(shapefile) 
        lineArray           = gp.CreateObject("Array")
        self.pointa         = gp.CreateObject("Point")
        self.pointa.id      = str(self.a)
        self.pointa.x       = self.ax
        self.pointa.y       = self.ay
        lineArray.add(self.pointa)
        self.pointb         = gp.CreateObject("Point")
        self.pointb.id      = str(self.b)
        self.pointb.x       = self.bx
        self.pointb.y       = self.by
        lineArray.add(self.pointb)
        self.feature        = cur.NewRow()
        self.feature.shape  = lineArray
        
        if self.inSF: 
            self.feature.inSF = 1
        else: 
            self.feature.inSF = 0
        self.feature.lineAB     = self.lineAB
        self.feature.line       = self.lineRef.name   
        self.feature.timePeriod = self.lineRef.timePeriod
        self.feature.freq       = self.lineRef.freq 
        self.feature.perCap     = self.lineRef.periodCap 
        self.feature.vehCap     = self.lineRef.vehicleCap
        self.feature.vehType    = self.lineRef.vehType   
        self.feature.a          = self.a    
        self.feature.b          = self.b   
        self.feature.load       = self.load 
        self.feature.vol        = "%8.2f" % self.vol 
        self.feature.traveltime = "%8.2f" % self.time
        self.feature.delayVsFF  = "%8.2f" % self.delayFromFF
        self.feature.dist       = self.dist
        self.feature.speed      = self.speed
        cur.InsertRow(self.feature)




if __name__ == '__main__':
    

    optlist, args = getopt.getopt(sys.argv[1:], "f:r:s:n:d:")

    reportFile      = None
    geodbFile       = None
    netFile         = None
    nodeDbfFile     = None
    freeflowFile    = None
    for o,a in optlist:
        if o=="-r":   reportFile    = a
        elif o=="-s": geodbFile     = a
        elif o=="-n": netFile       = a
        elif o=="-d": nodeDbfFile   = a
        elif o=="-f": freeflowFile  = a

    if netFile==None and nodeDbfFile==None:
        print USAGE
        print ""
        print "No netfile or node dbf file!"
        sys.exit(2)
    
    if netFile and nodeDbfFile:
        print USAGE
        print ""
        print "Either netfile or nodefile must be specified but not both"
        sys.exit(2)
        
    if reportFile==None and geodbFile==None:
        print USAGE
        print ""
        print "No output specified, nothing to do!"
        sys.exit(2)

    if len(args) != 3: 
        print USAGE
        exit(2)
        
    selection       = args[0]
    timeperiod      = args[1]
    trnAssgnFile    = args[2]
    
    if selection not in ['all', 'SF', 'MUNI', 'crowded', 'overCapacity', 'crowdedInSF', 'overCapacityInSF', 'test']:
        print USAGE
        sys.exit(2)
    if selection == 'all':
        selection = None

    Link.initializeNodeToCoords(netFile, nodeDbfFile)
    
    if freeflowFile: Link.initializeFreeflowTimes(freeflowFile)
    
    tc=TransitCrowding(timeperiod, trnAssgnFile, selection)

    if reportFile:
        tc.createReport(reportFile)
    if geodbFile:
        gp=arcgisscripting.create()
        
        # create the geodatabase if needed
        absGeodbFile = os.path.abspath(geodbFile)
        (geodir,geofile) = os.path.split(absGeodbFile)
        createGDB(gp, geodir, geofile)
            
        tc.reportSelectedLinesIntoShapefile(gp,absGeodbFile,name=selection)