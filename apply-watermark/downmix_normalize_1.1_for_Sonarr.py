import subprocess
import os
import sys
import logging
import configparser
from pathlib import Path
import pathlib
import json
import re
from subprocess import Popen, PIPE
import requests
import time
import shutil
import hashlib
from sys import exit


# As you can see, this is pretty much identical to your code
from argparse import ArgumentParser

# config_path = pathlib.Path(__file__).parent.absolute() / "config.ini"
config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.ini')

config = configparser.ConfigParser()
config.read(config_file)
downmix_filter = config['ffmpeg']['downmix_filter']
temp_folder = 'I:\\temp\\'
TEMP_FOLDER = 'I:\\temp\\'


compression_values = config['audio']['compression_filter_values']

check_md5 = False
notification_retry_count = 1
notification_retry_delay = 2

log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'for-sonarr.txt')

logging.basicConfig(filename=log_file, encoding='utf-8', level=logging.DEBUG, format='%(asctime)s  %(levelname)s:  %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p')

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

input_i = -16
input_tp = -1.5
input_lra = 11
regexp = re.compile('.*\.(mp4|avi|mov|mkv|divx|xvid|flv|webm|m2ts|m1v|m2v|ogm|ogv|wmv)$')
regexpTmp = re.compile('.*\.ffprocess_tmp\.mkv$')
fileNumber = 0 
file_message = []

file = ''
SONARR_FILE_PATH = ''
FILE_NAME_AND_EXTENSION = ''
FILE_NAME = ''
FILE_EXTENSION = ''
FILE_DIRECTORY_PATH = ''


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
        logger.warning(message)
        return message
    elif type == logging.FATAL:
        logger.fatal(message)
        return message
    return message

def getFileDetails(filepath):
    cmd = ['ffprobe', '-show_format', '-show_streams', '-loglevel', 'quiet', '-print_format', 'json', filepath]
    
    result = subprocess.check_output(cmd)
    data = json.loads(result.decode("utf-8"))
    return data

def getLoudNormValues(file):
    send_notification(file, log(logging.INFO, 'Retrieving loudnorm values...'))
    filter_cmd = 'loudnorm=I=-23:TP=-2:LRA=15:linear=true:print_format=json'
    cmd = ['ffmpeg', '-i', f'"{file}"']
    cmd.append('-af')
    cmd.append(filter_cmd)
    cmd.append('-f')
    cmd.append('null')
    cmd.append('-')
    
    #info = subprocess.run(cmd, capture_output=True, text=True).stdout.strip()
    # res = run_script(str.join(' ', cmd))
    first_step_output = subprocess.run(str.join(' ', cmd), shell=True,stderr=subprocess.PIPE)
    if first_step_output.returncode == 0:
        output = json.loads("{" + first_step_output.stderr.decode().split("{")[1])
        logging.debug(output)
        return output
    return None

def getFilename(file):
    filename = file
    if os.path.isfile(file):
        filepath = SONARR_FILE_PATH
        filename, file_extension = os.path.splitext(filepath)
        f1, f2 = os.path.split(filename)
    
    return f2

def getFilePath(file):
    filePath = file
    if os.path.isfile(file):
        filePath = SONARR_FILE_PATH
    
    return filePath

def getTempFilePath(file, tempFilename):
    if sys.platform == "win32":
        TEMP_FOLDER = config['conversion']['temp_folder_win']
    elif sys.platform == "darwin":
        TEMP_FOLDER = config['conversion']['temp_folder_mac']
    
    log(logging.DEBUG, f'Temp folder is: {TEMP_FOLDER}')
    tmp_location = os.path.join(TEMP_FOLDER, f'{FILE_NAME}{tempFilename}')
    log(logging.INFO, f'Using {tmp_location} as temp file')
    return tmp_location

def run_script(script):
    logging.debug("Running scripts.")
    try:
        command = run_script_command(script)
        logging.info("Running script '%s'." % (script))
        stdout, stderr = command.communicate()
        logging.debug("Stdout: %s." % stdout)
        logging.debug("Stderr: %s." % stderr)
        status = command.wait()
        return stdout
    except:
        logging.exception("Failed to execute script %s." % script)

