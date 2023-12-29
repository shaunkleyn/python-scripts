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

# As you can see, this is pretty much identical to your code
from argparse import ArgumentParser

# config_path = pathlib.Path(__file__).parent.absolute() / "config.ini"
config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.ini')


config = configparser.ConfigParser()
config.read(config_file)
downmix_filter = config['ffmpeg']['downmix_filter']

parser = ArgumentParser()
parser.add_argument("-f", "--folder", dest="directory", help="Folder containing items to normalize")
args = parser.parse_args()
directory = args.directory

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

input_i = -16
input_tp = -1.5
input_lra = 11
regexp = re.compile('.*\.(mp4|avi|mov|mkv|divx|xvid|flv|webm|m2ts|m1v|m2v|ogm|ogv|wmv)$')
regexpTmp = re.compile('.*\.ffprocess_tmp\.mkv$')
fileNumber = 0 
file_message = []


def processFile(file):
    file_path, file_name_with_extension = os.path.split(file)
    file_name, file_extension = os.path.splitext(file_name_with_extension)
    new_file = os.path.join(file_path, f'{file_name}-new.mkv')
    original_file = os.path.join(file_path, file_name_with_extension + '.original2')
    
    ffmpeg_cmd = ['ffmpeg', '-hide_banner', '-i']
    ffmpeg_cmd.append(file)

    
    ffprobe_cmd = ['ffprobe', '-show_format', '-show_streams', '-loglevel', 'quiet', '-print_format', 'json', file]
    result = subprocess.check_output(ffprobe_cmd)
    data = json.loads(result.decode("utf-8"))
    stream_index = 0
    original_stream_index = 0
    audio_index = 0
    
    number_of_audio_tracks = 0
    number_of_normalized_tracks = 0
    number_of_surround_tracks = 0
    number_of_non_normalized_tracks = 0
    for stream in data['streams']:
        if stream['codec_type'] == 'audio':
            number_of_audio_tracks+= 1
            if int(stream['channels']) > 2:
                number_of_surround_tracks += 1
            if 'tags' in stream and 'title' in stream['tags']:
                    if 'normali' in str.lower(stream['tags']['title']):
                        number_of_normalized_tracks += 1
                        continue
            number_of_non_normalized_tracks +=1
                    
                    
    # ffmpeg -hide_banner -i /Users/shaunkleyn/Desktop/normalize-audio/test-23-06-19/3rd.Rock.from.the.Sun.S03E05.Scaredy.Dick.720p.WEB-HD.x264.170MB-Pahe.in.mkv 
    # -vcodec copy -map 0:0 -map 0:a -c copy -map -0:a:0 
    # -threads 0 -metadata:g encoding_tool=SMA -y /Users/shaunkleyn/Desktop/normalize-audio/test-23-06-19/3rd.Rock.from.the.Sun.S03E05.Scaredy.Dick.720p.WEB-HD.x264.170MB-Pahe.in-new.mkv
    video_codec = ''      
    for stream in data['streams']:
        if stream['codec_type'] == 'audio':
            filter_text = ''
            compand_cmd = 'compand=attacks=0:points=-80/-90|-45/-45|-27/-25|0/-7|20/-7,dynaudnorm=f=250:g=31'
            disposition = []
            if int(stream['channels']) > 2 or stream['codec_name'] != 'aac':
                # loudnorm_values = getLoudNormValues(file, audio_index)
                if int(stream['channels']) > 2:
                    filter_text = f'lowpass=c=LFE:f=120,pan=stereo|FL=.3FL+.21FC+.3FLC+.3SL+.3BL+.21BC+.21LFE|FR=.3FR+.21FC+.3FRC+.3SR+.3BR+.21BC+.21LFE, {compand_cmd}' 
                    disposition.append('downmixed')
                    disposition.append('compand')
            elif int(stream['channels']) == 2:
                print('already stereo')
                if 'tags' in stream and 'title' in stream['tags']:
                    if 'normali' in str.lower(stream['tags']['title']):
                        if '(' in str.lower(stream['tags']['title']):
                            print('normalised by SMA')
                            #if the original surround sound track exists then let's remove this track
                            #so that we can normalise it again
                            if number_of_non_normalized_tracks > 0:
                                ffmpeg_cmd.append(f'-map')
                                ffmpeg_cmd.append(f'-0:a:{audio_index}')
                                stream_index += 1
                                audio_index += 1
                                continue
                            
                            #check disposition to see if compression & loudnorm has been applied
                            if 'disposition' in stream:
                                if 'compand' in stream['disposition']:
                                    print('already compressed')
                                else:
                                    print('apply compression')
                                    disposition.append('compand')
                                    filter_text = compand_cmd
                                    
                                if 'loudnorm' in stream['disposition']:
                                    print('already applied loudnorm')
                                else:
                                    print('apply loudnorm')
                        else:
                            print('normalised by something else')
                            disposition.append('compand')
                            #apply compression & loudnorm
                            filter_text = compand_cmd
                    else:
                        print('not normalised')
                        disposition.append('compand')
                        #apply compression & loudnorm
                        filter_text = compand_cmd
                else:
                    print('no title')
                    disposition.append('compand')
                    #apply compression & loudnorm
                    filter_text = compand_cmd
                    
            ffmpeg_cmd.append(f'-c:a')
            # ffmpeg_cmd.append(f'-c:a:{audio_index}')
            ffmpeg_cmd.append(f'copy')
            # ffmpeg_cmd.append(f'libfdk_aac')
            ffmpeg_cmd.append(f'-map')
            ffmpeg_cmd.append(f'0:a:{audio_index}')
            # ffmpeg_cmd.append(f'0:{original_stream_index}')
            # ffmpeg_cmd.append(f'-ac:a:{audio_index}')
            # ffmpeg_cmd.append(f'2')
            # ffmpeg_cmd.append(f'-b:a:{audio_index}')
            # ffmpeg_cmd.append(f'256k')
            
            ffmpeg_cmd.append(f'-metadata:s:a:{audio_index}')
            ffmpeg_cmd.append(f'BPS=256000')
            
            ffmpeg_cmd.append(f'-metadata:s:a:{audio_index}')
            ffmpeg_cmd.append(f'BPS-eng=256000')
            #-metadata:s:a:0 BPS=256000 -metadata:s:a:0 BPS-eng=256000
            
            if filter_text != '':
                ffmpeg_cmd.append(f'-filter:a:{audio_index}')
                ffmpeg_cmd.append(f'"{filter_text}"')
            
            ffmpeg_cmd.append(f'-metadata:s:a:{audio_index}')
            ffmpeg_cmd.append(f'"title=Stereo ({str.upper(stream["codec_name"])} Normalized) NEW"')
            
            ffmpeg_cmd.append(f'-metadata:s:a:{audio_index}')
            ffmpeg_cmd.append(f'"title=Stereo ({str.upper(stream["codec_name"])} Normalized) NEW"')
            
            ffmpeg_cmd.append(f'-metadata:s:a:{audio_index}')
            ffmpeg_cmd.append('language=eng')
            
            if len(disposition) > 0:
                ffmpeg_cmd.append(f'-disposition:a:{audio_index}')
                ffmpeg_cmd.append(f'+{str.join("-", disposition)}')
            
            stream_index += 1
            audio_index += 1
        elif stream['codec_type'] == 'video':
            print(f'stream {stream_index} is video')
            ffmpeg_cmd.append('-vcodec')
            ffmpeg_cmd.append('copy')
            ffmpeg_cmd.append('-map')
            ffmpeg_cmd.append(f'0:{original_stream_index}')
            video_codec = stream['codec_name']
            stream_index += 1
        elif stream['codec_type'] == 'subtitle':
            print(f'stream {stream_index} is subtitle')
        else:
            print(f"stream {stream_index} is {stream['codec_type']}")
        original_stream_index += 1
        
    ffmpeg_cmd.append('-threads')
    ffmpeg_cmd.append('0')
    
    ffmpeg_cmd.append('-metadata:g')
    ffmpeg_cmd.append('encoding_tool=SMA')
    
    
    if video_codec in ['x265', 'h265', 'hevc']:
        ffmpeg_cmd.append('-tag:v')
        ffmpeg_cmd.append('hvc1')
    
    ffmpeg_cmd.append('-y')
    
    ffmpeg_cmd.append(new_file)
    # ffmpeg_cmd.append(f"lowpass=c=LFE:f=120,pan=stereo|FL=.3FL+.21FC+.3FLC+.3SL+.3BL+.21BC+.21LFE|FR=.3FR+.21FC+.3FRC+.3SR+.3BR+.21BC+.21LFE,compand=attacks=0:points=-80/-90|-45/-45|-27/-25|0/-7|20/-7,dynaudnorm=f=250:g=31")
    cmd = str.join(' ', ffmpeg_cmd)
    print(cmd)
    first_step_output = subprocess.run(cmd, shell=True,stderr=subprocess.PIPE)
    if first_step_output.returncode == 0:
        output = json.loads("{" + first_step_output.stderr.decode().split("{")[1])
        return output
    else: 
        print(first_step_output.stderr)
        #libfdk_aac -map 0:1 -ac:a:0 2 -b:a:0 320k     

