import configparser
import pathlib
import requests
import sys
import html

config_path = pathlib.Path(__file__).parent.absolute() / "config.ini"
config = configparser.ConfigParser()
config.read(config_path)

print('Using ' + config_path)

# Tautulli setup
tautulli_ip = config['tautulli']['ip']
tautulli_port = config['tautulli']['port']
tautulli_api_key = config['tautulli']['api_key']
tautulli_url = f'http://{tautulli_ip}:{tautulli_port}/api/v2?apikey={tautulli_api_key}'
tautulli_url2 = f'http://{tautulli_ip}:{tautulli_port}/api/v2' #?apikey={tautulli_api_key}'

termination_message_intro = config['termination']['message_intro']
termination_reason = config['termination']['reason']



def getSessions(ssn):
    response = ssn.get(f'{tautulli_url}&cmd=get_activity').json().get('response')
    if response is not None and response['result'] == 'success' and hasattr(response['data'], 'sessions'):
        return response['data']['sessions']

    return None



def terminate_session(self, session_key=None, session_id=None, message=''):
    """Call Tautulli's terminate_session api endpoint"""
    payload = {}

    if session_key:
        payload['session_key'] = session_key
    elif session_id:
        payload['session_id'] = session_id

    if message:
        payload['message'] = message

    return self._call_api('terminate_session', payload)

def terminateSession(ssn, session_key, message):
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

ssn = requests.Session()
sessions = getSessions(ssn)
if sessions is not None and len(sessions) > 0:
    for session in sessions:
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
            message = message.replace('__reason__', 'reason goes here')

            #message = html.escape(message)
            terminateSession(ssn, session['session_key'], message)