def run_script_command(script):
    return Popen([str(script)], shell=True, stdin=PIPE, stdout=PIPE, stderr=PIPE,close_fds=(os.name != 'nt'))

def getStreamInfo(file):
    log(logging.DEBUG, f'getStreamInfo')
    info = {}
    info['audio'] = []
    info['video'] = []
    cmd = ['ffprobe', '-show_format', '-show_streams', '-loglevel', 'quiet', '-print_format', 'json', file]
    try:
        result = subprocess.check_output(cmd)
        data = json.loads(result.decode("utf-8"))
        for stream in data['streams']:
            if stream['codec_type'] == 'audio':
                info['audio'].append(stream)
            elif stream['codec_type'] == 'video':
                info['video'].append(stream)
        return info

    except Exception as e:
        log(logging.FATAL, f'Error while retrieving stream information.  {str(e)}')
        return info

def removeAdditionalAudioStreams(filepath):
    log(logging.DEBUG, f'removeAdditionalAudioStreams')
    filename, file_extension = os.path.splitext(filepath)
    
    send_notification(filename, log(logging.INFO, f'Removing additional audio streams...'))
    response = []
    cmd = ['ffprobe', '-show_format', '-show_streams', '-loglevel', 'quiet', '-print_format', 'json', filepath]

    ffmpegCmd = ['ffmpeg', '-v', 'quiet', '-stats', '-hide_banner', '-y', '-i', filepath]
    ffmpegCmd.append("-map")
    ffmpegCmd.append("0")
    reconvert = False

    try:
        result = subprocess.check_output(cmd)
        data = json.loads(result.decode("utf-8"))

        i = 0
        audioStream = 0
        videoStream = 0
        subtitleStream = 0
        totalAudioStreams = 0
        hasSurroundAudio = False
        audioStreams = []
        
        for stream in data['streams']:
            if stream['codec_type'] == 'audio':
                audioStreams.append(stream)
                totalAudioStreams += 1
                
                if int(stream['channels']) > 2:
                    hasSurroundAudio = True

        streamsRemaining = totalAudioStreams
        if totalAudioStreams == 1:
            title = ''
            if 'title' in audioStreams[0]['tags']:
                title = audioStreams[0]['tags']['title']
                
            response.append(log(logging.INFO, f'File only has 1 audio stream: \n\tCodec: {audioStreams[0]["codec_name"]}\n\tChannels: {audioStreams[0]["channels"]}\n\tTitle: {title}'))
            return response
        
        response.append(log(logging.INFO, f'File has {totalAudioStreams} audio streams:'))
        for stream in data['streams']:
            if stream['codec_type'] == 'audio':
                if streamsRemaining > 1:
                    if 'title' in stream['tags']:
                        # Remove the normalized stream
                        if 'Normalized' in stream['tags']['title']:
                            msg = f'#{fileNumber}) Removing Normalized audio: \n\t\tTrack {audioStream + 1} of {totalAudioStreams}, \n\t\tCodec: {stream["codec_name"]}, \n\t\tTitle: {stream["tags"]["title"]}'
                            response.append(log(logging.INFO, msg))
                            print(msg)
                            ffmpegCmd.append("-map")
                            ffmpegCmd.append("-0:a:%d" % audioStream)
                            reconvert = True
                            streamsRemaining-=1
                        elif totalAudioStreams > 1 and hasSurroundAudio and int(stream['channels']) == 2:  # Remove the downmixed stream
                            msg = f'#{fileNumber}) Removing downmixed audio: \n\t\tTrack {audioStream + 1} of {totalAudioStreams}, \n\t\tCodec: {stream["codec_name"]}, \n\t\tTitle: {stream["tags"]["title"]}'
                            response.append(log(logging.INFO, msg))
                            print(msg)
                            logging.info(msg)
                            ffmpegCmd.append("-map")
                            ffmpegCmd.append("-0:a:%d" % audioStream)
                            reconvert = True
                            streamsRemaining-=1
                        elif totalAudioStreams > 1 and int(stream['disposition']['default']) == 1: #
                            msg = f'#{fileNumber}) Removing default audio: \n\t\tTrack {audioStream + 1} of {totalAudioStreams}, \n\t\tCodec: {stream["codec_name"]}, \n\t\tTitle: {stream["tags"]["title"]}'
                            response.append(log(logging.INFO, msg))
                            print(msg)
                            ffmpegCmd.append("-map")
                            ffmpegCmd.append("-0:a:%d" % audioStream)
                            reconvert = True
                            streamsRemaining-=1
                        elif '(' in stream['tags']['title']: #stream['codec_name'] == 'ac3' and audioStream + 1 >= streamsRemaining:
                            msg = f'#{fileNumber}) Removing additional stream:\n\t\tTrack {audioStream + 1} of {totalAudioStreams}, \n\t\tCodec: {stream["codec_name"]}, \n\t\tTitle: {stream["tags"]["title"]}'
                            response.append(log(logging.INFO, msg))
                            print(msg)
                            logging.info(msg)
                            ffmpegCmd.append("-map_metadata")
                            ffmpegCmd.append('-1')
                            reconvert = True
                            streamsRemaining-=1
                        elif streamsRemaining > 1:
                            msg = f'#{fileNumber}) Removing additional stream: \n\t\tTrack {audioStream + 1} of {totalAudioStreams}, \n\t\tCodec: {stream["codec_name"]}, \n\t\tTitle: {stream["tags"]["title"]}'
                            response.append(log(logging.INFO, msg))
                            print(msg)
                            logging.info(msg)
                            ffmpegCmd.append("-map")
                            ffmpegCmd.append("-0:a:%d" % audioStream)
                            reconvert = True
                            streamsRemaining-=1
                        else:
                            msg = f'#{fileNumber}) Keeping stream: \n\t\tTrack {audioStream + 1} of {totalAudioStreams}, \n\t\tCodec: {stream["codec_name"]}, \n\t\tTitle: {stream["tags"]["title"]}'
                            response.append(log(logging.INFO, msg))
                            print(msg)
                            continue
                else:
                    msg = f'#{fileNumber}) Keeping stream: \n\t\tTrack {audioStream + 1} of {totalAudioStreams}, \n\t\tCodec: {stream["codec_name"]}, \n\t\tTitle: {stream["tags"]["title"]}'
                    response.append(log(logging.INFO, msg))
                    print(msg) 
                    
                audioStream += 1
                subtitleStream += 1

            i += 1

        if reconvert is True:# and audioStream > 1:
            ffmpegCmd.append("-c")
            ffmpegCmd.append("copy")
            
            cmd = ffmpegCmd

            file_path, file_name_with_extension = os.path.split(file)
            filename, file_extension = os.path.splitext(file_name_with_extension)
            # filename, file_extension = os.path.splitext(filepath)
            # filepathTmp = os.path.join(file_path, filename + ".ffprocess_tmp.mkv")
            filepathTmp = getTempFilePath(file, '.ffprocess_tmp.mkv')
            filepathNew = getTempFilePath(file, '.mkv')
            # filepathNew = os.path.join(file_path, filename + ".mkv")
            cmd.append(filepathTmp)

            logging.debug("Running cmd: %s" % cmd)
            response.append('FFMPEG Command: ' + str.join(' ', cmd))
            exitcode = run_command(cmd)
            response.append(f'Exit code: {exitcode}')
            
            if exitcode == 0:
                logging.info("Converting successfully, removing old stuff...")

                # os.remove(filepath)
                os.rename(filepath, filepath + '.original')
                response.append(log(logging.INFO, f'Renamed {filepath} to {filepath}.original'))
                
                os.rename(filepathTmp, filepathNew)
                response.append(log(logging.INFO, f'Renamed {filepathTmp} to {filepathNew}'))

                logging.info("Removing of audio tracks complete.")
                response.append("Removing of audio tracks complete.")
            else:
                logging.error("Converting failed, continuing...")
                response.append("Removing of audio tracks FAILED.")

        # else:
        #     logging.info("File is already good, nothing to do...")

    except (subprocess.CalledProcessError, KeyError):
        logging.error("Couldn't check file %s, continuing..." % filepath)
        response.append(f'Conversion of file {filepath} failed.')
        return None

