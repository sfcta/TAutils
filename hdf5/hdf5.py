#!/usr/bin/env python

""" Batch converts cube matrix files to HDF5 """

import subprocess,os, types, warnings
import tables
import numpy

warnings.filterwarnings("ignore", category=tables.NaturalNameWarning) # Pytables doesn't like our table numbering scheme
MAT2H5_BIN = "Y:\\champ\util\bin\\mat2h5.exe"

__author__ = "Elizabeth Sall and Lisa Zorn, San Francisco County Transportation Authority"
__license__= "GPL"
__email__  = "elizabeth@sfcta.org"
__date__   = "2008-07-07"

def h5mat(convertFile):
    """ calls the executable that changes between .MAT and .h5 files
    """
    subprocess.call([MAT2H5_BIN,convertFile])

def convertSet(fileList):
    """ calls the executable that changes between .MAT and .h5 files
    for a set of file names
    """
    for file in fileList:
        print "converting %s" % (file)
        h5mat(file)

def convertTransit(path,tod):
    """converts all transit skim files for a numeric time period
    """
    timePeriods = {1:'EA', 2:'AM', 3:'MD', 4:'PM', 5:'EV'}
    tlist=['WLW','WMW','WPW','WBW','APW','ABW','WPA','WBA']
    convlist = []
    for item in tlist:
        convlist.append(os.path.join(path,"TRN"+item+timePeriods[tod]+".MAT"))
    convertSet(convlist)

def convertHwy(path,tod):
    """converts  hwyskim file for a numeric time period
    """
    timePeriods = {1:'EA', 2:'AM', 3:'MD', 4:'PM', 5:'EV'}
    item = os.path.join(path,"HWYALL"+timePeriods[tod]+".MAT")
    h5mat (item)

class H5Matrix(dict):
    """H5Matrix mimics a TP+ matrix file"""

    @classmethod
    def open(self, fname):
        """ Open an existing H5Matrix file for reading."""
        h5 = self()

        h5.h5file = tables.openFile(fname, mode='r')
        h5.zones = int(h5.h5file.getNodeAttr('/','zones')[0])
        h5.matrices = int(h5.h5file.getNodeAttr('/','tables')[0])

        h5.populate_tables()

        return h5

    @classmethod
    def create(self, fname, zones=0, matrices=0, tnames=None, template=None):
        """ Create an H5 file for storing TP+ style matrices
        """
        h5 = self()

        h5.h5file = tables.openFile(fname, mode='w')
        h5.zones = zones
        h5.matrices = matrices
        if matrices == 0 and len(tnames) > 0:
            h5.matrices = len(tnames)

        # Create attributes that are consistent with input file
        h5.h5file.setNodeAttr('/','zones', numpy.array([zones], numpy.int32))
        h5.h5file.setNodeAttr('/','tables', numpy.array([matrices], numpy.int32))

        if (tnames or matrices): h5.create_tables(tnames or matrices)

        return h5


    def populate_tables(self):
        for t in range(1,self.matrices+1):
            node = self.h5file.getNode('/','%s' % (t))
            self[t] = node


    def create_tables(self, matrices):
        """ Create new set of tables in this H5Matrix.
            Pass an integer to create that number of new blank tables without table names.
            Pass a list of names to create that many tables with named attributes.
        """

        atom = tables.Float64Atom()
        shape = (self.zones, self.zones)
        filters = tables.Filters(complevel=7, complib='zlib')

        if type(matrices) == types.IntType:
            # Pass an integer to create that number of new blank tables without table names.
            for t in range(1, 1+matrices):
                tOut = self.h5file.createCArray(self.h5file.root, '%s' % t, atom, shape, filters=filters)
                tOut.attrs.zones =  numpy.array([self.zones], numpy.int32)
                tOut.attrs.name = '%s' % t
                self[t] = tOut
        else:
            # Pass a list of names to create that many tables with named attributes.
            for t in range(1, 1+len(matrices)):
                tOut = self.h5file.createCArray(self.h5file.root, '%s'% t, atom, shape, filters=filters)
                tOut.attrs.zones =  numpy.array([self.zones], numpy.int32)
                tOut.attrs.name = matrices[t-1]
                self[t] = tOut

    def close(self):
        for t in self:
            self[t].flush()
        self.h5file.close()
