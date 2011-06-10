#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os,subprocess,shutil

__author__ = "Elizabeth Sall, San Francisco County Transportation Authority"
__license__= "GPL"
__email__  = "elizabeth@sfcta.org"
__date__   = "Mar 30 10:57:39 2011"

HWYEXPORTSCRIPT = r"exportHwyFromPy.s"
NODEFILE=r"c:\Temp\node.csv"
LINKFILE=r"c:\Temp\link.csv"

SFBOUNDBOX = {"NW":(5976893,2125313),"NE":(6027508,2136941),"SW":(5977234,2085983),"SE":(6027850,2084957) }

def nodeInBoundBox((x,y),box=SFBOUNDBOX,verbose=False):
    if verbose:
        print "BOX:",box
        print "NODE:",x,y
    if x < box['NE'][0] and y < box['NE'][1]:
        if verbose: print "NE Bound OK"
        if x > box['NW'][0] and y < box['NW'][1]:
            if verbose: print "NW Bound OK"
            if x < box['SE'][0] and y > box['SE'][1]:
                if verbose: print "SE Bound OK"
                if x > box['SW'][0] and y > box['SW'][1]:
                    if verbose: print "SW Bound OK"
                    return True
    return False



def cubeNet2CSV(file,extra_vars=["DISTANCE"],script   = HWYEXPORTSCRIPT ):
    """export cube network to DBF files in C:\temp directory
    
    options:
        -extra_vars: list extra variables to export
    """
    
    #set environment variables
    os.environ['CUBENET']=file

    if len(extra_vars)>0:

        extra_vars_str=","
        extra_vars_str+=extra_vars_str.join(extra_vars)
        os.environ['XTRAVAR']=extra_vars_str
    else: os.environ['XTRAVAR']=''
    
    print "EXPORTING CUBE NETWORK: ",os.environ['CUBENET']
    print "...adding variables: %s" % (extra_vars_str if len(extra_vars)>0 else "None")
    print "...running script: \n      %s" % (script)
    
    filedir = os.path.dirname(os.path.abspath(file))
    cmd = "runtpp " + script
    proc = subprocess.Popen( cmd, cwd = filedir, stdout=subprocess.PIPE, stderr=subprocess.PIPE )
    for line in proc.stdout:
        line = line.strip('\r\n')
        print "stdout: " + line

    retStderr = []
    for line in proc.stderr:
        line = line.strip('\r\n')
        print "stderr: " + line
    retcode  = proc.wait()
    
    if retcode ==2:
        raise

    print "Received %d from [%s]" % (retcode, cmd)
    print "Exported cube network:\n  from: %s \n  to TEMP\\ node.csv and link.csv" % (file)
    shutil.copyfile(NODEFILE,os.path.join(".",'node.csv'))
    shutil.copyfile(LINKFILE,os.path.join(".",'link.csv'))

def import_nodes_from_csv(extra_vars=[],networkFile="finalTMP_TP2_pm.tmp"):
    
    """imports cube network from network file and returns a dictionary of node XYs by Node Number
    """
    if not os.path.exists('node.csv'):
        cubeNet2CSV(file=networkFile)
        
    # Open node file and add nodes
    nodes={}
    F=open('node.csv',mode='r')
    for rec in F:
        r=rec.strip().split(',')
        n=int(r[0])
        x=float(r[1])
        y=float(r[2])
        nodes[n]=(x,y)
    F.close()
    return nodes
    
def nodes_zones_links_connectors_fromCSV(extra_vars=[],networkFile="finalTMP_TP2_pm.tmp"):
    
    """imports cube network from network file and returns a list of each
    """
    if not os.path.exists('node.csv') and os.path.exists('link.csv'):
        cubeNet2CSV(file=networkFile,extra_vars=extra_vars)

    MAXZONE=2475
    zones=[]
    nodes=[]
    F=open('node.csv',mode='r')
    for rec in F:
        r=rec.strip().split(',')
        n=int(r[0])
        x=float(r[1])
        y=float(r[2])
        if n<=MAXZONE:
            zones.append({"N":n,"x":x,"y":y})
        else:
            nodes.append({"N":n,"x":x,"y":y})
    F.close()
    
    links=[]
    connectors=[]
    F=open('link.csv',mode='r')
    for rec in F:
        r = rec.strip().split(',')
        link={'A':int(r[0]),'B':int(r[1])}
        for v in extra_vars:
            link[v] = r[extra_vars.index(v)+2]
        if a<=MAXZONE or b<=MAXZONE:
            connectors.append(link)
        else:
            links.append(link)

    F.close()
    return nodes,zones,links,connectors
            