def getFileDetails(filepath):
    cmd = ['ffprobe', '-show_format', '-show_streams', '-loglevel', 'quiet', '-print_format', 'json', filepath]
    
    result = subprocess.check_output(cmd)
    data = json.loads(result.decode("utf-8"))
    return data

def getLoudNormValues(file):
    send_notification(file, f'Getting loudnorm values...')
    log(logging.INFO, 'Retrieving loudnorm values...')
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
    info = {}
    info['audio'] = []
    info['video'] = []
    cmd = ['ffprobe', '-show_format', '-show_streams', '-loglevel', 'quiet', '-print_format', 'json', file]
    try:
        # res = run_script(str.join(' ', cmd))
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

def removeAdditionalAudioStreams(filename):
    fileNumber = 0
    if regexpTmp.search(filename) is not None:
        return None

    if regexp.search(filename) is not None:
        send_notification(filename, f'Removing additional audio streams...')
        response = []
        fileNumber+=1
        filepath = os.path.join(root, filename)
        filename, file_extension = os.path.splitext(filepath)
        logging.info(f"#{fileNumber}) Checking file: {filename}")

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
                    
                response.append(f'File only has 1 audio stream: \n\tCodec: {audioStreams[0]["codec_name"]}\n\tChannels: {audioStreams[0]["channels"]}\n\tTitle: {title}')
                return response
            
            print(f'#{fileNumber}) {totalAudioStreams} audio streams')
            response.append(f'File has {totalAudioStreams} audio streams:')
            for stream in data['streams']:
                if stream['codec_type'] == 'audio':
                    if streamsRemaining > 1:
                        if 'title' in stream['tags']:
                            # Remove the normalized stream
                            if 'Normalized' in stream['tags']['title']:
                                msg = f'#{fileNumber}) Removing Normalized audio: \n\t\tTrack {audioStream + 1} of {totalAudioStreams}, \n\t\tCodec: {stream["codec_name"]}, \n\t\tTitle: {stream["tags"]["title"]}'
                                response.append(msg)
                                print(msg)
                                ffmpegCmd.append("-map")
                                ffmpegCmd.append("-0:a:%d" % audioStream)
                                reconvert = True
                                streamsRemaining-=1
                            elif totalAudioStreams > 1 and hasSurroundAudio and int(stream['channels']) == 2:  # Remove the downmixed stream
                                msg = f'#{fileNumber}) Removing downmixed audio: \n\t\tTrack {audioStream + 1} of {totalAudioStreams}, \n\t\tCodec: {stream["codec_name"]}, \n\t\tTitle: {stream["tags"]["title"]}'
                                response.append(msg)
                                print(msg)
                                ffmpegCmd.append("-map")
                                ffmpegCmd.append("-0:a:%d" % audioStream)
                                reconvert = True
                                streamsRemaining-=1
                            elif totalAudioStreams > 1 and int(stream['disposition']['default']) == 1: #
                                msg = f'#{fileNumber}) Removing default audio: \n\t\tTrack {audioStream + 1} of {totalAudioStreams}, \n\t\tCodec: {stream["codec_name"]}, \n\t\tTitle: {stream["tags"]["title"]}'
                                response.append(msg)
                                print(msg)
                                ffmpegCmd.append("-map")
                                ffmpegCmd.append("-0:a:%d" % audioStream)
                                reconvert = True
                                streamsRemaining-=1
                            elif '(' in stream['tags']['title']: #stream['codec_name'] == 'ac3' and audioStream + 1 >= streamsRemaining:
                                msg = f'#{fileNumber}) Removing additional stream:\n\t\tTrack {audioStream + 1} of {totalAudioStreams}, \n\t\tCodec: {stream["codec_name"]}, \n\t\tTitle: {stream["tags"]["title"]}'
                                response.append(msg)
                                print(msg)
                                ffmpegCmd.append("-map_metadata")
                                ffmpegCmd.append('-1')
                                reconvert = True
                                streamsRemaining-=1
                            elif streamsRemaining > 1:
                                msg = f'#{fileNumber}) Removing additional stream: \n\t\tTrack {audioStream + 1} of {totalAudioStreams}, \n\t\tCodec: {stream["codec_name"]}, \n\t\tTitle: {stream["tags"]["title"]}'
                                response.append(msg)
                                print(msg)
                                ffmpegCmd.append("-map")
                                ffmpegCmd.append("-0:a:%d" % audioStream)
                                reconvert = True
                                streamsRemaining-=1
                            else:
                                msg = f'#{fileNumber}) Keeping stream: \n\t\tTrack {audioStream + 1} of {totalAudioStreams}, \n\t\tCodec: {stream["codec_name"]}, \n\t\tTitle: {stream["tags"]["title"]}'
                                response.append(msg)
                                print(msg)
                                continue
                    else:
                        msg = f'#{fileNumber}) Keeping stream: \n\t\tTrack {audioStream + 1} of {totalAudioStreams}, \n\t\tCodec: {stream["codec_name"]}, \n\t\tTitle: {stream["tags"]["title"]}'
                        response.append(msg)
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
                filepathTmp = os.path.join(file_path, filename + ".ffprocess_tmp.mkv")
                filepathNew = os.path.join(file_path, filename + ".mkv")
                cmd.append(filepathTmp)

                logging.debug("Running cmd: %s" % cmd)
                response.append('FFMPEG Command: ' + str.join(' ', cmd))
                exitcode = run_command(cmd)
                response.append(f'Exit code: {exitcode}')
                
                if exitcode == 0:
                    logging.info("Converting successfully, removing old stuff...")

                    # os.remove(filepath)
                    os.rename(filepath, filepath + '.original2')
                    response.append(f'Renamed {filepath} to {filepath}.original2')
                    
                    os.rename(filepathTmp, filepathNew)
                    response.append(f'Renamed {filepathTmp} to {filepathNew}')

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

