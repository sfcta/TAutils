class Linki(dict):
    """ Linki Link.  Has A-node, B-node, possibly a comment and a distance.
    """
    def __init__(self):
        dict.__init__(self)
        self.A=''
        self.B=''
        self.comment=''
        self.distance=''
        self.xferTime=''
        self.accessType=''
    
    def __repr__(self):
        s = "%8s %8s" % (self.A, self.B)
        
        # access links have a type and a transfer time
        if self.accessType != '':
            s += " %s" % self.accessType

        if self.xferTime != '':
            s += " %3s" % self.xferTime    
        elif self.distance != '':
            s += " %8s" % self.distance
        
        if self.comment != '':
            s += " %s" % (self.comment)
        return s
    