import sys

__all__ = ['Node']

class Node(object):
    """
    Transit node. This can only exist as part of a transit line.
    
    * *num* is the string representation of the node number with stop-status (e.g. '-24322')
    * *stop* is True or False
    
    All other attributes stored as a dictionary. e.g::

        thisnode["DELAY"]="0.5"

    """
    
    # static variables for nodes.xls
    descriptions        = {}
    descriptions_read   = False

    def __init__(self, n):
        self.attr = {}
        if isinstance(n,int):
            self.num = str(n)
        else:
            self.num = n            
        self.stop=(self.num.find('-')<0 and True or False)
        self.comment = None

    def setStop(self, isStop=True):
        """
        Changes to stop-status of this node to *isStop*
        """
        n = abs(int(self.num))
        self.stop = isStop

        if not self.stop:
            n = -n

        self.num = str(n)

    def isStop(self):
        """
        Returns True if this node is a stop, False if not.
        """
        if int(self.num)>0: return True
        return False

    def boardsDisallowed(self):
        """
        Returns True if this node is a stop and boardings are disallowed (ACCESS=2)
        """
        if not self.isStop(): return False
        
        if "ACCESS" not in self.attr: return False
        
        if int(self.attr["ACCESS"]) == 2: return True
        
        return False

    def lineFileRepr(self, prependNEquals=False, lastNode=False):
        """
        String representation for line file
        """

        if prependNEquals: s=" N="
        else:              s="   "

        # node number
        if self.stop: s+= " "
        s += self.num
        # attributes
        for k,v in sorted(self.attr.items()):
            if k=="DELAY" and float(v)==0: continue  # NOP
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

    def description(self):
        """
        Returns the description of this node (a string), or None if unknown.
        """
        Node.getDescriptions()
        
        if abs(int(self.num)) in Node.descriptions:
            return Node.descriptions[abs(int(self.num))]
        
        return None

    @staticmethod
    def getDescriptions():
        # if we've already done this, do nothing
        if Node.descriptions_read: return
        
        try:
            import xlrd
            workbook = xlrd.open_workbook(filename=r"Y:\champ\util\nodes.xls",
                                          encoding_override='ascii')
            sheet    = workbook.sheet_by_name("equiv")
            row = 0
            while (row < sheet.nrows):
                Node.descriptions[int(sheet.cell_value(row,0))] = \
                    sheet.cell_value(row,1).encode('utf-8')
                row+=1
            
            # print "Read descriptions: " + str(Node.descriptions)
        except ImportError: 
            print "Could not import xlrd module, Node descriptions unknown"
        except:
            print "Unexpected error reading Nodes.xls:", sys.exc_info()[0]
            print sys.exc_info()
            
        Node.descriptions_read = True
                