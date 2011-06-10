from simpleparse.common import numbers, strings, comments
from simpleparse import generator
from simpleparse.parser import Parser
from simpleparse.dispatchprocessor import *
from types import *

from mx.TextTools import TextTools
import copy, inspect, logging, os, re, pdb, copy, subprocess, sys, tempfile, time, xlrd

class NetworkException(Exception): pass

# for all the logging in this file
WranglerLogger = logging.getLogger("WranglerLogger")

WRANGLER_FILE_SUFFICES = [ "lin", "link", "pnr", "zac", "access", "xfer" ]

# PARSER DEFINITION ------------------------------------------------------------------------------
# NOTE: even though XYSPEED and TIMEFAC are node attributes here, I'm not sure that's really ok --
# Cube documentation implies TF and XYSPD are node attributes...
transit_file_def=r'''
transit_file      := ( accessli / line / link / pnr / zac )+, smcw*, whitespace*

line              := whitespace?, smcw?, c"LINE", whitespace, lin_attr*, lin_node*, whitespace?
lin_attr          := ( lin_attr_name, whitespace?, "=", whitespace?, attr_value, whitespace?,
                       comma, whitespace?, semicolon_comment* )
lin_nodeattr      := ( lin_nodeattr_name, whitespace?, "=", whitespace?, attr_value, whitespace?, comma?, whitespace?, semicolon_comment* )
lin_attr_name     := c"allstops" / c"color" / (c"freq",'[',[1-5],']') / c"mode" / c"name" / c"oneway" / c"owner" / c"runtime" / c"timefac" / c"xyspeed"
lin_nodeattr_name := c"access_c" / c"access" / c"delay" /  c"xyspeed" / c"timefac"
lin_node          := lin_nodestart?, whitespace?, nodenum, spaces*, comma?, spaces*, semicolon_comment?, whitespace?, lin_nodeattr*
lin_nodestart     := (whitespace?, "N", whitespace?, "=")

link              := whitespace?, smcw?, c"LINK", whitespace, link_attr*, whitespace?, semicolon_comment*
link_attr         := (( (link_attr_name, whitespace?, "=", whitespace?,  attr_value) /
                        (word_nodes, whitespace?, "=", whitespace?, nodepair) /
                        (word_modes, whitespace?, "=", whitespace?, numseq) ),
                      whitespace?, comma?, whitespace?)
link_attr_name    := c"dist" / c"speed" / c"time" / c"oneway"

pnr               := whitespace?, smcw?, c"PNR", whitespace, pnr_attr*, whitespace?
pnr_attr          := (( (pnr_attr_name, whitespace?, "=", whitespace?, attr_value) /
                        (word_node, whitespace?, "=", whitespace?, ( nodepair / nodenum )) /
                        (word_zones, whitespace?, "=", whitespace?, numseq )),
                       whitespace?, comma?, whitespace?, semicolon_comment*)
pnr_attr_name     := c"time" / c"maxtime" / c"distfac" / c"cost"

zac               := whitespace?, smcw?, c"ZONEACCESS", whitespace, zac_attr*, whitespace?, semicolon_comment*
zac_attr          := (( (c"link", whitespace?, "=", whitespace?, nodepair) /
                        (zac_attr_name, whitespace?, "=", whitespace?, attr_value) ),
                      whitespace?, comma?, whitespace?)
zac_attr_name     := c"mode"

accessli             := whitespace?, smcw?, nodenumA, spaces?, nodenumB, spaces?, (float/int)?, spaces?, semicolon_comment?

word_nodes        := c"nodes"
word_node         := c"node"
word_modes        := c"modes"
word_zones        := c"zones"
numseq            := int, (spaces?, ("-" / ","), spaces?, int)*
nodepair          := nodenum, spaces?, ("-" / ","), spaces?, nodenum
nodenumA          := nodenum
nodenumB          := nodenum
nodenum           := int
attr_value        := alphanums / string_single_quote / string_double_quote
alphanums         := [a-zA-Z0-9\.]+
<comma>           := [,]
<whitespace>      := [ \t\r\n]+
<spaces>          := [ \t]+
smcw              := whitespace?, (semicolon_comment / c_comment, whitespace?)+
'''
nodepair_pattern = re.compile('(\d+)[-,\s]*(\d+)')

def setupLogging(infoLogFilename, debugLogFilename, logToConsole=True):
    """ Sets up the logger.  The infoLog is terse, just gives the bare minimum of details
        so the network composition will be clear later.
        The debuglog is very noisy, for debugging.
        Spews it all out to console too, if logToConsole is true.
    """
    # create a logger
    WranglerLogger.setLevel(logging.DEBUG)

    infologhandler = logging.StreamHandler(open(infoLogFilename, 'w'))
    infologhandler.setLevel(logging.INFO)
    infologhandler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s','%Y-%m-%d %H:%M'))
    WranglerLogger.addHandler(infologhandler)

    debugloghandler = logging.StreamHandler(open(debugLogFilename,'w'))
    debugloghandler.setLevel(logging.DEBUG)
    debugloghandler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s', '%Y-%m-%d %H:%M'))
    WranglerLogger.addHandler(debugloghandler)

    if logToConsole:
        consolehandler = logging.StreamHandler()
        consolehandler.setLevel(logging.DEBUG)
        consolehandler.setFormatter(logging.Formatter('%(name)-12s: %(levelname)-8s %(message)s'))
        WranglerLogger.addHandler(consolehandler)


# Data structures -----------------------------------------------------------

