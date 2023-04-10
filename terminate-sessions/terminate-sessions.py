import configparser
import pathlib
import requests
import sys
import os
import html
import json
import logging
import urllib


# create the log file in the working directory
log_path = os.path.join(str(pathlib.Path(__file__).parent.absolute()), str(os.path.basename(__file__).replace('.py', '.log')))
logging.basicConfig(filename=log_path, encoding='utf-8', level=logging.DEBUG, format='%(asctime)s %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p')
# create logger
logger = logging.getLogger('')
logger.setLevel(logging.DEBUG)

# create console handler and set level to debug
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)

# create formatter
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# add formatter to ch
ch.setFormatter(formatter)

# add ch to logger
logger.addHandler(ch)

config_path = pathlib.Path(__file__).parent.absolute() / "config.ini"
logger.info(f'using config: "{str(config_path)}"')
config = configparser.ConfigParser()
config.read(config_path)

# Tautulli setup
tautulli_ip = config['tautulli']['ip']
tautulli_port = config['tautulli']['port']
tautulli_api_key = config['tautulli']['api_key']
tautulli_url = f'http://{tautulli_ip}:{tautulli_port}/api/v2?apikey={tautulli_api_key}'
tautulli_url2 = f'http://{tautulli_ip}:{tautulli_port}/api/v2' #?apikey={tautulli_api_key}'

termination_message_intro = config['termination']['message_intro']
termination_reason = config['termination']['reason']

# Apprise setup
apprise_api = config['apprise']['url']
apprise_config = config['apprise']['config']

sessionTimeout = 10  # ten sec.

def build_url(base_url, path, args_dict = []):
    # Returns a list in the structure of urlparse.ParseResult
    # build_url('http://www.example.com/', '/somepage/index.html', args)
    url_parts = list(urllib.parse.urlparse(base_url))
    url_parts[2] = path
    url_parts[4] = urllib.parse.urlencode(args_dict)
    return urllib.parse.urlunparse(url_parts)

def sendMessage(title, text):
    logger.info('Sending message...')
    logger.info(f'Title: "{title}", Body: "{text}"')
    try:
        payload = {
            'tag': 'terminate-sessions',
            'title': title,
            'body': text,
            'type': 'info'
        }

        headers = {'content-type': 'application/json', 'Accept-Charset': 'UTF-8'}
        req = requests.post(
            url= build_url(apprise_api, f'/notify/{apprise_config}'),
            json = payload,
            headers=headers
        )
    except Exception as e: # work on python 3.x
        logger.error(f'Failed to send message: "{title}": {text}.')
        logger.error(str(e))

sendMessage(str(os.path.basename(__file__)), 'Starting...')

def getSessions(ssn):
    try:
        logger.info('Retrieving sessions...')
        response = ssn.get(f'{tautulli_url}&cmd=get_activity', timeout=sessionTimeout).json().get('response')
        if response is not None and response['result'] == 'success' and len(response['data']) > 0:
            return response['data']['sessions']
    except Exception as e: # work on python 3.x
        logger.error('Failed to get sessions: '+ str(e))

    return None

def terminate_session(self, session_key=None, session_id=None, message=''):
    sendMessage(f'Terminating Session {session_key}', message)
    """Call Tautulli's terminate_session api endpoint"""
    try:
        logger.info(f'Terminating session {session_key} with message "{message}"')
        payload = {}

        if session_key:
            payload['session_key'] = session_key
        elif session_id:
            payload['session_id'] = session_id

        if message:
            payload['message'] = message

        return self._call_api('terminate_session', payload)
    except Exception as e: # work on python 3.x
        logger.error(f'Failed to terminate session {session_id} with message: "{message}"')
        logger.error(str(e))

def terminateSession(ssn, session_key, message):
    try:
        logger.info(f'Terminating session {session_key} with message "{message}"')
        payload = {}
        payload['cmd'] = 'terminate_session'
        payload['apikey'] = tautulli_api_key
        payload['session_key'] = session_key
        payload['message'] = message
        #ssn.request('GET', tautulli_url, params=payload)
        #response = ssn.request('GET', tautulli_url2, params=payload)
        #print(response.content)


        response = ssn.get(f'{tautulli_url}&cmd=terminate_session&session_key={session_key}&message={message}')
        print(response)
        print(response.content)
        return response
    except Exception as e: # work on python 3.x
        logger.error(f'Failed to terminate session {session_key} with message: "{message}"')
        logger.error(str(e))

def millisecondsToTime(milliseconds):
    millis = int(milliseconds)
    seconds=(millis/1000)%60
    seconds = int(seconds)
    minutes=(millis/(1000*60))%60
    minutes = int(minutes)
    hours=(millis/(1000*60*60))%24
    hours = int(hours)

    print ("%d:%d:%d" % (hours, minutes, seconds))
    return "%dh:%dm:%ds" % (hours, minutes, seconds)

if len(sys.argv) > 1:
    termination_reason = sys.argv[1]
    print(termination_reason)
    
logger.info(f'Using reason: "{termination_reason}"')
    
ssn = requests.Session()

# with requests.Session() as c:
#     url = 'http://172.31.13.135/tpo/spp/'
#     c.get(url, headers=headers, timeout=timeout)
#     payload = {'regno': 'myregno', 'password': 'mypassword'}
#     c.post(url, data = payload, headers=headers, timeout=timeout)
#     r = c.get('http://172.31.13.135/tpo/spp/home.php', headers=headers, timeout=timeout)
#     print r.content
sessions = getSessions(ssn)
if sessions is not None and len(sessions) > 0:
    logger.info(f'Found {str(len(sessions))} sessions')
    for session in sessions:
        try:
            sessionTitle = session['grandparent_title']
            if session['media_type'] == 'episode':
                season = session['parent_media_index'].zfill(2)
                episode = session['media_index'].zfill(2)
                sessionTitle += f' - S{season}E{episode}'
                stream_progress = millisecondsToTime(session['view_offset'])
                stream_duration = millisecondsToTime(session['duration'])

                if stream_duration.startswith('0h:'):
                    stream_progress = stream_progress[3:]
                    stream_duration = stream_duration[3:]

                message = f"Hi {session['friendly_name']}.  We're sorry to interrupt you while you're watching '{sessionTitle}', you were probably just getting into it.  We need to stop your stream for a while due to the following: __reason__.  Be sure to continue watching '{sessionTitle}' from {stream_progress} when we're back online."
                # TODO
                message = message.replace('__reason__', termination_reason)

                #message = html.escape(message)
                terminateSession(ssn, session['session_key'], message)
        except Exception as e: # work on python 3.x
            logger.error(f'Failed to terminate session "{sessionTitle}"')
            logger.error(str(e))
else:
    logger.info('No sessions found to terminate')
    sendMessage('', 'No sessions to terminate')