def run_command(command):
    send_notification(file, log(logging.INFO, f'Running command:\n{str.join(" ", command)}'))
    process = subprocess.Popen(command, stdout=subprocess.PIPE)
    while True:
        output = process.stdout.readline()
        if output:
            print(output.strip())
        if process.poll() is not None:
            break

    return process.wait()



def delete(file):
    try:
        file_message.append(log(logging.DEBUG, f'Attempting to delete "{file}"...'))
        os.remove(file)
        file_message.append(log(logging.DEBUG, f'Successfully deleted "{file}"'))
        return True
    except Exception as e:
        file_message.append(log(logging.FATAL, f'Unable to delete file "{file}". {e}'))
        return False
    
def rename(oldname, newname):
    try:
        old_filepath = os.path.join(FILE_DIRECTORY_PATH, oldname)
        old_filename, file_extension = os.path.splitext(old_filepath)
        new_filepath = os.path.join(FILE_DIRECTORY_PATH, newname)
        new_filename, file_extension = os.path.splitext(new_filepath)
        file_message.append(log(logging.DEBUG, f'Attempting to rename "{oldname}" to {newname}...'))
        os.rename(oldname, newname)
        file_message.append(log(logging.DEBUG, f'Successfully renamed "{oldname}" to "{newname}"'))
        return True
    except Exception as e:
        file_message.append(log(logging.FATAL, f'Unable to rename file "{oldname}" to "{newname}". {e}'))
        return False
    
