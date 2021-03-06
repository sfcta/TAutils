import os, re, shutil, subprocess
from socket         import gethostname

from .HwySpecsRTP import HwySpecsRTP
from .Logger import WranglerLogger
from .Network import Network
from .NetworkException import NetworkException

__all__ = ['HighwayNetwork']

class HighwayNetwork(Network):
    """
    Representation of a roadway network.
    """

    def __init__(self, champVersion, basenetworkpath, isTiered=False,
                 hwyspecsdir=None, hwyspecs=None, tempdir=None, networkName=None):
        """
        *basenetworkpath* should be a starting point for this network, and include a ``FREEFLOW.net``,
        as well as ``turns[am,pm,op].pen`` files.

        *isTiered*: when False, checks out the *basenetworkpath* from Y:\networks.  When True,
        expects the basenetwork path to be a fullpath and uses that.

        *hwyspecs*, if passed in, should be an instance of :py:class:`HwySpecsRTP`.  It
        is only used for logging.
        """
        Network.__init__(self, champVersion, networkName)
        
        if isTiered:
            (head,tail) = os.path.split(basenetworkpath)
            self.applyBasenetwork(head,tail,None)
        else:
            self.applyingBasenetwork = True
            self.cloneAndApplyProject(networkdir=basenetworkpath, tempdir=tempdir)

        # keep a reference of the hwyspecsrtp for logging
        self.hwyspecsdir = hwyspecsdir
        self.hwyspecs = hwyspecs

    def getProjectVersion(self, parentdir, networkdir, gitdir, projectsubdir=None):
        """        
        Returns champVersion for this project

        See :py:meth:`Wrangler.Network.applyProject` for argument details.
        """
        if projectsubdir:
            champversionFilename = os.path.join(parentdir, networkdir, projectsubdir,"champVersion.txt")
        else:
            champversionFilename = os.path.join(parentdir, networkdir,"champVersion.txt")

        try:
            WranglerLogger.debug("Reading %s" % champversionFilename)
            champVersion = open(champversionFilename,'r').read()
            champVersion = champVersion.strip()
        except:
            champVersion = Network.CHAMP_VERSION_DEFAULT
        return champVersion
        
    def applyBasenetwork(self, parentdir, networkdir, gitdir):
        
        # copy the base network file to my workspace
        shutil.copyfile(os.path.join(parentdir,networkdir,"FREEFLOW.net"), "FREEFLOW.BLD")
        for filename in ["turnsam.pen", "turnspm.pen", "turnsop.pen"]:
            shutil.copyfile(os.path.join(parentdir,networkdir,filename), filename)

        # done
        self.applyingBasenetwork = False

    def applyProject(self, parentdir, networkdir, gitdir, projectsubdir=None, **kwargs):
        """
        Applies a roadway project by calling ``runtpp`` on the ``apply.s`` script.
        By convention, the input to ``apply.s`` is ``FREEFLOW.BLD`` and the output is 
        ``FREEFLOW.BLDOUT`` which is copied to ``FREEFLOW.BLD`` at the end of ``apply.s``

        See :py:meth:`Wrangler.Network.applyProject` for argument details.
        """
        # special case: base network
        if self.applyingBasenetwork:
            self.applyBasenetwork(parentdir, networkdir, gitdir)
            return
        
        if projectsubdir:
            applyDir = os.path.join(parentdir, networkdir, projectsubdir)
            applyScript = "apply.s"
            descfilename = os.path.join(parentdir, networkdir, projectsubdir,"desc.txt")
            turnsfilename = os.path.join(parentdir, networkdir, projectsubdir, "turns.pen")
        else:
            applyDir = os.path.join(parentdir, networkdir)
            applyScript = "apply.s"
            descfilename = os.path.join(parentdir, networkdir,'desc.txt')
            turnsfilename = os.path.join(parentdir, networkdir, "turns.pen")

        # read the description
        desc = None
        try:
            desc = open(descfilename,'r').read()
        except:
            pass
        
        # move the FREEFLOW.BLD into place
        shutil.move("FREEFLOW.BLD", os.path.join(applyDir,"FREEFLOW.BLD"))

        # dispatch it, cube license
        hostname = gethostname().lower()
        if hostname not in ['berry','eureka','taraval','townsend']:
            f = open('runtpp_dispatch.tmp', 'w')
            f.write("runtpp " + applyScript + "\n")
            f.close()
            (cuberet, cubeStdout, cubeStderr) = self._runAndLog("Y:/champ/util/bin/dispatch.bat runtpp_dispatch.tmp taraval", run_dir=applyDir) 
        else:
            (cuberet, cubeStdout, cubeStderr) = self._runAndLog(cmd="runtpp "+applyScript, run_dir=applyDir)
            

        nodemerge = re.compile("NODEMERGE: \d+")
        linkmerge = re.compile("LINKMERGE: \d+-\d+")
        for line in cubeStdout:
            line = line.rstrip()
            if re.match(nodemerge,line): continue
            if re.match(linkmerge,line): continue
            WranglerLogger.debug(line)
        
        if cuberet != 0 and cuberet != 1:
            WranglerLogger.fatal("FAIL! Project: "+applyScript)
            raise NetworkException("HighwayNetwork applyProject failed; see log file")

        # move it back
        shutil.move(os.path.join(applyDir,"FREEFLOW.BLD"), "FREEFLOW.BLD")

        # append new turn penalty file to mine
        if os.path.exists(turnsfilename):
            for filename in ["turnsam.pen", "turnspm.pen", "turnsop.pen"]:
                newturnpens = open(turnsfilename, 'r').read()
                turnfile = open(filename, 'a')
                turnfile.write(newturnpens)
                turnfile.close()
                WranglerLogger.debug("Appending turn penalties from "+turnsfilename)

        WranglerLogger.debug("")
        WranglerLogger.debug("")

        year    = None
        county  = None
        if (networkdir==self.hwyspecsdir and
            self.hwyspecs and
            projectsubdir in self.hwyspecs.projectdict):
            year    = self.hwyspecs.projectdict[projectsubdir]["MOD YEAR"]
            county  = self.hwyspecs.projectdict[projectsubdir]["County"]
            desc    = (self.hwyspecs.projectdict[projectsubdir]["Facility"] + ", " +
                       self.hwyspecs.projectdict[projectsubdir]["Action"] + ", " +
                       self.hwyspecs.projectdict[projectsubdir]["Span"])

        self.logProject(gitdir=gitdir,
                        projectname=(networkdir + "\\" + projectsubdir if projectsubdir else networkdir),
                        year=year, projectdesc=desc, county=county)

    def write(self, path='.', name='FREEFLOW.NET', writeEmptyFiles=True, suppressQuery=False):
        if not os.path.exists(path):
            WranglerLogger.debug("\nPath [%s] doesn't exist; creating." % path)
            os.mkdir(path)

        else:
            netfile = os.path.join(path,"FREEFLOW.net")
            if os.path.exists(netfile) and not suppressQuery:
                print "File [%s] exists already.  Overwrite contents? (y/n/s) " % netfile
                response = raw_input("")
                WranglerLogger.debug("response = [%s]" % response)
                if response == "s" or response == "S":
                    WranglerLogger.debug("Skipping!")
                    return

                if response != "Y" and response != "y":
                    exit(0)

        shutil.copyfile("FREEFLOW.BLD",os.path.join(path,name))
        WranglerLogger.info("Writing into %s\\%s" % (path, name))
        WranglerLogger.info("")

        for filename in ["turnsam.pen", "turnspm.pen", "turnsop.pen"]:
            shutil.copyfile(filename, os.path.join(path, filename))