class TransitLine(object):
    """Transit route. Behaves like a dictionary of attributes.
       'n' is list of Node objects (see Wrangler.Node)
       All other attributes are stored as a dictionary (e.g. thisroute['MODE']='5')
    """
    def __init__(self, name=None, template=None):
        self.attr = {}
        self.n = []
        self.comment = None

        self.name = name
        if name and name.find('"')==0:
            self.name = name[1:-1]  # Strip leading/trailing dbl-quotes

        if template:
            self._applyTemplate(template)

    def setFreqs(self, freqs):
        '''Set all five headways (AM,MD,PM,EV,EA)'''
        if not len(freqs)==5: raise NetworkException('Must specify all 5 frequencies')
        self.attr['FREQ[1]'] = freqs[0]
        self.attr['FREQ[2]'] = freqs[1]
        self.attr['FREQ[3]'] = freqs[2]
        self.attr['FREQ[4]'] = freqs[3]
        self.attr['FREQ[5]'] = freqs[4]

    def getFreqs(self):
        return [self.attr['FREQ[1]'],
                self.attr['FREQ[2]'],
                self.attr['FREQ[3]'],
                self.attr['FREQ[4]'],
                self.attr['FREQ[5]']]


    def hasNode(self,nodeNumber):
        for node in self.n:
            if abs(int(node.num)) == abs(nodeNumber):
                return True
        return False

    def hasLink(self,nodeA,nodeB):
        nodeNumPrev = -1
        for node in self.n:
            nodeNum = abs(int(node.num))
            if nodeNum == abs(nodeB) and nodeNumPrev == abs(nodeA):
                return True
            nodeNumPrev = nodeNum
        return False

    def hasSegment(self,nodeA,nodeB):
        hasA=False
        for node in self.n:
            nodeNum = abs(int(node.num))
            if nodeNum == abs(nodeA):
                hasA=True
            elif nodeNum == abs(nodeB):
                if hasA: return True
                else: return False
        return False

    def numStops(self):
        numStops = 0
        for node in self.n:
            if node.isStop(): numStops += 1
        return numStops

    def setNodes(self, newnodelist):
        for i in range(len(newnodelist)):
            if isinstance(newnodelist[i],int): newnodelist[i] = Node(newnodelist[i])
        self.n = newnodelist

    def insertNode(self,refNodeNum,newNodeNum,stop=False,after=True):
        newNode = Node(newNodeNum)
        if stop==True: newNode.setStop(True)
        for nodeIdx in range(len(self.n)):
            currentNodeNum = abs(int(self.n[nodeIdx].num))
            if currentNodeNum == abs(refNodeNum):
                if after==True:
                    self.n.insert(nodeIdx+1,newNode)
                    WranglerLogger.DEBUG("In line %s: inserted node %s after node %s" % (self.name,newNode.num,str(refNodeNum)))
                else:
                    self.n.insert(nodeIdx,newNode)
                    WranglerLogger.DEBUG("In line %s: inserted node %s before node %s" % (self.name,newNode.num,str(refNodeNum)))

    def splitLink(self,nodeA,nodeB,newNodeNum,stop=False):
        """checks to see if the link exists in the line and then inserts the
        new node in between node A and nodeB
        """
        if not self.hasLink(nodeA,nodeB):
            raise NetworkException( "Line %s Doesn't have that link - so can't split it" % (self.name))
        newNode = Node(newNodeNum)
        if stop==True: newNode.setStop(True)

        nodeNumPrev = -1
        for nodeIdx in range(len(self.n)):
            currentNodeNum = abs(int(self.n[nodeIdx].num))
            if currentNodeNum == abs(nodeB) and nodeNumPrev == abs(nodeA):
                self.n.insert(nodeIdx,newNode)
                WranglerLogger.debug("In line %s: inserted node %s between node %s and node %s" % (self.name,newNode.num,str(nodeA),str(nodeB)))
            nodeNumPrev = currentNodeNum

    def extendLine(self, oldnode, newsection, beginning=True):
        """ Replace nodes up through oldnode with newsection.
            Newsection can be an array of numbers; this will make nodes.
            If beginning, does this at the beginning; otherwise at the end.
        """
        ind = self.n.index(oldnode)
        # make the new nodes
        for i in range(len(newsection)):
            if isinstance(newsection[i],int): newsection[i] = Node(newsection[i])

        if beginning:
            # print self.n[:ind+1]
            self.n[:ind+1] = newsection
        else:
            self.n[ind:] = newsection

    def replaceSegment(self, node1, node2, newsection):
        """ Replaces the section from node1 to node2 with the newsection
            Newsection can be an array of numbers; this will make nodes.
        """
        WranglerLogger.debug("replacing segment",node1,node2)
        try:
            ind1 = self.n.index(node1)
        except:
            ind1 = self.n.index(-node1)

        try:
            ind2 = self.n.index(node2)
        except:
            ind2 = self.n.index(-node2)

        attr1 = self.n[ind1].attr
        attr2 = self.n[ind2].attr

        # make the new nodes
        for i in range(len(newsection)):
            if isinstance(newsection[i],int): newsection[i] = Node(newsection[i])
        # xfer the attributes
        newsection[0].attr=attr1
        newsection[-1].attr=attr2

        self.n[ind1:ind2+1] = newsection

    def setStop(self, nodenum, isStop=True):
        i = self.n.index(nodenum)
        self.n[i].setStop(isStop)

    def addStopsToSet(self, set):
        for nodeIdx in range(len(self.n)):
            if self.n[nodeIdx].isStop():
                set.add(int(self.n[nodeIdx].num))

    def _applyTemplate(self, template):
        '''Copy all attributes (including nodes) from an existing transit line to this line'''
        self.attr = copy.deepcopy(template.attr)
        self.n = copy.deepcopy(template.n)
        self.comment = template.comment

    # Dictionary methods
    def __getitem__(self,key): return self.attr[key]
    def __setitem__(self,key,value): self.attr[key]=value
    def __cmp__(self,other): return cmp(self.name,other)

    # String representation: for outputting to line-file
    def __repr__(self):
        s = '\nLINE NAME=\"%s\",\n    ' % (self.name,)
        if self.comment: s+= self.comment

        # Line attributes
        s += ",\n    ".join(["%s=%s" % (k,v) for k,v in sorted(self.attr.items())])

        # Node list
        s += ",\n"
        prevAttr = True
        for nodeIdx in range(len(self.n)):
            s += self.n[nodeIdx].lineFileRepr(prependNEquals=prevAttr, lastNode=(nodeIdx==len(self.n)-1))
            prevAttr = len(self.n[nodeIdx].attr)>0

        return s

    def __str__(self):
        s = 'Line name \"%s\" freqs=%s' % (self.name, str(self.getFreqs()))
        return s

class Node(object):
    """Transit node. This can only exist as part of a transit line that it belongs to.
       'num' is the string representation of the node number with stop-status (e.g. '-24322')
       'stop' is True or False
        All other attributes stored as a dictionary (e.g. thisnode["DELAY"]="0.5")
    """

    def __init__(self, n):
        self.attr = {}
        if isinstance(n,int):
            self.num = str(n)
        else:
            self.num = n
        self.stop=(self.num.find('-')<0 and True or False)
        self.comment = None

    def setStop(self, isStop=True):
        n = abs(int(self.num))
        self.stop = isStop

        if not self.stop:
            n = -n

        self.num = str(n)

    def isStop(self):
        if int(self.num)>0: return True
        return False

    # String representation for line file
    def lineFileRepr(self, prependNEquals=False, lastNode=False):
        if prependNEquals: s=" N="
        else:              s="   "

        # node number
        if self.stop: s+= " "
        s += self.num
        # attributes
        for k,v in sorted(self.attr.items()):
            s +=", %s=%s" % (k,v)
        # comma
        if not lastNode: s+= ","
        # comment
        if self.comment: s+=' %s' % (self.comment,)
        # eol
        s += "\n"
        return s

    # Dictionary methods
    def __getitem__(self,key): return self.attr[key]
    def __setitem__(self,key,value): self.attr[key]=value
    def __cmp__(self,other): return cmp(int(self.num),other)

