import configparser
import pathlib
import requests
import sys

config_path = pathlib.Path(__file__).parent.absolute() / "config.ini"
config = configparser.ConfigParser()
config.read(config_path)

# Tautulli setup
tautulli_ip = config['tautulli']['ip']
tautulli_port = config['tautulli']['port']
tautulli_api_key = config['tautulli']['api_key']
tautulli_url = f'http://{tautulli_ip}:{tautulli_port}/api/v2?apikey={tautulli_api_key}'

termination_message_intro = config['termination']['message_intro']


def getSessions(ssn):
    response = ssn.get(f'{tautulli_url}&cmd=get_activity').json().get('response')
    if response is not None and response.result == 'success':
        return response.data

    return None

def terminateSession(ssn, session_key, message):
    response = ssn.get(f'{tautulli_url}&cmd=terminate_session&session_key={session_key}&message={message}').json().get('response')
    return response


ssn = requests.Session()
sessions = getSessions(ssn)
if sessions is not None and len(sessions) > 0:
    for session in sessions:
        sessionTitle = session.grandparentTitle
        if session.libraryName == 'TV Shows':
            season = session.parentMediaIndex.zfill(2)
            episode = session.mediaIndex.zfill(2)
            sessionTitle += f'S{season}E{episode}'
            terminateSession(ssn, termination_message_intro, session.sessionKey)
