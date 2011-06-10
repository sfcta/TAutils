import logging

class HwySpecsRTP:
    """ Simple class to read in the RTP specifications from a CSV file.
    """
    
    def __init__(self,specsFile):
        """
        Read and cache specifications.  Will apply in order read in.
        """
        self.projects = [] # list of RTP reference numbers
        self.projectdict = {} # RTP reference number => dictionary of attributes
        
        specs = open(specsFile,'r')
        i=0
        for line in specs:
            i+=1
            if i==1:
                head=line.strip().split(',')
            else:
                l = line.strip().split(',')
                #print l
                RTPref = l[head.index("RTP Ref#")]
                self.projectdict[RTPref] = {}
                self.projects.append(RTPref)
                
                self.projectdict[RTPref]["Facility"]=l[head.index("Corridor")]
                self.projectdict[RTPref]["Action"]=l[head.index("Action")]
                self.projectdict[RTPref]["Span"]=l[head.index("Span")]
                self.projectdict[RTPref]["County"]=l[head.index("County")]
                self.projectdict[RTPref]["MOD YEAR"]=int(l[head.index("MOD YEAR")])
                self.projectdict[RTPref]["RTP FUNDING"]=l[head.index("RTP FUNDING")]


    def listOfProjects(self,maxYear=2035,baseYear=2000):
        """
        Returns the project RTP Reference numbers that qualify (after *baseYear*, before and including *maxYear*)
        """
        projectList = []
        for pref in self.projects:
            if self.projectdict[pref]["MOD YEAR"]<=maxYear and self.projectdict[pref]["MOD YEAR"]>baseYear:
                projectList.append(pref)
        return projectList
        
    def printProjects(self,fileObj):
        fileObj.write("YEAR   RTP     FACILITY       COUNTY     ACTION      \n")
        fileObj.write("----------------------------------------------------\n")
        for p in self.projects:
            fileObj.write( str(p["MOD YEAR"])+" "+p["RTP REF"]+" "+p["Facility"]+" "+p["Action"]+" "+p["County"]+"\n")
    
    def logProjects(self, logger):
        logger.info("YEAR   RTP     FACILITY       COUNTY     ACTION      ")
        logger.info("----------------------------------------------------")
        for p in self.projects:
            logger.info( str(p["MOD YEAR"])+" "+p["RTP REF"]+" "+p["Facility"]+" "+p["Action"]+" "+p["County"])



