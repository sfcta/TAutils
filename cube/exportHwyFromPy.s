RUN PGM=NETWORK

NETI[1]=%CUBENET%
LINKO=%TEMP%\link.csv ,FORMAT=SDF,INCLUDE=A,B,%XTRAVAR%
NODEO=%TEMP%\node.csv,FORMAT=SDF,INCLUDE=N,X,Y

ENDRUN