# def getLoudNormValues(file, stream_index):
#     filter_cmd = 'loudnorm=I=-23:TP=-2:LRA=15:linear=true:print_format=json'
#     cmd = ['ffmpeg', '-hide_banner', '-i', file]
#     cmd.append("-map")
#     cmd.append(f'0:a:{stream_index}')
#     cmd.append('-af')
#     cmd.append(filter_cmd)
#     cmd.append('-f')
#     cmd.append('null')
#     cmd.append('-')
#     first_step_output = subprocess.run(str.join(' ', cmd), shell=True,stderr=subprocess.PIPE)
#     if first_step_output.returncode == 0:
#         output = json.loads("{" + first_step_output.stderr.decode().split("{")[1])
#         return output
#     return None

def run_command(command):
    send_notification(file, f'Running command:\n{str.join(" ", command)}')
    process = subprocess.Popen(command, stdout=subprocess.PIPE)
    while True:
        output = process.stdout.readline()
        if output:
            print(output.strip())
        if process.poll() is not None:
            break

    return process.wait()

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

def delete(file):
    try:
        filepath = os.path.join(root, file)
        filename, file_extension = os.path.splitext(filepath)
        file_message.append(log(logging.DEBUG, f'Attempting to delete "{filename}"...'))
        os.remove(file)
        file_message.append(log(logging.DEBUG, f'Successfully deleted "{filename}"'))
        return True
    except Exception as e:
        file_message.append(log(logging.FATAL, f'Unable to delete file "{filename}". {e}'))
        return False
    
