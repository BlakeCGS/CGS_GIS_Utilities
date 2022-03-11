from io import StringIO
import sys
import smtplib
import os
import json
import logging
from arcgis.gis import GIS
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import date, datetime
from logging.handlers import RotatingFileHandler
import publishReport

class LogGIS(object):
    def __init__(self, scriptPath, scriptDescription):
        self.ScriptDescription = scriptDescription
        configFile = os.path.join(os.path.dirname(__file__), 'loggis_config.json')
        with open(configFile, 'r') as configFileIn:
            configData = configFileIn.read()
        configObj = json.loads(configData)
        for prop, value in configObj.items():
            setattr(self, prop, value)
        now = datetime.now()
        #Valid values for LogLevel are: DEBUG, INFO, WARN, ERROR, CRITICAL. The default is INFO.
        fileLogLevel = logging.DEBUG
        emailLogLevel = logging.INFO
        if hasattr(self, 'FileLogLevel'):
            fileLogLevel = self.GetLogLevelFromText(self.FileLogLevel)
        if hasattr(self, 'EmailLogLevel'):
            emailLogLevel = self.GetLogLevelFromText(self.EmailLogLevel)
         # Expose logging levels. These are just helpers so the calling scripts does not need to import logging
        self.DEBUG = logging.DEBUG
        self.INFO = logging.INFO
        self.WARNING = logging.WARNING
        self.ERROR = logging.ERROR
        self.CRITICAL = logging.CRITICAL
        
        #Set path properties
        self.ScriptFullPath = os.path.realpath(scriptPath)
        self.ScriptParentFolder = os.path.dirname(self.ScriptFullPath)
        self.ScriptFileNameWithExt = os.path.basename(self.ScriptFullPath)
        self.ScriptFileName = os.path.splitext(self.ScriptFileNameWithExt)[0]

        # Set logfile
        codePath = os.path.dirname(os.path.abspath(scriptPath))
        scriptFileName = os.path.split(scriptPath)[1]
        logFileName = f'{os.path.splitext(scriptFileName)[0]}_{str(now.year)}.log'
        logfile = os.path.join(codePath, 'logs', logFileName)

        # Create logging formatter
        #fhFormatter = logging.Formatter('%(asctime)-12s %(funcName)-36s %(message)-96s', '%I:%M:%S %p')
        logFormatter = logging.Formatter("%(asctime)-28s %(levelname)-8s %(funcName)s:%(lineno)-12s %(message)-36s", '%m/%d/%Y @ %I:%M:%S %p')        
        # Create logging rotating handler
        rotateHandler = RotatingFileHandler(logfile, maxBytes=1000000, backupCount=5)
        rotateHandler.setLevel(fileLogLevel)
        rotateHandler.setFormatter(logFormatter)
        #Create the console hanlder
        console_handler = logging.StreamHandler()
        #console_handler.setLevel(logLevel)
        #Create the stream handler
        self._logStream = StringIO()
        streamHandler = logging.StreamHandler(self._logStream)
        streamHandler.setLevel(emailLogLevel)
        streamHandler.setFormatter(logFormatter)

        # Create logger object and add all the handlers
        self.logger = logging.getLogger(scriptFileName)
        self.logger.addHandler(rotateHandler)
        self.logger.addHandler(console_handler)
        self.logger.addHandler(streamHandler)
        self.logger.setLevel(logging.DEBUG)
        self.logger.debug('**************************************************************************')

        #Setup portal logging
        if self.LoggingPortalURL.upper() == "PRO":
            self.gis = GIS("pro")
        else:
            self.gis = GIS(self.LoggingPortalURL, self.LoggingPortalUser, self.LoggingPortalPassword)
        if self.PortalScriptInfoItemID == "":
            print ("Publishing the Script Info report")
            newId = publishReport.publishCsvReport(self.gis, self.FilenameScriptInfo, "")
            # Write new ItemId
            print (f"Writing new itemId ({newId}) to the config file.")
            configObj["PortalScriptInfoItemID"] = newId
            f = open(configFile, "w")
            f.write(json.dumps(configObj, indent=4))
            f.close()
            # Get the new table and delete the sample row.
            fl = self.gis.content.get(newId)
            table = fl.tables[0]
            print (f"Deleting the sample row.")
            deletes = table.delete_features(where = "OBJECTID > 0")
        else:
            fl = self.gis.content.get(self.PortalScriptInfoItemID)
            if fl is None:
                print ("Couldn't Find the Featre Layer. You might need to clear the itemId in the config.json file.")
        self.scriptInfoTable = fl.tables[0]
        fset = self.scriptInfoTable.query(where=f"FileName='{self.ScriptFullPath}'")
        self.scriptRow = None
        if len(fset) == 0:
            self.scriptInfoTable.edit_features(adds = [{"attributes": {"FileName": f"{self.ScriptFullPath}", "Description": f"{self.ScriptDescription}"}}])
            self.scriptRow = self.scriptInfoTable.query(where=f"FileName='{self.ScriptFullPath}'").features[0]
        else:
            self.scriptRow = fset.features[0]


    def CompleteLogging(self):
        while self.logger.hasHandlers():
            self.logger.removeHandler(self.logger.handlers[0])


    def SetStartInfo(self):
        self.PreviousStartTime = self.scriptRow.attributes['LastStart']
        self.scriptRow.attributes['LastStart'] = datetime.now()
        self.scriptInfoTable.edit_features(updates=[self.scriptRow])
    
    def SetEndInfo(self):
        self.PreviousEndTime = self.scriptRow.attributes['LastEnd']
        self.scriptRow.attributes['LastEnd'] = datetime.now()
        self._logStream.flush()
        logMessage = self._logStream.getvalue()
        self.scriptRow.attributes['LastMessage'] = logMessage
        self.scriptRow.attributes['LastStatus'] = 'ERROR' if 'ERROR' in logMessage else 'SUCCESS'
        a = self.scriptInfoTable.edit_features(updates=[self.scriptRow])
        print (a)

    def GetLogLevelFromText(self, logText):
        logLevel = logging.INFO
        if logText.upper() == 'DEBUG':
            logLevel = logging.DEBUG
        elif logText.upper() == 'WARN':
            logLevel = logging.WARNING
        elif logText.upper() == 'ERROR':
            logLevel = logging.ERROR
        elif logText.upper() == 'CRITICAL':
            logLevel = logging.CRITICAL
        return logLevel

        # Start log
        #self.logger.info(f'script {scriptPath} started')
 
    def emailLog(self):
        self._logStream.flush()
        logMessage = self._logStream.getvalue()
        subject = f'{self.ScriptDescription} - ERROR' if 'ERROR' in logMessage else f'{self.ScriptDescription} - SUCCESS'
        self.sendEmail(subject, logMessage, self.StandardEmailList)

    def sendEmail(self, subject, msg_html, recipients, internal=False):
        try:
            msg = MIMEMultipart()
            msg['Subject'] = subject
            msg['To'] = ';'.join(recipients)
            msg['From'] = self.MaileSender
            # create the tags for the HTML version of the message so it has a fixed width font
            prefix_html = '''\
            <html>
            <head></head>
            <body>
            <p style="font-family:'Lucida Console', Monaco, monospace;font-size:12px">
            '''
            suffix_html = '''\
            </p>
            </body>
            </html>
            '''
            # replace spaces with non-breaking spaces (otherwise, multiple spaces are truncated)
            msg_html = msg_html.replace(' ', '&nbsp;')
            # replace new lines with <br> tags and add the HTML tags before and after the message
            msg_html = prefix_html + msg_html.replace('\n', '<br>') + suffix_html

            # # Record the MIME types of both parts - text/plain and text/html.
            #part1 = MIMEText(msgPlain, 'plain')
            part2 = MIMEText(msg_html, 'html')

            # Add both forms of the message
            #msg.attach(part1)
            msg.attach(part2)

            # Connect to exchange and send email
            conn = smtplib.SMTP(self.SMTPServer)
            conn.ehlo()
            #conn.starttls()
            conn.ehlo()
            conn.sendmail(self.MaileSender, recipients, msg.as_string())
            conn.close()
        except Exception as e:
            tb = sys.exc_info()[2]
            #print (e)
            self.logger.error(f"ERROR @ Line {tb.tb_lineno}. {str(e.args[0])}", self.ERROR)