class TransitLink(dict):
    """ Transit support Link.
       'nodes' property is the node-pair for this link (e.g. 24133,34133)
       'comment' is any end-of-line comment for this link
                 (must include the leading semicolon)
        All other attributes are stored in a dictionary (e.g. thislink['MODE']='1,2')
    """
    def __init__(self):
        dict.__init__(self)
        self.id=''
        self.comment=''

    def __repr__(self):
        s = "LINK nodes=%s, " % (self.id,)

        # Deal w/all link attributes
        fields = ['%s=%s' % (k,v) for k,v in self.items()]
        s += ", ".join(fields)
        s += self.comment

        return s

    def addNodesToSet(self, set):
        """ Add integer versions of the nodes in this like to the given set
        """
        m = re.match(nodepair_pattern, self.id)
        set.add(int(m.group(1)))
        set.add(int(m.group(2)))

class PNRLink(dict):
    """ PNR Support Link.
       'node' property is the node-pair for this link (e.g. 24133-34133)
       'comment' is any end-of-line comment for this link including the leading semicolon
        All other attributes are stored in a dictionary (e.g. thislink['MODE']='1,2')
    """
    def __init__(self):
        dict.__init__(self)
        self.id=''
        self.comment=''

    def __repr__(self):
        s = "PNR NODE=%s " % (self.id,)

        # Deal w/all link attributes
        fields = ['%s=%s' % (k,v) for k,v in self.items()]

        s += " ".join(fields)
        s += self.comment

        return s

class ZACLink(dict):
    """ ZAC support Link.
       'link' property is the node-pair for this link (e.g. 24133-34133)
       'comment' is any end-of-line comment for this link
                 (must include the leading semicolon)
        All other attributes are stored in a dictionary (e.g. thislink['MODE']='17')
    """
    def __init__(self):
        dict.__init__(self)
        self.id=''
        self.comment=''

    def __repr__(self):
        s = "ZONEACCESS link=%s " % (self.id,)

        # Deal w/all link attributes
        fields = ['%s=%s' % (k,v) for k,v in self.items()]

        s += " ".join(fields)
        s += self.comment

        return s

class Linki(dict):
    """ Linki Link.  Has A-node, B-node, possibly a comment and a distance.
    """
    def __init__(self):
        dict.__init__(self)
        self.A=''
        self.B=''
        self.comment=''
        self.distance=''

    def __repr__(self):
        s = "%8s %8s" % (self.A, self.B)
        if self.distance != '':
            s += " %8s" % self.distance
        if self.comment != '':
            s += " %s" % (self.comment)
        return s

# ------------------------------------------------------------------------------
# End of Data Structures
# ------------------------------------------------------------------------------

class TransitFileProcessor(DispatchProcessor):
    """ Class to process transit files
    """
    def __init__(self, verbosity=1):
        self.verbosity=verbosity
        self.lines = []
        self.links = []
        self.pnrs   = []
        self.zacs   = []
        self.accesslis = []
        self.xferlis   = []
        self.liType    = ''

    def crackTags(self, leaf, buffer):
        tag = leaf[0]
        text = buffer[leaf[1]:leaf[2]]
        subtags = leaf[3]

        b = []

        if subtags:
            for leaf in subtags:
                b.append(self.crackTags(leaf, buffer))

        return (tag,text,b)

    def line(self, (tag,start,stop,subtags), buffer):
        # this is the whole line
        if self.verbosity>=1:
            print tag, start, stop

        # Append list items for this line
        for leaf in subtags:
            xxx = self.crackTags(leaf,buffer)
            self.lines.append(xxx)

        if self.verbosity==2:
            # lines are composed of smcw (semicolon-comment / whitespace), line_attr and lin_node
            for linepart in subtags:
                print "  ",linepart[0], " -> [ ",
                for partpart in linepart[3]:
                    print partpart[0], "(", buffer[partpart[1]:partpart[2]],")",
                print " ]"

    def link(self, (tag,start,stop,subtags), buffer):
        # this is the whole link
        if self.verbosity>=1:
            print tag, start, stop

        # Append list items for this link
        for leaf in subtags:
            xxx = self.crackTags(leaf,buffer)
            self.links.append(xxx)

        if self.verbosity==2:
            # links are composed of smcw and link_attr
            for linkpart in subtags:
                print "  ",linkpart[0], " -> [ ",
                for partpart in linkpart[3]:
                    print partpart[0], "(", buffer[partpart[1]:partpart[2]], ")",
                print " ]"

    def pnr(self, (tag,start,stop,subtags), buffer):
        if self.verbosity>=1:
            print tag, start, stop

        # Append list items for this link
        for leaf in subtags:
            xxx = self.crackTags(leaf,buffer)
            self.pnrs.append(xxx)

        if self.verbosity==2:
            # pnrs are composed of smcw and pnr_attr
            for pnrpart in subtags:
                print " ",pnrpart[0], " -> [ ",
                for partpart in pnrpart[3]:
                    print partpart[0], "(", buffer[partpart[1]:partpart[2]], ")",
                print " ]"

    def zac(self, (tag,start,stop,subtags), buffer):
        if self.verbosity>=1:
            print tag, start, stop

        if self.verbosity==2:
            # zacs are composed of smcw and zac_attr
            for zacpart in subtags:
                print " ",zacpart[0], " -> [ ",
                for partpart in zacpart[3]:
                    print partpart[0], "(", buffer[partpart[1]:partpart[2]], ")",
                print " ]"

        # Append list items for this link
        for leaf in subtags:
            xxx = self.crackTags(leaf,buffer)
            self.zacs.append(xxx)

    def smcw(self, (tag,start,stop,subtags), buffer):
        """ Semicolon comment whitespace
        """
        if self.verbosity>=1:
            print tag, start, stop

    def accessli(self, (tag,start,stop,subtags), buffer):
        if self.verbosity>=1:
            print tag, start, stop

        for leaf in subtags:
            xxx = self.crackTags(leaf,buffer)
            if self.liType=="access":
                self.accesslis.append(xxx)
            elif self.liType=="xfer":
                self.xferlis.append(xxx)
            else:
                raise NetworkException("Found access or xfer link without classification")

