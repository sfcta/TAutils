#!/usr/bin/env python

"""Quick converter from h5 matrix to dbf. Originally written to convert bike logsums
to dbfs for visualizaton. 
"""

import getopt, numpy, os, sys
from tables import IsDescription,Int32Col,Float32Col,openFile,Float32Atom,Filters,CArray
from dbfpy import dbf

__author__ = "Lisa Zorn, San Francisco County Transportation Authority"
__license__= "GPL"
__email__  = "lisa@sfcta.org"
__date__   = "Nov 9, 2010" 

INPUT_H5    = r"X:\Projects\BikeModel\trace\bike_model_output\BikeLogsum.h5"
MODE        = "select"
ORIGIN      = -1
DESTINATION = -1

USAGE = """

 python h5matrixToDbf.py [-o|-d taz] [select|to|from] input_h5
 
 Reads input_h5, such as PERSONTRIPS_DAILY.h5 or BikeLogsums.h5!
 
 For select mode, either an origin or a destination must be specified; output will be
 just the given row or columns in the children of the H5.
 
 For to mode, output will be the sums of the rows
 For from mode, output will be the sums of the cols
"""

try:
    optlist,args    = getopt.getopt(sys.argv[1:],"d:o:")
except getopt.GetoptError, err:
    print str(err)
    print USAGE
    sys.exit(2)

if len(args) < 2: 
    print USAGE
    sys.exit(1)
MODE            = args[0]
INPUT_H5        = args[1]
for o,a in optlist:
    if o=="-o": ORIGIN = int(a)
    if o=="-d": DESTINATION = int(a)

print "Opening " + INPUT_H5
h5file = openFile(INPUT_H5,mode="r")

(head,tail) = os.path.split(INPUT_H5)
tail = tail.rsplit(".",1)[0]
outfilename = tail + "_" + MODE
    
if MODE=="select":

    colname = "nocol"
    if ORIGIN >= 0:
        outfilename += "_origin%d" % ORIGIN
        colname = "DEST"
    elif DESTINATION >= 0:
        outfilename += "_destination%d" % DESTINATION
        colname = "ORIG"
    else:
        print "No origin nor destination specified."
        sys.exit(-1)

elif MODE=="to": colname = "DEST"
elif MODE=="from": colname = "ORIG"
else:
    print USAGE
    sys.exit(1)

outfilename += ".dbf"

arr = {}
for node in h5file.root:
    childname = node.name

    if MODE=="select":
        if ORIGIN >= 0:
            arr[childname] = h5file.root._f_getChild(childname)[ORIGIN-1,:]
        elif DESTINATION >= 0:
            arr[childname] = h5file.root._f_getChild(childname)[:,DESTINATION-1]
    elif MODE=="from":
        arr[childname] = numpy.sum(h5file.root._f_getChild(childname), axis=0)
    elif MODE=="to":
        arr[childname] = numpy.sum(h5file.root._f_getChild(childname), axis=1)

# print arr
children = arr.keys()
children.sort()
# print children

print "Writing " + outfilename
outdbf = dbf.Dbf(outfilename, new=True)
outdbf.addField((colname,    "N", 5, 0))
for childname in children:
    # because ArcGIS HATES this
    fieldname = childname
    if fieldname[0].isdigit(): fieldname = "F_" + fieldname
    fieldname = fieldname[0:8]
    outdbf.addField((fieldname,  "N", 12,2))

firstchild = children[0]

for rownum in range(len(arr[firstchild])):
    rec = outdbf.newRecord()
    rec[colname] = rownum+1
    
    for childidx in range(len(children)):
        fieldname = children[childidx]
        if fieldname[0].isdigit(): fieldname = "F_" + fieldname
        fieldname = fieldname[0:8]        
           
        rec[fieldname]  = arr[children[childidx]][rownum]
    rec.store()
    
outdbf.flush()
outdbf.close()
h5file.close()