def rename(oldname, newname):
    try:
        old_filepath = os.path.join(root, oldname)
        old_filename, file_extension = os.path.splitext(old_filepath)
        new_filepath = os.path.join(root, newname)
        new_filename, file_extension = os.path.splitext(new_filepath)
        file_message.append(log(logging.DEBUG, f'Attempting to rename "{old_filename}" to {new_filename}...'))
        os.rename(oldname, newname)
        file_message.append(log(logging.DEBUG, f'Successfully renamed "{old_filename}" to "{new_filename}"'))
        return True
    except Exception as e:
        file_message.append(log(logging.FATAL, f'Unable to rename file "{old_filename}" to "{new_filename}". {e}'))
        return False
    
def apply_compression(file, downmix):
    send_notification(file, f'Applying compression.\n\tDownmix:{downmix}')
    response = {'success' : True, 'data': {}}
    output_file = f'{file}-ffmpeg.wav'
    response['data']['file'] = output_file
    response['data']['tags'] = []
    
    try:
        cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", file, '-af']
        audio_filter = 'compand=attacks=0:points=-80/-90|-45/-45|-27/-25|0/-7|20/-7'
        if downmix == True:
            audio_filter = f'pan=stereo|FL=1.0*FL+0.707*FC+0.707*SL+0.707*LFE|FR=1.0*FR+0.707*FC+0.707*SR+0.707*LFE,{audio_filter}'
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
    output_file = f'{file}-ffmpeg_norm.wav'
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
    output_file = f'{file}-aac.m4a'
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
    output_file = f'{video_file}_temp.mkv'
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
        filepath = os.path.join(root, title)
        filename, file_extension = os.path.splitext(filepath)
        title = filename
    retryCount = 10
    
    result = requests.post('http://192.168.8.100:8000/notify', json={
                    'urls': 'tgram://5022461051:AAHjO6VfT25und8CdEKIN1pxXagER-oN3Uk/-1001647957502',
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

# loop through all .mkv files in the current directory
# for file in os.listdir():
for root, dirs, files in os.walk(directory):
    prev_file = None
    for f in files:  
        # if len(file_message) > 0 and prev_file is not None:
            # send_notification(prev_file, str.join('\n', file_message))
        prev_file = None
        file_message = []
        try:
            file = os.path.normpath(os.path.join(root, f))
            prev_file = file
            if regexp.search(file) is not None:
                file_message.append(log(logging.INFO, f'Processing {file}'))
                send_notification(file, f'Processing {file}')
                try:
                    result = removeAdditionalAudioStreams(file)
                    if result is not None:
                        file_message.append(str.join('\n', result))
                        
                    data = getStreamInfo(file)
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
                        send_notification(file, str.join('\n', file_message))
                        continue

                    file_message.append(log(logging.INFO, f'Processing {file}'))

                except Exception as e:
                    file_message.append(log(logging.FATAL, f'Could not retrieve audio details for file {file}. {e}'))
                    send_notification(file, str.join('\n', file_message))
                    # logger.fatal(f'Could not retrieve audio details for file {file}. {e}')
                    #sys.exit(1)
                #2023-06-18 19:13:59 - MANUAL - INFO - "C:\Program Files\ffmpeg\ffmpeg.exe" 
                # -i "T:\series\The Big Bang Theory\Season 02\The.Big.Bang.Theory.S02E01.1080p.BluRay.x265.10bit.SoftSub.DigiMoviez.mkv.original" 
                # -vcodec copy -map 0:0 -metadata:s:v title=FHD -metadata:s:v handler_name=FHD 
                # -c:a:0 libfdk_aac -map 0:1 -ac:a:0 2 -b:a:0 320k -metadata:s:a:0 BPS=320000 -metadata:s:a:0 BPS-eng=320000 -filter:a:0 "lowpass=c=LFE:f=120,pan=stereo|FL=.3FL+.21FC+.3FLC+.3SL+.3BL+.21BC+.21LFE|FR=.3FR+.21FC+.3FRC+.3SR+.3BR+.21BC+.21LFE,compand=attacks=0:points=-80/-90|-45/-45|-27/-25|0/-7|20/-7,dynaudnorm=f=250:g=31,loudnorm=I=-16:LRA=11:TP=-1.5" -metadata:s:a:0 "title=Stereo (AAC Normalized)" -metadata:s:a:0 "handler_name=Stereo (AAC Normalized)" -metadata:s:a:0 language=eng -disposition:a:0 +default-dub-original-comment-lyrics-karaoke-forced-hearing_impaired-visual_impaired-captions 
                # -c:a:1 ac3 -map 0:1 -ac:a:1 2 -b:a:1 256k -metadata:s:a:1 BPS=256000 -metadata:s:a:1 BPS-eng=256000 -filter:a:1 "lowpass=c=LFE:f=120,pan=stereo|FL=.3FL+.21FC+.3FLC+.3SL+.3BL+.21BC+.21LFE|FR=.3FR+.21FC+.3FRC+.3SR+.3BR+.21BC+.21LFE,compand=attacks=0:points=-80/-90|-45/-45|-27/-25|0/-7|20/-7,dynaudnorm=f=250:g=31,loudnorm=I=-16:LRA=11:TP=-1.5" -metadata:s:a:1 "title=Stereo (AC3 Normalized)" -metadata:s:a:1 "handler_name=Stereo (AC3 Normalized)" -metadata:s:a:1 language=eng -disposition:a:1 -default-dub-original-comment-lyrics-karaoke-forced-hearing_impaired-visual_impaired-captions 
                # -threads 0 -metadata:g encoding_tool=SMA -tag:v hvc1 -y "T:\series\The Big Bang Theory\Season 02\The.Big.Bang.Theory.S02E01.1080p.BluRay.x265.10bit.SoftSub.DigiMoviez.mkv"

                tags = []
                channels = int(data['audio'][0]['channels'])
                codec = data['audio'][0]['codec_name']
                # extract audio to wav and apply filter if necessary
                file_message.append(log(logging.INFO, f'Audio stream has {channels} channels'))
                response = apply_compression(file, channels > 2)
                if response['success']:
                    channels = 2
                # if channels > 2:
                #     tags.append('downmixed')
                tags.extend(response['data']['tags'])
                    #ffmpeg_cmd.append('-af')
                    #ffmpeg_cmd.append('lowpass=c=LFE:f=120,pan=stereo|FL=.3FL+.21FC+.3FLC+.3SL+.3BL+.21BC+.21LFE|FR=.3FR+.21FC+.3FRC+.3SR+.3BR+.21BC+.21LFE')
                #     file_message.append(log(logger.INFO, f'Downmixing {str(channels)} and extracting WAV'))
                #     # subprocess.run(["ffmpeg", "-hide_banner", "-y", "-i", file, "-af", "pan=stereo|FL=0.25*FL+FC+0.6*LFE|FR=0.25*FR+FC+0.6*LFE", "-vn", file + "-ffmpeg.wav"])
                #     subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", file, "-af", "pan=stereo|FL=1.0*FL+0.707*FC+0.707*SL+0.707*LFE|FR=1.0*FR+0.707*FC+0.707*SR+0.707*LFE,compand=attacks=0:points=-80/-90|-45/-45|-27/-25|0/-7|20/-7", "-vn", file + "-ffmpeg.wav"])
                #     run_command()
                    
                #     tags.append('downmixed')
                #     tags.append('compand')
                #     tags.append('dynaudnorm')
                #     #subprocess.run(["ffmpeg", "-hide_banner", "-y", "-i", file, "-af", downmix_filter, "-vn", file + "-ffmpeg.wav"])
                # # elif (channels == 2 and codec != "A_AAC-2"):
                # elif (channels == 2 or codec != "A_AAC-2"):
                #     logger.info("Extracting WAV")
                #     subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", file, "-af", "compand=attacks=0:points=-80/-90|-45/-45|-27/-25|0/-7|20/-7", "-vn", file + "-ffmpeg.wav"])
                #     tags.append('compand')
                #     tags.append('dynaudnorm')

                # check if -ffmpeg.wav file exists
                if os.path.isfile(response['data']['file']):
                    response = apply_loudnorm(response['data']['file'])
                    tags.extend(response['data']['tags'])
                    loudnorm_audio_file = response['data']['file']
                    # loudnorm_values = getLoudNormValues(compresses_audio_file)
                    # loudnorm_params = f"loudnorm=I={str(input_i)}:TP={str(input_tp)}:LRA={str(input_lra)}:measured_I={loudnorm_values['input_i']}:measured_LRA={loudnorm_values['input_lra']}:measured_TP={loudnorm_values['input_tp']}:measured_thresh={loudnorm_values['input_thresh']}:offset={loudnorm_values['target_offset']}:linear=true:print_format=summary"
                    # logger.info(loudnorm_params)
                    # logger.debug('Running loudnorm')
                    # subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", compresses_audio_file, "-af", loudnorm_params, "-vn", file + "-ffmpeg_norm.wav"])
                    # tags.append('loudnorm')
                    # os.remove(compresses_audio_file)
                    # os.rename(file + "-ffmpeg_norm.wav", compresses_audio_file)

                    # logger.info("Converting to AAC")
                    # # convert wav to aac using qaac
                    # if sys.platform == "win32":
                    #     subprocess.run(["qaac64", loudnorm_audio_file, "-c", "0", "-o", file + "-aac.m4a"])
                    # elif sys.platform == "darwin":
                    #     subprocess.run(["afconvert", "-q", "127", "-s", "0", "-b" , "320000", "-d", "aac", loudnorm_audio_file, file + "-aac.m4a"])
                    #     # subprocess.run(["afconvert", "-q", "127", "-s", "3", "--quality", "2", "-d", "aach", compresses_audio_file, file + "-aac.m4a"])

                    convert_audio_response = convert_audio(response['data']['file'])
                    if convert_audio_response['success']:
                        codec = 'aac'
                        
                    # delete -ffmpeg.wav file
                    logging.debug('Deleting wav file')
                    delete(loudnorm_audio_file)

                    logger.info("Replacing Audio using mkvmerge")
                    # replace audio track in original file with -qaac.m4a
                    # subprocess.run(["mkvmerge", "-o", file + "_temp.mkv", file, "--no-audio", "--language", "0:eng", "--track-name", "0:Audio", file + "-aac.m4a"])
                    #ffmpeg -i video.mp4 -i audio.wav -c:v copy -c:a aac -map 0:v:0 -map 1:a:0 output.mp4
                    #subprocess.run(["ffmpeg", "-i", file, "-i", file + "-aac.m4a", "-c:v", "copy", "-c:a", "aac", "-map", "0:v:0", "-map", "1:a:0", file + "_temp.mkv"])
                    # subprocess.run(["mkvmerge", "-o", file + "_temp.mkv", "--no-audio", file, file + "-aac.m4a"])
                    merge_response = merge_audio_and_video(file, convert_audio_response['data']['file'])
                    if(merge_response['success']):
                        delete(convert_audio_response['data']['file'])
                        # rename(merge_response['data']['file'], file)
                    # delete -aac.mp4 file
                    # logger.debug('Deleting m4a file')
                    # os.remove(file + "-aac.m4a")

                    # os.rename(file + "_temp.mkv", file)
                    # os.remove(file + ".original.mkv")
                    # try:
                    #     if(rename(file, file + ".original2")):
                    #         delete(file + ".original2")
                    #     # logger.debug(f'Renaming {file} to { file + ".original2"}')
                    #     # os.rename(file, file + ".original2")
                    #     # os.remove(file + ".original2")
                    # except Exception as e: # work on python 3.x:
                    #     logger.fatal(f'Could not delete {file + ".original2"}: {str(e)}')

                    # set audio track's title using mkvpropedit
                    # subprocess.run(["mkvpropedit", file, "--edit", "track:a1", "--set", "name=" + "Stereo (AAC Compressed & Normalized)"])
                    # channels = 2

                # check if .srt file exists
                # if os.path.isfile(file.replace(".mkv", ".srt")):
                #     logger.info("Embedding subtitles")
                #     # merge .srt file into original file
                #     subprocess.run(["mkvmerge", "-o", file + "_temp.mkv", file, file.replace(".mkv", ".srt")])
                #     # os.rename(file + "_temp.mkv", file)

                ffmpeg_cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", file + "_temp.mkv"]
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
                ffmpeg_cmd.append(file + "_temp_metadata.mkv")
                #'-threads', '0', '-metadata:g' , 'encoding_tool=SMA', file + "-ffmpeg_norm.mkv"]
                subprocess.run(ffmpeg_cmd)
                try:
                    if(delete(file + "_temp.mkv")):
                        if(rename(file, file + '.delete')):
                            if(rename(file + "_temp_metadata.mkv", file)):
                                delete(file + '.delete')
                    # os.remove(file + "_temp.mkv")
                except:
                    logger.error(f'error while removing file: {file + "_temp.mkv"}')
                #-metadata:s:a:0 "title=Stereo (AC3 Normalized)" -metadata:s:a:0 "handler_name=Stereo (AC3 Normalized)" -metadata:s:a:0 language=eng -disposition:a:0 +default-dub-original-comment-lyrics-karaoke-forced-hearing_impaired-visual_impaired-captions
#                subprocess.run(["ffmpeg", "-hide_banner", "-y", "-i", file, "-metadata:s:a:0", '"title=Stereo (AAC Compressed & Normalized)"', "-metadata:s:a:0", '"handler_name=Stereo (AAC Compressed & Normalized)"', '-threads', '0', '-metadata:g' , 'encoding_tool=SMA', file + "-ffmpeg_norm.mkv"])

                # normalize audio and update title if necessary
                # if title != "Normalized":
                #     logger.info("Normalizing audio for " + file)
                #     #subprocess.run(["ffmpeg-normalize", "-pr", "-f", file])
                #     # process = subprocess.run(["ffmpeg-normalize", "-pr", "-ar", "48000", "-c:a", "libfdk_aac", "-b:a", "192k", "-koa", "-o", file, "-f", file])
                #     process = subprocess.run(["ffmpeg-normalize", "-pr", "-ar", "48000", "-c:a", "libfdk_aac", "-b:a", "192k", "-o", file, "-f", file])
                #     #ffmpeg-normalize -v "%%~nxF" -ar 48000 -c:a aac -b:a 192k -o "%%~nF_temp%%~xF" && echo Adding NORMALIZED_AUDIO metadata && ffmpeg -v quiet -stats -hide_banner -y -i "%%~nF_temp%%~xF" -c copy -metadata NORMALIZED_AUDIO="true" "%%~nxF" && echo Deleting "%%~nF_temp%%~xF" && del "%%~nF_temp%%~xF" 2>nul
                #     if process.returncode == 0:
                #         logger.info("Command ran successfully")
                #         subprocess.run(["mkvpropedit", file, "--edit", "track:a1", "--set", "name=Normalized"])
                #     else:
                #         logger.info(f"Command failed with return code {process.returncode}")
                # else:
                #         logger.info(file + " already normalized")


                #Send a CURL POST request to https://apprise.pleximus.co.za/notify with JSON data
                requests.post('http://192.168.8.100:8000/notify', json={
                    'urls': 'tgram://5022461051:AAHjO6VfT25und8CdEKIN1pxXagER-oN3Uk/-1001647957502',
                    'title': 'File normalisation complete',
                    'body': file
                })
                send_notification(file, str.join('\n-----\n', file_message))
        except:
            logger.fatal(f'Error processing {file}')