def apply_compression(file, channels):
    send_notification(file, log(logging.INFO, f'Applying compression.\n\tDownmix:{channels} channels'))
    
    response = {'success' : True, 'data': {}}
    output_file = getTempFilePath(file, '.wav') #f'{file}-ffmpeg.wav'
    response['data']['file'] = output_file
    response['data']['tags'] = []
    
    try:
        cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", file, '-af']
        audio_filter = ''
        if config.getboolean('audio', 'apply_compression_filter') == True:
            audio_filter = f'compand={compression_values}' # 'compand=attacks=0:points=-80/-90|-45/-45|-27/-25|0/-7|20/-7'
            
        if config.getboolean('audio', 'downmix_audio') == True and channels > 2: #downmix == True:
            downmix_filter = config['audio'][f'downmix_{channels}ch_filter']
            #audio_filter = f'pan=stereo|FL=1.0*FL+0.707*FC+0.707*SL+0.707*LFE|FR=1.0*FR+0.707*FC+0.707*SR+0.707*LFE,{audio_filter}'
            audio_filter = f'{downmix_filter},{audio_filter}'
            file_message.append(log(logging.INFO, f'Downmixing {str(channels)} and extracting WAV'))
            response['data']['tags'].append('downmixed')
        else:
            logger.info("Extracting WAV")
        #     subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", file, "-af", "compand=attacks=0:points=-80/-90|-45/-45|-27/-25|0/-7|20/-7", "-vn", file + "-ffmpeg.wav"])
        #     tags.append('compand')
        #     tags.append('dynaudnorm')  
        
        cmd.append(audio_filter)
        cmd.append('-vn')
        cmd.append(output_file)
        response['data']['command'] = str.join(' ', cmd)
        run_command(cmd)
        response['data']['tags'].append('compand')
        response['data']['file'] = output_file
        return response
    except Exception as e:
        file_message.append(log(logging.FATAL, f'Unable to apply compression to "{file}". {e}'))
        response['success'] = False
        return response


def apply_loudnorm(file):
    send_notification(file, f'Applying loudnorm.')
    response = {'success' : True, 'data': {}}
    output_file = getTempFilePath(file, '_norm.wav')
    response['data']['file'] = output_file
    response['data']['tags'] = []
    try:
        cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", file, '-af']
        loudnorm_values = getLoudNormValues(file)
        loudnorm_params = f"loudnorm=I={str(input_i)}:TP={str(input_tp)}:LRA={str(input_lra)}:measured_I={loudnorm_values['input_i']}:measured_LRA={loudnorm_values['input_lra']}:measured_TP={loudnorm_values['input_tp']}:measured_thresh={loudnorm_values['input_thresh']}:offset={loudnorm_values['target_offset']}:linear=true:print_format=summary"
        file_message.append(log(logging.INFO, loudnorm_params))
        cmd.append(loudnorm_params)
        cmd.append('-vn')
        cmd.append(output_file)
        # subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", file, "-af", loudnorm_params, "-vn", file + "-ffmpeg_norm.wav"])
        response['data']['command'] = str.join(' ', cmd)
        log(logging.INFO, 'Applying loudnorm')
        run_command(cmd)
        response['data']['tags'].append('loudnorm')
        if(delete(file)):
            if(rename(output_file, file)):
                response['data']['file'] = file
        return response
    except Exception as e:
        file_message.append(log(logging.FATAL, f'Unable to apply loudnorm to "{file}". {e}'))
        response['success'] = False
        response['message'] = f'Unable to apply loudnorm to "{file}". {e}'
        return response
    