class TransitParser(Parser):

    def __init__(self, filedef, verbosity=1):
        Parser.__init__(self, filedef)
        self.verbosity=verbosity
        self.tfp = TransitFileProcessor(self.verbosity)

    def buildProcessor(self):
        return self.tfp

    def convertLineData(self):
        """ Convert the parsed tree of data into a usable python list of transit lines
            returns list of comments and transit line objects
        """
        rows = []
        currentRoute = None

        for line in self.tfp.lines:
            # Each line is a 3-tuple:  key, value, list-of-children.

            # Add comments as simple strings
            if line[0] == 'smcw':
                cmt = line[1].strip()
                if not cmt==';;<<Trnbuild>>;;':
                    rows.append(cmt)
                continue

            # Handle Line attributes
            if line[0] == 'lin_attr':
                key = None
                value = None
                comment = None
                # Pay attention only to the children of lin_attr elements
                kids = line[2]
                for child in kids:
                    if child[0]=='lin_attr_name': key=child[1]
                    if child[0]=='attr_value': value=child[1]
                    if child[0]=='semicolon_comment': comment=child[1].strip()

                # If this is a NAME attribute, we need to start a new TransitLine!
                if key=='NAME':
                    if currentRoute:
                        rows.append(currentRoute)
                    currentRoute = TransitLine(name=value)
                else:
                    currentRoute[key] = value  # Just store all other attributes

                # And save line comment if there is one
                if comment: currentRoute.comment = comment
                continue

            # Handle Node list
            if line[0] == "lin_node":
                # Pay attention only to the children of lin_attr elements
                kids = line[2]
                node = None
                for child in kids:
                    if child[0]=='nodenum':
                        node = Node(child[1])
                    if child[0]=='lin_nodeattr':
                        key = None
                        value = None
                        for nodechild in child[2]:
                            if nodechild[0]=='lin_nodeattr_name': key = nodechild[1]
                            if nodechild[0]=='attr_value': value = nodechild[1]
                            if nodechild[0]=='semicolon_comment': comment=nodechild[1].strip()
                        node[key] = value
                        if comment: node.comment = comment
                currentRoute.n.append(node)
                continue

            # Got something other than lin_node, lin_attr, or smcw:
            WranglerLogger.critical("** SHOULD NOT BE HERE: %s" % line[0])

        # End of tree; store final route and return
        if currentRoute: rows.append(currentRoute)
        return rows

    def convertLinkData(self):
        """ Convert the parsed tree of data into a usable python list of transit lines
            returns list of comments and transit line objects
        """
        rows = []
        currentLink = None
        key = None
        value = None
        comment = None

        for link in self.tfp.links:
            # Each link is a 3-tuple:  key, value, list-of-children.

            # Add comments as simple strings:
            if link[0] in ('smcw','semicolon_comment'):
                if currentLink:
                    currentLink.comment = " "+link[1].strip()  # Link comment
                    rows.append(currentLink)
                    currentLink = None
                else:
                    rows.append(link[1].strip())  # Line comment
                continue

            # Link records
            if link[0] == 'link_attr':
                # Pay attention only to the children of lin_attr elements
                kids = link[2]
                for child in kids:
                    if child[0] in ('link_attr_name','word_nodes','word_modes'):
                        key = child[1]
                        # If this is a NAME attribute, we need to start a new TransitLink.
                        if key in ('nodes','NODES'):
                            if currentLink: rows.append(currentLink)
                            currentLink = TransitLink() # Create new dictionary for this transit support link

                    if child[0]=='nodepair':
                        currentLink.id = child[1]

                    if child[0] in ('attr_value','numseq'):
                        currentLink[key] = child[1]
                continue

            # Got something unexpected:
            WranglerLogger.critical("** SHOULD NOT BE HERE: %s" % link[0])

        # Save last link too
        if currentLink: rows.append(currentLink)
        return rows

    def convertPNRData(self):
        """ Convert the parsed tree of data into a usable python list of PNR objects
            returns list of strings and PNR objects
        """
        rows = []
        currentPNR = None
        key = None
        value = None

        for pnr in self.tfp.pnrs:
            # Each pnr is a 3-tuple:  key, value, list-of-children.
            # Add comments as simple strings

            # Textline Comments
            if pnr[0] =='smcw':
                # Line comment; thus existing PNR must be finished.
                if currentPNR:
                    rows.append(currentPNR)
                    currentPNR = None

                rows.append(pnr[1].strip())  # Append line-comment
                continue

            # PNR records
            if pnr[0] == 'pnr_attr':
                # Pay attention only to the children of attr elements
                kids = pnr[2]
                for child in kids:
                    if child[0] in ('pnr_attr_name','word_node','word_zones'):
                        key = child[1]
                        # If this is a NAME attribute, we need to start a new PNR.
                        if key in ('node','NODE'):
                            if currentPNR:
                                rows.append(currentPNR)
                            currentPNR = PNRLink() # Create new dictionary for this PNR

                    if child[0]=='nodepair' or child[0]=='nodenum':
                        currentPNR.id = child[1]

                    if child[0] in ('attr_value','numseq'):
                        currentPNR[key] = child[1]

                    if child[0]=='semicolon_comment':
                        currentPNR.comment = ' '+child[1].strip()

                continue

            # Got something unexpected:
            WranglerLogger.critical("** SHOULD NOT BE HERE: %s" % pnr[0])

        # Save last link too
        if currentPNR: rows.append(currentPNR)
        return rows

    def convertZACData(self):
        """ Convert the parsed tree of data into a usable python list of ZAC objects
            returns list of strings and ZAC objects
        """
        rows = []
        currentZAC = None
        key = None
        value = None

        for zac in self.tfp.zacs:
            # Each zac is a 3-tuple:  key, value, list-of-children.
            # Add comments as simple strings

            # Textline Comments
            if zac[0] in ('smcw','semicolon_comment'):
                if currentZAC:
                    currentZAC.comment = ' '+zac[1].strip()
                    rows.append(currentZAC)
                    currentZAC = None
                else:
                    rows.append(zac[1].strip())  # Append value

                continue

            # Link records
            if zac[0] == 'zac_attr':
                # Pay attention only to the children of lin_attr elements
                kids = zac[2]
                for child in kids:
                    if child[0]=='nodepair':
                        # Save old ZAC
                        if currentZAC: rows.append(currentZAC)
                        # Start new ZAC
                        currentZAC = ZACLink() # Create new dictionary for this ZAC.
                        currentZAC.id=child[1]

                    if child[0] =='zac_attr_name':
                        key = child[1]

                    if child[0]=='attr_value':
                        currentZAC[key] = child[1]

                continue

            # Got something unexpected:
            WranglerLogger.critical("** SHOULD NOT BE HERE: %s" % zac[0])

        # Save last link too
        if currentZAC: rows.append(currentZAC)
        return rows

    def convertLinkiData(self, linktype):
        """ Convert the parsed tree of data into a usable python list of ZAC objects
            returns list of strings and ZAC objects
        """
        rows = []
        currentLinki = None
        key = None
        value = None

        linkis = []
        if linktype=="access":
            linkis=self.tfp.accesslis
        elif linktype=="xfer":
            linkis=self.tfp.xferlis
        else:
            raise NetworkException("ConvertLinkiData with invalid linktype")

        for accessli in linkis:
            # whitespace?, smcw?, nodenumA, spaces?, nodenumB, spaces?, (float/int)?, spaces?, semicolon_comment?
            if accessli[0]=='smcw':
                rows.append(accessli[1].strip())
            elif accessli[0]=='nodenumA':
                currentLinki = Linki()
                rows.append(currentLinki)
                currentLinki.A = accessli[1].strip()
            elif accessli[0]=='nodenumB':
                currentLinki.B = accessli[1].strip()
            elif accessli[0]=='float' or accessli[0]=='int':
                currentLinki.distance = accessli[1].strip()
            elif accessli[0]=='semicolon_comment':
                currentLinki.comment = accessli[1].strip()
            else:
                # Got something unexpected:
                WranglerLogger.critical("** SHOULD NOT BE HERE: %s" % accessli[0])

        return rows

