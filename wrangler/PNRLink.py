import re
from .Regexes import nodepair_pattern

__all__ = ['PNRLink']

class PNRLink(dict):
    """ PNR Support Link.
       'node' property is the node-pair for this link (e.g. 24133-34133)
       'comment' is any end-of-line comment for this link including the leading semicolon
        All other attributes are stored in a dictionary (e.g. thislink['MODE']='1,2')
    """
    UNNUMBERED = "unnumbered"
    
    def __init__(self):
        dict.__init__(self)
        self.id=''
        self.comment=''

        self.pnr=''
        self.station=''

    def __repr__(self):
        s = "PNR NODE=%s " % (self.id,)

        # Deal w/all link attributes
        fields = ['%s=%s' % (k,v) for k,v in self.items()]

        s += " ".join(fields)
        s += self.comment

        return s

    def parseID(self):
        """
        From CUBE documentation:
         Normally, NODE is a transit stop node. However, at some locations, the NODE
         might not be a stop node, but merely a drop-off node, or the entrance to a
         parking lot associated with a transit-stop node. To accommodate the latter
         scenario, append a second node to the first NODE value (NODE-NODE); the
         program generates an additional support (lot) link between the two nodes.
        """
        if self.id:
            m = re.match(nodepair_pattern, self.id)
            
            # it's either just the station
            if m == None: # it's a nodenum
                self.station = self.id
                self.pnr = self.UNNUMBERED
            # or it's pnr,station
            else:
                self.pnr = m.group(1)
                self.station = m.group(2)

        else:
            pass
        