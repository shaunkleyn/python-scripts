import sys, traceback, os
import logging
import requests
import time
import subprocess
import wmi
# from pypsexec.client import Client

log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'log.txt')

logging.basicConfig(filename=log_file, encoding='utf-8', level=logging.DEBUG, format='%(asctime)s %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p')

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler(filename=log_file, mode='a')
handler = logging.StreamHandler(sys.stderr)
handler.setFormatter(logging.Formatter('%(asctime)s|[%(levelname)s] %(message)s'))
logger.addHandler(handler)

# create console handler and set level to debug
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
# logger.addHandler(ch)

plexName = "Plex Media Server.exe"
plex_server = '192.168.8.100'

chats = {}
chats["rene"] = {
                        "bot" :   {   
                            "name" : "Plex Butler", 
                            "token" : "5104227651:AAHaN-7m1iWPvf-g3c5vDVIRZ0WtnR45gm0" }, 
                        "chats" : [
                            {  
                                "name" : "Plex Communications", 
                                "id" : "276818124" }] 
              }

chats["shaun"] = {
                        "bot" :   {   
                            "name" : "Plex Butler", 
                            "token" : "5104227651:AAHaN-7m1iWPvf-g3c5vDVIRZ0WtnR45gm0" }, 
                        "chats" : [
                            {  
                                "name" : "Plex Communications", 
                                "id" : "-1001647957502" }] 
              }

def log(type, message):
    if type == logging.DEBUG:
        logger.debug(message)
        return message
    elif type == logging.INFO:
        logger.info(message)
        return message
    elif type == logging.ERROR:
        logger.error(message)
        return message
    elif type == logging.WARN or type == logging.WARNING:
        logger.warn(message)
        return message
    elif type == logging.FATAL:
        logger.fatal(message)
        return message
    return message

def killTask (process_name):
    try: #taskkill /f /t /im Plex*
        # killed = os.system(f'taskkill /f /t /im "{process_name}.exe"')
        # This variable ti would be used
        # as a parity and counter for the
        # terminating processes
        ti = 0
        
        # This variable stores the name
        # of the process we are terminating
        # The extension should also be
        # included in the name
        name = plexName
        
        # Initializing the wmi object
        f = wmi.WMI()
        
        # Iterating through all the
        # running processes
        for process in f.Win32_Process():
            print(process.name)
            # Checking whether the process
            # name matches our specified name
            if process.name == name:
        
                # If the name matches,
                # terminate the process   
                process.Terminate()
            
                # This increment would acknowledge
                # about the termination of the
                # Processes, and would serve as
                # a counter of the number of processes
                # terminated under the same name
                ti += 1
        
        
        # True only if the value of
        # ti didn't get incremented
        # Therefore implying the
        # process under the given
        # name is not found
        if ti == 0:
        
            # An output to inform the
            # user about the error
            print("Process not found!!!")
    except Exception as e:
        killed = 0
    return killed

def getTasks(name):
    r = os.popen('tasklist /v').read().strip().split('\n')
    print ('# of tasks is %s' % (len(r)))
    for i in range(len(r)):
        s = r[i]
        if name in r[i]:
            print ('%s in r[i]' %(name))
            return r[i]
    return []

def send_notification(recipient, title, message, retryAttempt = 0):
    retryCount = 3
    bot = chats[recipient]['bot']
    for chat in chats[recipient]['chats']:
        log(logging.INFO, message)
        result = requests.post('http://192.168.8.100:8000/notify', json={
                        'urls': f'tgram://{bot["token"]}/{chat["id"]}',
                        'title': title,
                        'body': message
                    })
        if(result.status_code > 420):
            log(logging.INFO, result.text)
            time.sleep(10)
            log(logging.INFO, 'Retrying notification...')
            if retryAttempt < retryCount:
                send_notification(title, message, retryAttempt = retryAttempt +1)
            else:
                log(logging.WARNING, 'Retry count exceeded.  Continuing.')
            
# def send_notification(title, message, retryAttempt = 0):
#     retryCount = 3
    
#     result = requests.post('http://192.168.8.100:8000/notify', json={
#                     'urls': 'tgram://5022461051:AAHjO6VfT25und8CdEKIN1pxXagER-oN3Uk/-1001647957502',
#                     'title': title,
#                     'body': message
#                 })
#     if(result.status_code > 420):
#         log(logging.INFO, result.text)
#         time.sleep(10)
#         log(logging.INFO, 'Retrying notification...')
#         if retryAttempt < retryCount:
#             send_notification(title, message, retryAttempt = retryAttempt +1)
#         else:
#             log(logging.WARNING, 'Retry count exceeded.  Continuing.')

def startPlex():
    args = ['C:\Program Files (x86)\Plex\Plex Media Server\Plex Media Server.exe', '-noninteractive']
    subprocess.run(args) 

def isPlexAccessible():
    try:
        #wget -T 4 -t 2 --server-response --spider http://192.168.8.50:32400/?X-Plex-Token=wnosamRbzKdED9nRWoEr 2>&1 | find /i "200 OK" >>C:\plexRestartScript\logall2.txt
        result = requests.post(f'http://{plex_server}:32400/identity')
        return result.status_code == 200
    except:
        return False

def main():
    
    if isPlexAccessible() == True:     
        send_notification('shaun', 'Restart Plex', 'Killing all Plex tasks')
        killTask(plexName)
        #start "Sending Notification" /WAIT apprise -vv --title="Restart Plex" --body="Starting Plex..." \tgram://5104227651:AAHaN-7m1iWPvf-g3c5vDVIRZ0WtnR45gm0/276818124
        send_notification('shaun', 'Restart Plex', 'Starting Plex...')
        startPlex()
    else:
        send_notification('shaun', 'Restart Plex', 'Plex is running normally')
    
    # start "Sending Notification" /WAIT apprise -vv --title="Restart Plex" --body="Killing all Plex tasks" \tgram://5104227651:AAHaN-7m1iWPvf-g3c5vDVIRZ0WtnR45gm0/276818124
    # start "Sending Notification" /WAIT apprise -vv --title="Plex Restart" --body="A restart of Plex has been requested. You may experience some streaming issues while Plex is starting up again." \tgram://5104227651:AAHaN-7m1iWPvf-g3c5vDVIRZ0WtnR45gm0/-1001647957502

    
    # imgName = 'plex'

    # notResponding = 'Not Responding'

    # r = getTasks(imgName)

    # if not r:
    #     print('%s - No such process' % (imgName)) 

    # elif 'Not Responding' in r:
    #     print('%s is Not responding' % (imgName))
        
    # else:
    #     print('%s is Running or Unknown' % (imgName))
    # running_processes = os.popen('tasklist').readlines()
    # print(running_processes)
    #if b'notepad.exe' not in [blah]:
    #    subprocess.Popen('notepad.exe')
    #pkill("")
   
if __name__ == '__main__':
    main()