def convert_audio(file):
    send_notification(file, f'Converting audio to aac')
    response = {'success' : True, 'data': {}}
    # output_file = f'{file}-aac.m4a'
    output_file = getTempFilePath(file, '.m4a')
    response['data']['file'] = output_file
    response['data']['tags'] = []
    try:
        logger.info("Converting to AAC")
        # convert wav to aac using qaac
        if sys.platform == "win32":
            subprocess.run(["qaac64", file, "-c", "0", "-o", output_file])
        elif sys.platform == "darwin":
            subprocess.run(["afconvert", "-q", "127", "-s", "0", "-b" , "320000", "-d", "aac", file, output_file])
            # subprocess.run(["afconvert", "-q", "127", "-s", "3", "--quality", "2", "-d", "aach", compresses_audio_file, file + "-aac.m4a"])

        # delete -ffmpeg.wav file
        logging.debug('Deleting wav file')
        delete(file)
        return response
        # os.remove(loudnorm_audio_file)
    except Exception as e:
        file_message.append(log(logging.FATAL, f'Unable to convert "{file}". {e}'))
        response['success'] = False
        response['message'] = f'Unable to convert "{file}". {e}'
        return response

def merge_audio_and_video(video_file, audio_file):
    send_notification(file, f'Merging audio and video')
    response = {'success' : True, 'data': {}}
    output_file = getTempFilePath(video_file, '_temp.mkv') #f'{video_file}_temp.mkv'
    response['data']['file'] = output_file
    try:
        logger.info("Replacing Audio using mkvmerge")
        # replace audio track in original file with -qaac.m4a
        # subprocess.run(["mkvmerge", "-o", file + "_temp.mkv", file, "--no-audio", "--language", "0:eng", "--track-name", "0:Audio", file + "-aac.m4a"])
        #ffmpeg -i video.mp4 -i audio.wav -c:v copy -c:a aac -map 0:v:0 -map 1:a:0 output.mp4
        #subprocess.run(["ffmpeg", "-i", file, "-i", file + "-aac.m4a", "-c:v", "copy", "-c:a", "aac", "-map", "0:v:0", "-map", "1:a:0", file + "_temp.mkv"])
        subprocess.run(["mkvmerge", "-o", output_file, "--no-audio", video_file, audio_file])
        # delete(file)
        return response
        # os.remove(loudnorm_audio_file)
    except Exception as e:
        file_message.append(log(logging.FATAL, f'Unable to merge "{audio_file}" and "{video_file}". {e}'))
        response['success'] = False
        response['message'] = f'Unable to merge "{audio_file}" and "{video_file}". {e}'
        return response
        
def send_notification(title, message, retryAttempt = 0):
    if os.path.isfile(title):
        filepath = SONARR_FILE_PATH
        filename, file_extension = os.path.splitext(filepath)
        title = filename
    # retryCount = 1
    
    result = requests.post('http://192.168.8.100:8000/notify', json={
                    'urls': 'tgram://5022461051:AAHjO6VfT25und8CdEKIN1pxXagER-oN3Uk/-1001647957502',
                    'title': title,
                    'body': message
                })
    if(result.status_code > 420):
        log(logging.INFO, result.text)
        time.sleep(notification_retry_delay)
        log(logging.INFO, 'Retrying notification...')
        if retryAttempt < notification_retry_count:
            send_notification(title, message, retryAttempt = retryAttempt +1)
        else:
            log(logging.WARNING, 'Retry count exceeded.  Continuing.')

def replaceFile(current, new):
    result = shutil.copyfile(current, new)
    return result

def getFileMd5(file):
    md5_hash = hashlib.md5()
    hashes = []
    with open(file,"rb") as f:
    # Read and update hash in chunks of 4K
        for byte_block in iter(lambda: f.read(4096),b""):
            md5_hash.update(byte_block)
            hashes.append(md5_hash.hexdigest())
            print(md5_hash.hexdigest())
    return str.join('', hashes)

