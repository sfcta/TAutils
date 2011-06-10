__all__ = ['ZACLink']

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
