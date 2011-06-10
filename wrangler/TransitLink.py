import re
from .Regexes import nodepair_pattern

__all__ = ['TransitLink']

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
        
        self.Anode = None
        self.Bnode = None

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
        
    def setId(self, id):
        self.id = id

        m = re.match(nodepair_pattern, self.id)
        self.Anode = int(m.group(1))
        self.Bnode = int(m.group(2))  

    def isOneway(self):
        for key in self.keys():
            
            if key.upper()=="ONEWAY":
                if self[key].upper() in ["NO", "N", "0", "F", "FALSE"]: return False
                return True
        # key not found - what's the default?
        return True
                