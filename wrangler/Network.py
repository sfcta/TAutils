import os, re, string, subprocess, sys, tempfile
from .Logger import WranglerLogger
from .NetworkException import NetworkException
from .Regexes import git_commit_pattern, tag_num_pattern

__all__ = ['Network']

class Network(object):

    CHAMP_VERSION_DEFAULT = "pre4.3"
    # static variable
    allNetworks = {}

    def __init__(self, champVersion, networkName = None):
        """
        *champVersion* argument is for compatibility check.
        Currently this should be one of *pre4.3* and *4.3*
        Pass *networkName* to be added to the Networks dictionary
        """
        if champVersion not in ["4.3", "pre4.3"]:
            raise NetworkException("Do not understand champVersion %s")

        self.champVersion = champVersion
        self.appliedProjects = {}
        if networkName: Network.allNetworks[networkName] = self

    def _runAndLog(self, cmd, run_dir=".", logStdoutAndStderr=False):
        """
        Runs the given command in the given *run_dir*.  Returns a triple:
         (return code, stdout, stderr)
        where stdout and stderr are lists of strings.
        """
        proc = subprocess.Popen( cmd, cwd = run_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE )
        retStdout = []
        for line in proc.stdout:
            line = line.strip('\r\n')
            if logStdoutAndStderr: WranglerLogger.debug("stdout: " + line)
            retStdout.append(line)

        retStderr = []
        for line in proc.stderr:
            line = line.strip('\r\n')
            if logStdoutAndStderr: WranglerLogger.debug("stderr: " + line)
            retStderr.append(line)
        retcode  = proc.wait()
        WranglerLogger.debug("Received %d from [%s]" % (retcode, cmd))
        return (retcode, retStdout, retStderr)


    def getProjectVersion(self, parentdir, networkdir, gitdir, projectsubdir=None):
        """
        Implemented by subclasses. Returns champVersion for this project. 

        See :py:meth:`Wrangler.Network.applyProject` for argument details.
        """
        pass
    
    def checkProjectVersion(self, parentdir, networkdir, gitdir, projectsubdir=None):
        """
        Verifies that this project is compatible with the champVersion, raises an exception
          if not

        See :py:meth:`Wrangler.Network.applyProject` for argument details.
        """
        # the subclass figures out what champVersion this project is
        projChampVersion = self.getProjectVersion(parentdir=parentdir, networkdir=networkdir,
                                                  gitdir=gitdir, projectsubdir=projectsubdir)
        WranglerLogger.debug("Checking champ version compatibility of project (%s) with requirement (%s)" % 
                             (projChampVersion, self.champVersion))

        if self.champVersion == "pre4.3":
            if projChampVersion == "pre4.3":
                return
            if projChampVersion == "4.3":
                # See if there's a pre4.3 branch we can checkout
                cmd = r"git checkout preCHAMP4.3"
                (retcode, retstdout, retstderr) = self._runAndLog(cmd, gitdir)
                if retcode != 0:
                    raise NetworkException("Git checkout failed; see log file")
        
        if self.champVersion == "4.3":
            if projChampVersion == "pre4.3":
                raise NetworkException("Trying to use a pre4.3 network project (%s) to build a Champ4.3 network" % 
                                       (networkdir if not projectsubdir else os.path.join(networkdir,projectsubdir)))
        
    def applyProject(self, parentdir, networkdir, gitdir, projectsubdir=None, **kwargs):
        """
        Implemented by subclasses.  Args are as follows:

        * *parentdir* is the directory we're checking stuff out into (e.g. a temp dir)
        * *networkdir* is the name of the dir within ``Y:\\networks``
        * *gitdir* is the git repo; either the same as *networkdir* if the git repo is at
           that level (the typical case), or it's *networkdir\projectsubdir*
        * *projectsubdir* is an optional subdir of *networkdir*; If the ``apply.s`` or ``__init__.py``
          is in a subdir, this is how it's specified
        * *kwargs* are additional keyword args to pass into the apply()
        """
        pass
                                       
    def cloneAndApplyProject(self, networkdir, projectsubdir=None, tag=None, tempdir=None, **kwargs):
        """
        * *networkdir* corresponds to the dir relative to ``Y:\\networks``
        * *projectsubdir* is a subdir within that, or None if there's no subdir
        * *tag* is "1.0" or "1-latest", or None for just the latest version
        * *tempdir* is the parent dir to put the git clone dir; pass None for python to just choose
        * *kwargs* are additional args for the apply
        """
        if tempdir:
            gitdir = os.path.join(tempdir, networkdir)
            
            if not os.path.exists(tempdir):
                os.makedirs(tempdir)
                
            # if the tempdir exists and it's already here and the projectsubdir is present, 
            # then we already checked it out
            elif projectsubdir and os.path.exists(os.path.join(tempdir,networkdir,projectsubdir)):
                WranglerLogger.debug("Skipping checkout of %s, %s already exists" % 
                                     (networkdir, os.path.join(tempdir,networkdir,projectsubdir)))

                 # verify we didn't require conflicting tags
                try:
                    commitstr = self.getCommit(gitdir)
                except:
                    gitdir = os.path.join(gitdir, projectsubdir)
                    commitstr = self.getCommit(gitdir)

                tags = self.getTags(gitdir, commitstr)
                if tag and (not tags or tag not in tags):
                    # TODO: just checkout to the new tag
                    raise NetworkException("Conflicting tag requirements - FIXME!")

                self.checkProjectVersion(parentdir=tempdir, networkdir=networkdir,
                                         gitdir=gitdir, projectsubdir=projectsubdir)

                self.applyProject(parentdir=tempdir, networkdir=networkdir,
                                  gitdir=gitdir, projectsubdir=projectsubdir, **kwargs)
                return
            
            elif not projectsubdir and os.path.exists(os.path.join(tempdir,networkdir)):
                WranglerLogger.debug("Skipping checkout of %s, %s already exists" % 
                                     (networkdir, os.path.join(tempdir,networkdir)))
                
                self.checkProjectVersion(parentdir=tempdir, networkdir=networkdir,
                                         gitdir=gitdir, projectsubdir=projectsubdir)

                # TODO: we should verify we didn't require conflicting tags?
                self.applyProject(parentdir=tempdir, networkdir=networkdir,
                                  gitdir=gitdir, projectsubdir=projectsubdir, **kwargs)
                return
        else:
            tempdir = tempfile.mkdtemp(prefix="Wrangler_tmp_", dir=".")
            WranglerLogger.debug("Using tempdir %s" % tempdir)
            gitdir = os.path.join(tempdir, networkdir)
        
        WranglerLogger.debug("Checking out networkdir %s into tempdir %s %s" %
                             (networkdir,tempdir,"for "+projectsubdir if projectsubdir else ""))
        cmd = r"git clone --quiet Y:\networks\%s" % networkdir
        (retcode, retstdout, retstderr) = self._runAndLog(cmd, tempdir)
        
        if retcode != 0:
            if not projectsubdir:
                raise NetworkException("Git clone failed; see log file")

            # if there was a subdir involved, try checking if the subdir is the git dir
            gitdir = os.path.join(tempdir, networkdir, projectsubdir)
            newtempdir = os.path.join(tempdir,networkdir)
            if not os.path.exists(newtempdir):
                os.makedirs(newtempdir)

            cmd = r"git clone --quiet Y:\networks\%s\%s" % (networkdir, projectsubdir)
            (retcode, retstdout, retstderr) = self._runAndLog(cmd, newtempdir)



        if tag != None:
            cmd = r"git checkout %s" % tag
            (retcode, retstdout, retstderr) = self._runAndLog(cmd, gitdir)
            if retcode != 0:
                raise NetworkException("Git checkout failed; see log file")

        self.checkProjectVersion(parentdir=tempdir, networkdir=networkdir,
                                 gitdir=gitdir, projectsubdir=projectsubdir)

        self.applyProject(parentdir=tempdir, networkdir=networkdir,
                          gitdir=gitdir, projectsubdir=projectsubdir, **kwargs)

    def getCommit(self, gitdir):
        """
        Figures out the commit string for the given gitdir (so gitdir is a git dir).
        (e.g. a 40-character hex string)
        """
        cmd = r"git log -1"
        (retcode, retstdout, retstderr) = self._runAndLog(cmd, gitdir)
        if len(retstdout)<3:
            raise NetworkException("Git log failed; see log file")
        
        m = re.match(git_commit_pattern, retstdout[0])
        if not m:
            raise NetworkException("Didn't understand git log output: [" + retstdout[0] + "]")

        return m.group(1)

    def getTags(self, gitdir, commitstr):
        """
        Returns a list of all tags for this commit
        """
        cmd = r"git tag --contains " + commitstr
        (retcode, retstdout, retstderr) = self._runAndLog(cmd, gitdir)
        if len(retstdout)==0:
            return None
        return retstdout

    def getNumericTag(self, gitdir, commitstr):
        """
        Figures out the numeric tag, returns it.
        """
        tags = self.getTags(gitdir, commitstr)
        if not tags: return None

        for tag in tags:
            # require them to be 1.x(.x)
            if re.match(tag_num_pattern, tag):
                return tag
        print None

    def logProject(self, gitdir, projectname, year=None, projectdesc=None, county=None):
        """
        Figures out the commit string and the tag.  Subclass should figure out the rest.
        """
        commitstr = self.getCommit(gitdir)
        tag       = self.getNumericTag(gitdir, commitstr)

        if year:
            yearstr = "%4d" % year
        else:
            yearstr = "    "

        WranglerLogger.info("%-4s | %-5s | %-40s | %-40s | %-10s | %s" %
                            (yearstr,
                             tag if tag else "notag",
                             commitstr if commitstr else "",
                             string.lstrip(projectname) if projectname else "",
                             string.lstrip(county) if county else "",
                             string.lstrip(projectdesc) if projectdesc else ""
                             )
                            )
        self.appliedProjects[projectname] = tag if tag else commitstr
                
    def write(self, path='.', name='network', writeEmptyFiles=True, suppressQuery=False):
        """
        Implemented by subclass
        """
        pass