def processFile(file_path):

    # Don't process temp files
    if regexpTmp.search(FILE_NAME) is not None:
        return None
    
    # Check that we only process specific formats
    if regexp.search(file_path) is None:
        print(log(logging.warning, f'{FILE_NAME_AND_EXTENSION} is not in a format that we can process'))
        exit(1)
    
    send_notification(FILE_NAME_AND_EXTENSION, log(logging.INFO, f'Processing {FILE_NAME_AND_EXTENSION}'))
    try:
        result = removeAdditionalAudioStreams(file_path)
        if result is not None:
            file_message.append(str.join('\n', result))
            
        data = getStreamInfo(file_path)
        is_compressed = 'tags' in data['audio'][0] and 'COMPAND' in data['audio'][0]['tags']
        is_normalized = 'tags' in data['audio'][0] and 'DYNAUDNORM' in data['audio'][0]['tags']
        is_loudnorm = 'tags' in data['audio'][0] and 'LOUDNORM' in data['audio'][0]['tags']
        if is_compressed == False:
            is_compressed ='tags' in data['audio'][0] and 'title' in data['audio'][0]['tags'] and 'comp' in str.lower(data['audio'][0]['tags']['title'])
        if is_normalized == False:
            is_normalized ='tags' in data['audio'][0] and 'title' in data['audio'][0]['tags'] and 'norm' in str.lower(data['audio'][0]['tags']['title'])
        
        file_message.append(log(logging.INFO, 'File is ' + ('' if is_normalized else 'not ') + 'normalized'))
        file_message.append(log(logging.INFO, 'File is ' + ('' if is_compressed else 'not ') + 'compressed'))
        
        if is_normalized and is_compressed:
            file_message.append(log(logging.INFO, 'No need to convert audio'))
            send_notification(file_path, str.join('\n', file_message))
            exit(0)

        file_message.append(log(logging.INFO, f'Processing {FILE_NAME}'))

    except Exception as e:
        file_message.append(log(logging.FATAL, f'Could not retrieve audio details for file {FILE_NAME}. {e}'))
        send_notification(FILE_NAME, str.join('\n', file_message))

    tags = []
    channels = int(data['audio'][0]['channels'])
    codec = data['audio'][0]['codec_name']
    # extract audio to wav and apply filter if necessary
    file_message.append(log(logging.INFO, f'Audio stream has {channels} channels'))
    response = apply_compression(file_path, channels)
    if response['success']:
        channels = 2
    # if channels > 2:
    #     tags.append('downmixed')
    tags.extend(response['data']['tags'])
    # check if -ffmpeg.wav file exists
    if os.path.isfile(response['data']['file']):
        response = apply_loudnorm(response['data']['file'])
        tags.extend(response['data']['tags'])
        loudnorm_audio_file = response['data']['file']
        convert_audio_response = convert_audio(response['data']['file'])
        if convert_audio_response['success']:
            codec = 'aac'
            
        # # delete -ffmpeg.wav file
        # logging.debug('Deleting wav file')
        # delete(loudnorm_audio_file)

        logger.info("Replacing Audio using mkvmerge")
        # replace audio track in original file with -qaac.m4a
        merge_response = merge_audio_and_video(file_path, convert_audio_response['data']['file'])
        if(merge_response['success']):
            delete(convert_audio_response['data']['file'])

    temp_file = getTempFilePath(file_path, '.mkv')
    ffmpeg_cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", merge_response['data']['file']]
    audio_tags = {}
    audio_tags['title'] = 'Stereo (AAC Compressed & Normalized)'
    audio_tags['handler_name'] = 'Stereo (AAC Compressed & Normalized)'
    ffmpeg_cmd.append('-c')
    ffmpeg_cmd.append('copy')

    for tag in tags:
        audio_tags[tag] = '1'

    for audio_tag in audio_tags:
        ffmpeg_cmd.append('-metadata:s:a:0')
        ffmpeg_cmd.append(f'{audio_tag}={audio_tags[audio_tag]}')

    ffmpeg_cmd.append('-threads')
    ffmpeg_cmd.append('0')
    ffmpeg_cmd.append('-metadata:g')
    ffmpeg_cmd.append('encoding_tool=DOWNMIX_NORM_PYTHON')
    ffmpeg_cmd.append(temp_file) #file + "_temp_metadata.mkv")
    #'-threads', '0', '-metadata:g' , 'encoding_tool=SMA', file + "-ffmpeg_norm.mkv"]
    subprocess.run(ffmpeg_cmd)
    try:
        if(delete(merge_response['data']['file'])):#file + "_temp.mkv")):
            
            if check_md5: 
                newfile_md5 = getFileMd5(temp_file)
                # file_md5 = getFileMd5(file)
                replaceFile(temp_file, file_path)
                replaced_file = getFileMd5(file_path)
                
                if newfile_md5 == replaced_file:
                    delete(temp_file)
            else:
                # replaceFile(file_path, temp_file)
                replaceFile(temp_file, file_path)
                delete(temp_file)
            # if(rename(file, file + '.delete')):
            #     if(rename(file + "_temp_metadata.mkv", file)):
            #         delete(file + '.delete')
        # os.remove(file + "_temp.mkv")
    except:
        logger.error(f"error while removing file: {merge_response['data']['file']}")

    #Send a CURL POST request to https://apprise.pleximus.co.za/notify with JSON data
    requests.post('http://192.168.8.100:8000/notify', json={
        'urls': 'tgram://5022461051:AAHjO6VfT25und8CdEKIN1pxXagER-oN3Uk/-1001647957502',
        'title': 'File normalisation complete',
        'body': file_path
    })
    # send_notification(FILE_NAME, str.join('\n-----\n', file_message))    