class Network(object):
    """Full Cube network representation (all components)"""

    def __init__(self):
        self.lines = []
        self.links = []
        self.pnrs   = []
        self.zacs   = []
        self.accessli = []
        self.xferli   = []

    def __repr__(self):
        return "Network: %s lines, %s links, %s PNRs, %s ZACs" % (len(self.lines),len(self.links),len(self.pnrs),len(self.zacs))

    def isEmpty(self):
        """ TODO: could be smarter here and check that there are no non-comments since those
            don't really count
        """
        if (len(self.lines) == 0 and
            len(self.links) == 0 and
            len(self.pnrs) == 0 and
            len(self.zacs) == 0 and
            len(self.accessli) == 0 and
            len(self.xferli) == 0):
            return True

        return False

    def clear(self, projectstr):
        """ Clears out all network data to prep for a project apply.
            If it's already clear then this is a no-op but otherwise
            the user will be prompted (with the project string)
        """
        if self.isEmpty():
            # nothing to do!
            return

        query = "Clearing network for %s:\n" % projectstr
        query += "   %d lines, %d links, %d pnrs, %d zacs, %d accessli, %d xferli\n" % (len(self.lines),
            len(self.links), len(self.pnrs), len(self.zacs), len(self.accessli), len(self.xferli))
        query += "Is this ok? (y/n) "
        WranglerLogger.debug(query)
        response = raw_input("")

        WranglerLogger.debug("response=[%s]" % response)
        if response != "Y" and response != "y":
            exit(0)

        del self.lines[:]
        del self.links[:]
        del self.pnrs[:]
        del self.zacs[:]
        del self.accessli[:]
        del self.xferli[:]

    def validateOffstreet(self):
        print "validating off street"
        WranglerLogger.debug("Validating Off Street Transit Node Connections")

        nodeInfo = {} # lineset => { station node => { xfer node => [ walk node, pnr node ] }}
        doneNodes = set()

        # For each line
        for line in self.lines:
            if not isinstance(line,TransitLine): continue
            print "validating", line
            # The only off-road modes are BART, caltrain/ferry/rail, or LRT
            if line.attr["MODE"] != "4" and line.attr["MODE"] != "9": # and line.attr["MODE"] != "3":
                # WranglerLogger.info("-- Not mode 4 or 9, skipping check!")
                continue

            lineset = line.name[0:3]
            if lineset not in nodeInfo:
                nodeInfo[lineset] = {}

            # for each stop
            for stopIdx in range(len(line.n)):
                if not line.n[stopIdx].isStop(): continue

                stopNodeStr = line.n[stopIdx].num

                wnrNodes = set()
                pnrNodes = set()

                if stopNodeStr in nodeInfo[lineset]: continue
                nodeInfo[lineset][stopNodeStr] = {}

                #print " check if we have access to an on-street node"
                for link in self.xferli:
                    if not isinstance(link,Linki): continue
                    # This xfer links the node to the on-street network
                    if link.A == stopNodeStr:
                        nodeInfo[lineset][stopNodeStr][link.B] = ["-","-"]
                    elif link.B == stopNodeStr:
                        nodeInfo[lineset][stopNodeStr][link.A] = ["-","-"]

                #print " Check for WNR"
                for zac in self.zacs:
                    if not isinstance(zac,ZACLink): continue

                    m = re.match(nodepair_pattern, zac.id)
                    if m.group(1)==stopNodeStr: wnrNodes.add(int(m.group(2)))
                    if m.group(2)==stopNodeStr: wnrNodes.add(int(m.group(1)))

                #print "Check for PNR"
                for pnr in self.pnrs:
                    if not isinstance(pnr, PNRLink): continue
                    m = re.match(nodepair_pattern, pnr.id)
                    if m == None and pnr.id==stopNodeStr: # it's a nodenum
                        pnrNodes.add("unnumbered")
                    elif m.group(2)==stopNodeStr: pnrNodes.add(int(m.group(1)))
                    # The second node should be the stop!

                #print "Check that our access links go from an onstreet xfer to a pnr or to a wnr"
                for link in self.accessli:
                    if not isinstance(link,Linki): continue
                    try:
                        if int(link.A) in wnrNodes:
                            nodeInfo[lineset][stopNodeStr][link.B][0] = link.A
                        elif int(link.B) in wnrNodes:
                            nodeInfo[lineset][stopNodeStr][link.A][0] = link.B
                        elif int(link.A) in pnrNodes:
                            nodeInfo[lineset][stopNodeStr][link.B][1] = link.A
                        elif int(link.B) in pnrNodes:
                            nodeInfo[lineset][stopNodeStr][link.A][1] = link.B
                    except KeyError:
                        errorstr = "Invalid access link found in lineset %s stopNode %s -- Missing xfer?  A=%s B=%s, xfernodes=%s wnrNodes=%s pnrNodes=%s" % \
                            (lineset, stopNodeStr, link.A, link.B, str(nodeInfo[lineset][stopNodeStr].keys()), str(wnrNodes), str(pnrNodes))
                        WranglerLogger.warning(errorstr)
                        # raise NetworkException(errorstr)

        book = xlrd.open_workbook(r"Y:\CHAMP\util\nodes.xls")
        sh = book.sheet_by_index(0)
        nodeNames = {}
        for rx in range(0,sh.nrows): # skip header
            therow = sh.row(rx)
            nodeNames[int(therow[0].value)] = therow[1].value
        # WranglerLogger.info(str(nodeNames))

        # print it all out
        for lineset in nodeInfo.keys():

            stops = nodeInfo[lineset].keys()
            stops.sort()

            WranglerLogger.debug("--------------- Line set %s -------------------------------" % lineset)
            WranglerLogger.debug("%-30s %10s %10s %10s %10s" % ("stopname", "stop", "xfer", "wnr", "pnr"))
            for stopNodeStr in stops:
                numWnrs = 0
                stopname = "Unknown stop name"
                if int(stopNodeStr) in nodeNames: stopname = nodeNames[int(stopNodeStr)]
                for xfernode in nodeInfo[lineset][stopNodeStr].keys():
                    WranglerLogger.debug("%-30s %10s %10s %10s %10s" %
                                 (stopname, stopNodeStr, xfernode,
                                  nodeInfo[lineset][stopNodeStr][xfernode][0],
                                  nodeInfo[lineset][stopNodeStr][xfernode][1]))
                    if nodeInfo[lineset][stopNodeStr][xfernode][0] != "-": numWnrs += 1

                if numWnrs == 0:
                    errorstr = "Zero wnrNodes or onstreetxfers for stop %s!" % stopNodeStr
                    WranglerLogger.critical(errorstr)
                    # raise NetworkException(errorstr)

    def line(self, name):
        """ If a string is passed in, return the line for that name exactly.
            If a regex, return all relevant lines in a list.
            If 'all', returnall lines.
        """
        if isinstance(name,str):
            if name in self.lines:
                return self.lines[self.lines.index(name)]

        if str(type(name))=="<type '_sre.SRE_Pattern'>":
            toret = []
            for i in range(len(self.lines)):
                if isinstance(self.lines[i],str): continue
                if name.match(self.lines[i].name): toret.append(self.lines[i])
            return toret
        if name=='all':
            allLines = []
            for i in range(len(self.lines)):
                allLines.append(self.lines[i])
            return allLines
        raise NetworkException('Line name not found: %s' % (name,))

    def splitLinkInTransitLines(self,nodeA,nodeB,newNode,stop=False):
        totReplacements = 0
        allExp=re.compile(".")
        for line in self.line(allExp):
            if line.hasLink(nodeA,nodeB):
                line.splitLink(nodeA,nodeB,newNode,stop=stop)
                totReplacements+=1
        WranglerLogger.debug("Total Lines with Link %s-%s split:%d" % (nodeA,nodeB,totReplacements))

    def replaceSegmentInTransitLines(self,nodeA,nodeB,newNodes):
        totReplacements = 0
        allExp=re.compile(".")
        newSection=[nodeA]+newNodes+[nodeB]
        for line in self.line(allExp):
            if line.hasSegment(nodeA,nodeB):
                WranglerLogger.debug(line.name)
                line.replaceSegment(nodeA,nodeB,newSection)
                totReplacements+=1
        WranglerLogger.debug("Total Lines with Segment %s-%s replaced:%d" % (nodeA,nodeB,totReplacements))

    def setCombiFreqsForShortLine(self, shortLine, longLine, combFreqs):
        '''set all five headways for a short line to equal a combined
        headway including long line. i.e. set 1-California Short frequencies
        by inputing the combined frequencies of both lines.

        NOTE: make sure longLine Frequencies are set first!'''
        try:
            longLineInst=self.line(longLine)
        except:
            raise NetworkException('Unknown Route!  %s' % (longLine))
        try:
            shortLineInst=self.line(shortLine)
        except:
            raise NetworkException('Unknown Route!  %s' % (shortLine))

        [amLong,mdLong,pmLong,evLong,eaLong] = longLineInst.getFreqs()
        [amComb,mdComb,pmComb,evComb,eaComb] = combFreqs
        [amShort,mdShort,pmShort,evShort,eaShort] = [0,0,0,0,0]
        if (amLong-amComb)>0: amShort=amComb*amLong/(amLong-amComb)
        if (mdLong-mdComb)>0: mdShort=mdComb*mdLong/(mdLong-mdComb)
        if (pmLong-pmComb)>0: pmShort=pmComb*pmLong/(pmLong-pmComb)
        if (evLong-evComb)>0: evShort=evComb*evLong/(evLong-evComb)
        if (eaLong-eaComb)>0: eaShort=eaComb*eaLong/(eaLong-eaComb)
        shortLineInst.setFreqs([amShort,mdShort,pmShort,evShort,eaShort])


    def getCombinedFreq(self, names, coverage_set=False):
        """ pass a regex pattern, we'll show the combined frequency.  This
            doesn't change anything, it's just a useful tool.
        """
        lines = self.line(names)
        denom = [0,0,0,0,0]
        for l in lines:
            if coverage_set: coverage_set.discard(l.name)
            freqs = l.getFreqs()
            for t in range(5):
                if float(freqs[t])>0.0:
                    denom[t] += 1/float(freqs[t])

        combined = [0,0,0,0,0]
        for t in range(5):
            if denom[t] > 0: combined[t] = round(1/denom[t],2)
        return combined

    def verifyTransitLineFrequencies(self, frequencies, coverage=""):
        """ Utility function to verify the frequencies are as expected.
            frequencies is a dictionary of label => [ regex1, regex2, [freqlist] ]
            coverage is a regex that says we want to know if we verified the
              frequencies of all of these lines.  e.g. MUNI*
        """
        covset = set([])
        if coverage != "":
            covpattern = re.compile(coverage)
            for i in range(len(self.lines)):
                if isinstance(self.lines[i],str): continue
                if covpattern.match(self.lines[i].name): covset.add(self.lines[i].name)
            # print covset

        labels = frequencies.keys(); labels.sort()
        for label in labels:
            logstr = "Verifying %-40s: " % label

            for regexnum in [0,1]:
                frequencies[label][regexnum]=frequencies[label][regexnum].strip()
                if frequencies[label][regexnum]=="": continue
                pattern = re.compile(frequencies[label][regexnum])
                freqs = self.getCombinedFreq(pattern, coverage_set=covset)
                if freqs[0]+freqs[1]+freqs[2]+freqs[3]+freqs[4]==0:
                    logstr += "-- Found no matching lines for pattern [%s]" % (frequencies[label][regexnum])
                for timeperiod in range(5):
                    if abs(freqs[timeperiod]-frequencies[label][2][timeperiod])>0.2:
                        logstr += "-- Mismatch. Desired %s" % str(frequencies[label][2])
                        logstr += "but got ",str(freqs)
                        lines = self.line(pattern)
                        WranglerLogger.error(logstr)
                        WranglerLogger.error("Problem lines:")
                        for line in lines: WranglerLogger.error(str(line))
                        raise NetworkException("Mismatching frequency")
                logstr += "-- Match%d!" % (regexnum+1)
            WranglerLogger.debug(logstr)

        if coverage != "":
            WranglerLogger.debug("Found %d uncovered lines" % len(covset))
            for linename in covset:
                WranglerLogger.debug(self.line(linename))


    def write(self, path='.', name='transit', writeEmptyFiles=True, suppressQuery=False):
        self.validateOffstreet()

        """Write out this full transit network to disk in path specified.
        """
        if os.path.exists(path):
            if not suppressQuery:
                print "Path [%s] exists already.  Overwrite contents? (y/n) " % path
                response = raw_input("")
                WranglerLogger.debug("response = [%s]" % response)
                if response != "Y" and response != "y":
                    exit(0)
        else:
            WranglerLogger.debug("\nPath [%s] doesn't exist; creating." % path)
            os.mkdir(path)

        logstr = "Writing into %s\\%s: " % (path, name)
        WranglerLogger.info(logstr)
        print "Writing into %s\\%s: " % (path, name)
        logstr = ""
        if len(self.lines)>0 or writeEmptyFiles:
            logstr += " lines"
            f = open(os.path.join(path,name+".lin"), 'w');
            f.write(";;<<Trnbuild>>;;\n")
            for line in self.lines:
                if isinstance(line,str): f.write(line)
                else: f.write(repr(line)+"\n")
            f.close()

        if len(self.links)>0 or writeEmptyFiles:
            logstr += " links"
            f = open(os.path.join(path,name+".link"), 'w');
            for link in self.links:
                f.write(str(link)+"\n")
            f.close()

        if len(self.pnrs)>0 or writeEmptyFiles:
            logstr += " pnr"
            f = open(os.path.join(path,name+".pnr"), 'w');
            for pnr in self.pnrs:
                f.write(str(pnr)+"\n")
            f.close()

        if len(self.zacs)>0 or writeEmptyFiles:
            logstr += " zac"
            f = open(os.path.join(path,name+".zac"), 'w');
            for zac in self.zacs:
                f.write(str(zac)+"\n")
            f.close()

        if len(self.accessli)>0 or writeEmptyFiles:
            logstr += " access"
            f = open(os.path.join(path,name+".access"), 'w');
            for accessli in self.accessli:
                f.write(str(accessli)+"\n")
            f.close()

        if len(self.xferli)>0 or writeEmptyFiles:
            logstr += " xfer"
            f = open(os.path.join(path,name+".xfer"), 'w');
            for xferli in self.xferli:
                f.write(str(xferli)+"\n")
            f.close()

        logstr += "... done.\n"
        WranglerLogger.info(logstr)

    def parseAndPrintTransitFile(self, trntxt, verbosity=1):
        """  Verbosity=1: 1 line per line summary
             Verbosity=2: 1 line per node
        """
        success, children, nextcharacter = self.parser.parse(trntxt, production="transit_file")
        if not nextcharacter==len(trntxt):
            errorstr  = "\n   Did not successfully read the whole file; got to nextcharacter=%d out of %d total" % (nextcharacter, len(trntxt))
            errorstr += "\n   Did read %d lines, next unread text = [%s]" % (len(children), trntxt[nextcharacter:nextcharacter+50])
            raise NetworkException(errorstr)

        # Convert from parser-tree format to in-memory transit data structures:
        convertedLines = self.parser.convertLineData()
        convertedLinks = self.parser.convertLinkData()
        convertedPNR   = self.parser.convertPNRData()
        convertedZAC   = self.parser.convertZACData()
        convertedAccessLinki = self.parser.convertLinkiData("access")
        convertedXferLinki   = self.parser.convertLinkiData("xfer")

        return convertedLines, convertedLinks, convertedPNR, convertedZAC, \
            convertedAccessLinki, convertedXferLinki

    def parseFile(self, fullfile, insert_replace):
        """ fullfile is the filename,
            insert_replace=True if you want to replace the data in place rather than appending
        """
        suffix = fullfile.rsplit(".")[-1].lower()
        self.parseFileAsSuffix(fullfile,suffix,insert_replace)

    def parseFileAsSuffix(self,fullfile,suffix,insert_replace):
        """ This is a little bit of a hack, but it's meant to allow us to do something
            like read an xfer file as an access file...
        """
        self.parser = TransitParser(transit_file_def, verbosity=0)
        self.parser.tfp.liType = suffix
        logstr = "   Reading %s as %s" % (fullfile, suffix)
        f = open(fullfile, 'r');
        lines,links,pnr,zac,accessli,xferli = self.parseAndPrintTransitFile(f.read(), verbosity=0)
        f.close()
        logstr += self.doMerge(fullfile,lines,links,pnr,zac,accessli,xferli,insert_replace)
        WranglerLogger.debug(logstr)

    def doMerge(self,path,lines,links,pnrs,zacs,accessli,xferli,insert_replace=False):
        """Merge a set of transit lines & support links with this network's transit representation.
        """

        logstr = " -- Merging"

        if len(lines)>0:
            logstr += " %s lines" % len(lines)

            extendlines = copy.deepcopy(lines)
            for line in lines:
                if isinstance(line,TransitLine) and (line in self.lines):
                    logstr += " *%s" % (line.name)
                    if insert_replace:
                        self.lines[self.lines.index(line)]=line
                        extendlines.remove(line)
                    else:
                        self.lines.remove(line)

            if len(extendlines)>0:
                # for line in extendlines: print line
                self.lines.extend(["\n;######################### From: "+path+"\n"])
                self.lines.extend(extendlines)

        if len(links)>0:
            logstr += " %d links" % len(links)
            self.links.extend(["\n;######################### From: "+path+"\n"])
            self.links.extend(links)  #TODO: Need to replace existing links

        if len(pnrs)>0:
            logstr += " %d PNRs" % len(pnrs)
            self.pnrs.extend( ["\n;######################### From: "+path+"\n"])
            self.pnrs.extend(pnrs)  #TODO: Need to replace existing PNRs

        if len(zacs)>0:
            logstr += " %d ZACs" % len(zacs)
            self.zacs.extend( ["\n;######################### From: "+path+"\n"])
            self.zacs.extend(zacs)  #TODO: Need to replace existing PNRs

        if len(accessli)>0:
            logstr += " %d accesslinks" % len(accessli)
            self.accessli.extend( ["\n;######################### From: "+path+"\n"])
            self.accessli.extend(accessli)

        if len(xferli)>0:
            logstr += " %d xferlinks" % len(xferli)
            self.xferli.extend( ["\n;######################### From: "+path+"\n"])
            self.xferli.extend(xferli)


        logstr += "...done."
        return logstr

    def mergeDir(self,path,insert_replace=False):
        """ Append all the transit-related files in the given directory.
            Does NOT apply __init__.py modifications from that directory.
        """
        dirlist = os.listdir(path)
        dirlist.sort()
        WranglerLogger.debug("Path: %s" % path)

        for filename in dirlist:
            suffix = filename.rsplit(".")[-1].lower()
            if suffix in ["lin","link","pnr","zac","access","xfer"]:
                self.parser = TransitParser(transit_file_def, verbosity=0)
                self.parser.tfp.liType = suffix
                fullfile = os.path.join(path,filename)
                logstr = "   Reading %s" % filename
                f = open(fullfile, 'r');
                lines,links,pnr,zac,accessli,xferli = self.parseAndPrintTransitFile(f.read(), verbosity=0)
                f.close()
                logstr += self.doMerge(fullfile,lines,links,pnr,zac,accessli,xferli,insert_replace)
                WranglerLogger.debug(logstr)

    def _runAndLog(self, cmd, run_dir):
        proc = subprocess.Popen( cmd, cwd = run_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE )
        for line in proc.stdout:
            WranglerLogger.debug("stdout: " + line.strip('\r\n'))
        for line in proc.stderr:
            WranglerLogger.debug("stderr: " + line.strip('\r\n'))
        ret  = proc.wait()
        WranglerLogger.debug("Received %d from [%s]" % (ret, cmd))
        return ret

    def cloneAndApplyProject(self, projectname, tag=None, tempdir=None, **kwargs):
        """ Project name corresponds to projects in Y:\networks
            tag is "1.0" or "1-latest", or None for just the latest version
            tempdir is the parent dir to put the dir; pass None for python to just choose
            kwargs are additional args for the apply
        """
        if tempdir==None:
            tempdir = tempfile.mkdtemp(prefix="Wrangler_tmp_", dir=".")
            WranglerLogger.debug("Using tempdir %s" % tempdir)
        elif not os.path.exists(tempdir):
            os.makedirs(tempdir)

        cmd = r"git clone Y:\networks\%s" % projectname
        ret = self._runAndLog(cmd, tempdir)

        if ret != 0:
            raise NetworkException("Git clone failed; see log file")

        if tag != None:
            newdir = os.path.join(tempdir, projectname)
            cmd = r"git checkout %s" % tag
            ret = self._runAndLog(cmd, newdir)
            if ret != 0:
                raise NetworkException("Git checkout failed; see log file")

        # apply it
        sys.path.append(tempdir)
        evalstr = "import %s; %s.apply(self" % (projectname, projectname)
        for key,val in kwargs.iteritems():
            evalstr += ", %s=%s" % (key, str(val))
        evalstr += ")"
        exec(evalstr)

        WranglerLogger.info("Applied %s" % projectname)

        # boo this doesn't work!
        descstr =  "for name,data in inspect.getmembers(%s):\n" % (projectname)
        descstr += "    if name==\"desc\" and inspect.ismethod(name):\n"
        descstr += "        WranglerLogger.info(\"   - Description:\" + %s.desc())\n" % (projectname)
        descstr += "    elif name==\"year\" and inspect.ismethod(name):\n"
        descstr += "        WranglerLogger.info(\"   - Year:\" + str(%s.year()))\n" % (projectname)
        descstr += "    else: WranglerLogger.debug(\"%s %s\" % (name, str(data)))\n"
        exec(descstr)
        # exec("members = inspect.getmembers(%s)" % projectname)
        # WranglerLogger.debug(members)
