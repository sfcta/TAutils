import logging

__all__ = ['WranglerLogger', 'setupLogging']


# for all the Wrangler logging needs!
WranglerLogger = logging.getLogger("WranglerLogger")


def setupLogging(infoLogFilename, debugLogFilename, logToConsole=True):
    """ Sets up the logger.  The infoLog is terse, just gives the bare minimum of details
        so the network composition will be clear later.
        The debuglog is very noisy, for debugging.
        
        Pass none to either.
        Spews it all out to console too, if logToConsole is true.
    """
    # create a logger
    WranglerLogger.setLevel(logging.DEBUG)

    if infoLogFilename:
        infologhandler = logging.StreamHandler(open(infoLogFilename, 'w'))
        infologhandler.setLevel(logging.INFO)
        infologhandler.setFormatter(logging.Formatter('%(message)s'))
        WranglerLogger.addHandler(infologhandler)
    
    if debugLogFilename:
        debugloghandler = logging.StreamHandler(open(debugLogFilename,'w'))
        debugloghandler.setLevel(logging.DEBUG)
        debugloghandler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s', '%Y-%m-%d %H:%M'))
        WranglerLogger.addHandler(debugloghandler)
    
    if logToConsole:
        consolehandler = logging.StreamHandler()
        consolehandler.setLevel(logging.DEBUG)
        consolehandler.setFormatter(logging.Formatter('%(name)-12s: %(levelname)-8s %(message)s'))
        WranglerLogger.addHandler(consolehandler)
        
        