log(logging.INFO, '======== START PROCESSING ========')

if 'sonarr_eventtype' not in os.environ:
    log(logging.DEBUG, "No Sonarr event detected.  The script will now exit.")
    print("No Sonarr event detected.  The script will now exit.")
    exit(1)

if os.environ["sonarr_eventtype"].lower() == 'test':
    log(logging.DEBUG, "Sonarr Test event detected.  Nothing to do here.")
    print("Sonarr Test event detected.  Nothing to do here.")
    exit(0)
    
    
if os.environ["sonarr_eventtype"].lower() == 'download':
    log(logging.DEBUG, "Sonarr Download event detected.  Processing file...")
    if 'sonarr_episodefile_path' in os.environ:
        log(logging.INFO, f'Sonarr passed file: {os.environ["sonarr_episodefile_path"]}')
        try:
            SONARR_FILE_PATH = os.environ['sonarr_episodefile_path']
            # FILE_NAME, FILE_EXTENSION = os.path.split(SONARR_FILE_PATH)
            FILE_DIRECTORY_PATH, FILE_NAME_AND_EXTENSION = os.path.split(SONARR_FILE_PATH)
            FILE_NAME, FILE_EXTENSION = os.path.splitext(FILE_NAME_AND_EXTENSION)
            # FILE_NAME_AND_EXTENSION = f'{FILE_NAME}.{FILE_EXTENSION}'
            # FILE_DIRECTORY_PATH = os.path.dirname(SONARR_FILE_PATH)
            log(logging.DEBUG, f'SONARR_FILE_PATH: {SONARR_FILE_PATH}')
            log(logging.DEBUG, f'FILE_NAME: {FILE_NAME}')
            log(logging.DEBUG, f'FILE_EXTENSION: {FILE_EXTENSION}')
            log(logging.DEBUG, f'FILE_NAME_AND_EXTENSION: {FILE_NAME_AND_EXTENSION}')
            log(logging.DEBUG, f'FILE_DIRECTORY_PATH: {FILE_DIRECTORY_PATH}')
            log(logging.DEBUG, f'TEMP_FOLDER: {TEMP_FOLDER}')
            
            processFile(SONARR_FILE_PATH)
            log(logging.INFO, f'Completed processing for: {FILE_NAME_AND_EXTENSION}')
            log(logging.INFO, '======== FINISHED PROCESSING ========')
            exit(0)
        except Exception as e:
            log(logging.FATAL, f'Could not process file {FILE_NAME}. {e}')
            send_notification(FILE_NAME, str.join('\n', file_message))
            exit(1)
        
        