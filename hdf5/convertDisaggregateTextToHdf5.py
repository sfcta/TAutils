#!/usr/bin/env python

""" converts CHAMP4 disagregate trip or tour list data to HDF5 tables """

import getopt
import sys
import os
from champUtil import Trip, recordKeys
from time import time,localtime,strftime
from tables import openFile,Filters

__author__ = "Lisa Zorn, San Francisco County Transportation Authority"
__license__= "GPL"
__email__  = "lisa@sfcta.org"
__date__   = "Jan 22, 2010" 

USAGE = """
usage: python convertDisaggregateTextToHdf5.py -t [TYPE] [inputfile.txt] [outputfile.H5]

 Converts the input disaggregate text file to the hdf5 version.
 
"""

#### Parse options and arguments
type = ""
optlist,args = getopt.getopt(sys.argv[1:],'t:')
for o,a in optlist:
    if o=="-t":
        type = a

if type != "TRIPMC" and type != "TOURDC" and type != "TOURMC":
    print USAGE
    print "Supported types include TRIPMC, TOURDC and TOURMC currently."
    exit(1)

if (len(args) != 2):
    print USAGE
    exit(1)

infilename    = args[0]
print "INFILE = " + infilename
outfilename = args[1] 
print "OUTFILE = " + outfilename

infile       = open(infilename, 'rU') # The U is for universal newline support
# It is necessary because of an issue I was running into where a number of lines (apparently random)
# would read in without the newline and cause the table to become corrupted
# See here: http://bugs.python.org/issue1142
infilesize   = os.path.getsize(infilename)
estrecs      = int(infilesize/195)
starttime    = time()
print "Reading input file " + infilename + "; size = " + str(infilesize)
print "Estimating " + str(estrecs) + " records"

outfile      = openFile(outfilename, mode="w")
compfilt     = Filters(complevel=1,complib='zlib')
table        = outfile.createTable("/", "records",Trip,type + " records", filters=compfilt, expectedrows=estrecs)
print "Creating output file " + outfilename

print strftime("%x %X", localtime(starttime)) + " Started" 
sys.stdout.flush()

trip         = table.row


# These keys aren't in the TRIPMC.OUT1 file
if type == "TOURDC":
    recordKeys[34:] = []
    print recordKeys

if type=="TOURMC":
    recordKeys[65:] = []
    recordKeys.remove("mcLogSumW0")
    recordKeys.remove("mcLogSumW1")
    recordKeys.remove("mcLogSumW2")
    recordKeys.remove("mcLogSumW3")
    
    recordKeys.remove("mcLogSumW")
    recordKeys.remove("dcLogSumPk")
    recordKeys.remove("dcLogSumOp")
    recordKeys.remove("dcLogSumAtWk")
    
if type == "TRIPMC":
    recordKeys.remove("mcLogSumW0")
    recordKeys.remove("mcLogSumW1")
    recordKeys.remove("mcLogSumW2")
    recordKeys.remove("mcLogSumW3")
    recordKeys.remove("mcLogSumW")
    recordKeys.remove("dcLogSumPk")
    recordKeys.remove("dcLogSumOp")
    recordKeys.remove("dcLogSumAtWk")
    recordKeys.remove("stopBefTime1")
    recordKeys.remove("stopBefTime2")
    recordKeys.remove("stopBefTime3")
    recordKeys.remove("stopBefTime4")
    recordKeys.remove("stopAftTime1")
    recordKeys.remove("stopAftTime2")
    recordKeys.remove("stopAftTime3")
    recordKeys.remove("stopAftTime4")
    recordKeys.remove("autoExpUtility")
    recordKeys.remove("walkTransitAvailable")
    recordKeys.remove("walkTransitProb")
    recordKeys.remove("driveTransitOnly")
    recordKeys.remove("driveTransitOnlyProb")
    recordKeys.remove("stopb1")
    recordKeys.remove("stopb2")
    recordKeys.remove("stopb3")
    recordKeys.remove("stopb4")          
    recordKeys.remove("stopa1")
    recordKeys.remove("stopa2")
    recordKeys.remove("stopa3")    
    recordKeys.remove("stopa4")
    recordKeys.remove("prefTripTod")
    recordKeys.remove("tripTod")

linesread    = 0
for line in infile:
    
    tokens     = line.split(' ')
    while '' in tokens: tokens.remove('')
    tokenIdx= 0

    for key in recordKeys:
        try:
            trip[key] = int(tokens[tokenIdx])
            # if key=="mSegDir" and trip[key] > 2:
            #    print "PROBLEM: invalid mSegDir!"
        except TypeError, (strerror):
            print "Type error: %s for key [%s] val [%s] linesread=%d" % (strerror, key, tokens[tokenIdx], linesread)
        except IndexError, (strerror):
            print "Index error %s for key [%s] or index [%d] linesread=%d" % (strerror, key, tokenIdx, linesread)
        except ValueError:
            # It's either an int or a float... Int failed so try float
            try:
                trip[key] = float(tokens[tokenIdx])
            except ValueError:
                print "Double value error for key [%s] index [%d]" % (key, tokenIdx)
                exit(1)

        # if linesread== 0: print key + " => " + tokens[tokenIdx] + " = " + str(trip[key])

        tokenIdx     += 1
    trip.append()
    # print trip

    linesread += 1

    if (linesread % 100000 == 0):
        table.flush()
        print strftime("%x %X", localtime()) + "%10d lines read" % (linesread)
        sys.stdout.flush()

infile.close()
outfile.close()

endtime        = time()
print "%10d lines read" % (linesread)
print "Completed at " + strftime("%x %X", localtime(endtime)) + "; took " + str((endtime-starttime)/60.0) + " mins"