#        WranglerLogger.debug(inspect.getmembers()

    def addDelay(self, additionalLinkFile=""):
        """ Replaces the addDelay.awk script which is mostly parsing
            If additionalLinkFile is passed in, also uses that link file to supress dwell delay.
        """
        DELAY_VALUES = {}
        DELAY_VALUES['Std'] = {1:0.5,  2:0.5,  3:0.4,  # Muni Express, Local, Metro
                              4:0.0, # BART
                              5:0.5, # Non-SF Regional
                              6:0.2, # SamTrans Express
                              7:0.2, # Golden Gate Express
                              8:0.2, # AC Transit Express
                              9:0}   # Ferries, caltrain
        DELAY_VALUES['TPS'] = copy.deepcopy(DELAY_VALUES['Std'])
        for i in [1,2,3,5]:  # Muni modes plus non-sf regional are a bit faster
            DELAY_VALUES['TPS'][i] -= 0.1

        DELAY_VALUES['BRT'] = copy.deepcopy(DELAY_VALUES['Std'])
        DELAY_VALUES['BRT'][1]=0.32  # (20% Savings Low Floor)*(20% Savings POP)*Dwell=.8*.8*.5=.32
        DELAY_VALUES['BRT'][2]=0.32  # (20% Savings Low Floor)*(20% Savings POP)*Dwell=.8*.8*.5=.32
        DELAY_VALUES['BRT'][3]=0.3   # lmz changed to 0.3 from 0.1
        DELAY_VALUES['BRT'][5]=0.32
        DEFAULT_DELAY_VALUE=0.5

        linkSet = set()
        for link in self.links:
            if isinstance(link,TransitLink):
                link.addNodesToSet(linkSet)
        logstr = "addDelay: Size of linkset = %d" % (len(linkSet))

        if additionalLinkFile!="":
            linknet = Network()
            linknet.parser = TransitParser(transit_file_def, verbosity=0)
            f = open(additionalLinkFile, 'r');
            junk,additionallinks,junk,junk,junk,junk = \
                linknet.parseAndPrintTransitFile(f.read(), verbosity=0)
            f.close()
            for link in additionallinks:
                if isinstance(link,TransitLink):
                    link.addNodesToSet(linkSet)
                    # print linkSet
            logstr += " => %d with %s\n" % (len(linkSet), additionalLinkFile)
        WranglerLogger.debug(logstr)


        for line in self.lines:
            "addin for line:",line
            if not isinstance(line,TransitLine): continue
            # replace RUNTIME with TIMEFAC=1.0
            if "RUNTIME" in line.attr:
                del line.attr["RUNTIME"]
                # line.attr["TIMEFAC"] = 1.0

            # figure out what the dwell delay is
            dwellDelay = 0
            if 'MODE' not in line.attr:
                WranglerLogger.warning("Mode unknown for line %s" % (line.name))
                dwellDelay = DEFAULT_DELAY_VALUE
            else:
                mode = int(line.attr['MODE'].strip(r'"\''))
                if 'OWNER' in line.attr:    owner = line.attr['OWNER'].strip(r'"\'')
                else:                       owner = 'Std'

                if owner not in DELAY_VALUES:
                    WranglerLogger.warning("addDelay: Didn't understand owner [%s] in line [%s]  Using owner=[Std]" % (owner, line.name))
                    owner = 'Std'

                dwellDelay = DELAY_VALUES[owner][mode]

                # print "line name=%s mode=%d owner=%s dwellDelay=%f" % (line.name, mode, owner, dwellDelay)


            # add it in
            for nodeIdx in range(len(line.n)):
                # linkSet nodes - don't add delay 'cos that's inherent to the link
                if int(line.n[nodeIdx].num) in linkSet: continue

                # last stop - no delay, end of the line
                if nodeIdx == len(line.n)-1: continue

                # dwell delay for stop nodes only, first is ok if nonstop
                if nodeIdx>0 and not line.n[nodeIdx].isStop(): continue

                line.n[nodeIdx].attr["DELAY"]=str(dwellDelay)


if __name__ == '__main__':

    LOG_FILENAME = "Wrangler_main_%s.info.LOG" % time.strftime("%Y%b%d.%H%M%S")
    setupLogging(LOG_FILENAME, LOG_FILENAME.replace("info", "debug"))

    net = Network()
    net.cloneAndApplyProject(projectname="Muni_TEP")
    net.cloneAndApplyProject(projectname="Muni_CentralSubway", tag="1-latest", modelyear=2030)
    net.cloneAndApplyProject(projectname="BART_eBART")

    net.write(name="muni", writeEmptyFiles=False)
