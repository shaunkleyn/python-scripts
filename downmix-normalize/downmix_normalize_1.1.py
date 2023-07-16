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

ffmpeg_cmd_base = ['ffmpeg', '-hide_banner', '-i']

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
    logging.debug('Getting loudnorm values')
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
    # res = run_script(str.join(' ', cmd))
    result = subprocess.check_output(cmd)
    data = json.loads(result.decode("utf-8"))
    for stream in data['streams']:
        if stream['codec_type'] == 'audio':
            info['audio'].append(stream)
        elif stream['codec_type'] == 'video':
            info['video'].append(stream)
                    
    return info

def removeAdditionalAudioStreams(filename):
    fileNumber = 0
    if regexpTmp.search(filename) is not None:
        return None

    if regexp.search(filename) is not None:
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
            
            for stream in data['streams']:
                if stream['codec_type'] == 'audio':
                    totalAudioStreams += 1
                    
                    if int(stream['channels']) > 2:
                        hasSurroundAudio = True

            streamsRemaining = totalAudioStreams
            if totalAudioStreams == 1:
                return None
            
            print(f'#{fileNumber}) {totalAudioStreams} audio streams')
            for stream in data['streams']:
                if stream['codec_type'] == 'audio':
                    if streamsRemaining > 1:
                        if 'title' in stream['tags']:
                            # Remove the normalized stream
                            if 'Normalized' in stream['tags']['title']:
                                print(f'#{fileNumber}) Removing Normalized audio: Track {audioStream + 1} of {totalAudioStreams}, Codec: {stream["codec_name"]}, Title: {stream["tags"]["title"]}')
                                ffmpegCmd.append("-map")
                                ffmpegCmd.append("-0:a:%d" % audioStream)
                                reconvert = True
                                streamsRemaining-=1
                            elif totalAudioStreams > 1 and hasSurroundAudio and int(stream['channels']) == 2:  # Remove the downmixed stream
                                print(f'#{fileNumber}) Removing downmixed audio: Track {audioStream + 1} of {totalAudioStreams}, Codec: {stream["codec_name"]}, Title: {stream["tags"]["title"]}')
                                ffmpegCmd.append("-map")
                                ffmpegCmd.append("-0:a:%d" % audioStream)
                                reconvert = True
                                streamsRemaining-=1
                            elif totalAudioStreams > 1 and int(stream['disposition']['default']) == 1: #
                                print(f'#{fileNumber}) Removing default audio: Track {audioStream + 1} of {totalAudioStreams}, Codec: {stream["codec_name"]}, Title: {stream["tags"]["title"]}')
                                ffmpegCmd.append("-map")
                                ffmpegCmd.append("-0:a:%d" % audioStream)
                                reconvert = True
                                streamsRemaining-=1
                            elif '(' in stream['tags']['title']: #stream['codec_name'] == 'ac3' and audioStream + 1 >= streamsRemaining:
                                print(f'#{fileNumber}) Removing additional stream: Track {audioStream + 1} of {totalAudioStreams}, Codec: {stream["codec_name"]}, Title: {stream["tags"]["title"]}')
                                ffmpegCmd.append("-map_metadata")
                                ffmpegCmd.append('-1')
                                reconvert = True
                                streamsRemaining-=1
                            elif streamsRemaining > 1:
                                print(f'#{fileNumber}) Removing additional stream: Track {audioStream + 1} of {totalAudioStreams}, Codec: {stream["codec_name"]}, Title: {stream["tags"]["title"]}')
                                ffmpegCmd.append("-map")
                                ffmpegCmd.append("-0:a:%d" % audioStream)
                                reconvert = True
                                streamsRemaining-=1
                            else:
                                continue

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
                exitcode = run_command(cmd)

                if exitcode == 0:
                    logging.info("Converting successfully, removing old stuff...")

                    # os.remove(filepath)
                    os.rename(filepath, filepath + '.original2')
                    os.rename(filepathTmp, filepathNew)

                    logging.info("Converting finished...")
                else:
                    logging.error("Converting failed, continuing...")

            # else:
            #     logging.info("File is already good, nothing to do...")

        except (subprocess.CalledProcessError, KeyError):
            logging.error("Couldn't check file %s, continuing..." % filepath)
            return None

def run_command(command):
    process = subprocess.Popen(command, stdout=subprocess.PIPE)
    while True:
        output = process.stdout.readline()
        if output:
            print(output.strip())
        if process.poll() is not None:
            break

    return process.wait()

# loop through all .mkv files in the current directory
# for file in os.listdir():
for root, dirs, files in os.walk(directory):
    for f in files:
        file = os.path.normpath(os.path.join(root, f))
        if regexp.search(file) is not None:
            logger.info("Processing " + file)
            ffmpeg_cmd = ffmpeg_cmd_base
            
            try:
                removeAdditionalAudioStreams(file)
                data = getStreamInfo(file)
                is_normalized = False
                is_compressed = False
                has_title = False
                title = None
                has_tags = 'tags' in data['audio'][0]
                
                if has_tags:
                    has_title = 'title' in data['audio'][0]['tags']
                    is_compressed = 'COMPAND' in data['audio'][0]['tags']
                
                if has_title == True:
                    title = data['audio'][0]['tags']['title']
                    is_normalized = 'norm' in str.lower(title)
                    is_compressed = 'comp' in str.lower(title)
                
                if has_title == False or is_compressed == False:
                    is_compressed = 'tags' in data['audio'][0] and 'COMPAND' in data['audio'][0]['tags']

                if is_normalized and is_compressed:
                    continue
                    
                codec = data['audio'][0]['codec_name']
                channels = int(data['audio'][0]['channels'])

                logger.info(f'Codec: {channels}')
                logger.info(f'Channels: {channels}')
                logger.info(f'Title: {title}')
                
            except:
                logger.fatal(f'Could not retrieve audio details for file {file}')
                #sys.exit(1)
            #2023-06-18 19:13:59 - MANUAL - INFO - "C:\Program Files\ffmpeg\ffmpeg.exe" 
            # -i "T:\series\The Big Bang Theory\Season 02\The.Big.Bang.Theory.S02E01.1080p.BluRay.x265.10bit.SoftSub.DigiMoviez.mkv.original" 
            # -vcodec copy -map 0:0 -metadata:s:v title=FHD -metadata:s:v handler_name=FHD 
            # -c:a:0 libfdk_aac -map 0:1 -ac:a:0 2 -b:a:0 320k -metadata:s:a:0 BPS=320000 -metadata:s:a:0 BPS-eng=320000 -filter:a:0 "lowpass=c=LFE:f=120,pan=stereo|FL=.3FL+.21FC+.3FLC+.3SL+.3BL+.21BC+.21LFE|FR=.3FR+.21FC+.3FRC+.3SR+.3BR+.21BC+.21LFE,compand=attacks=0:points=-80/-90|-45/-45|-27/-25|0/-7|20/-7,dynaudnorm=f=250:g=31,loudnorm=I=-16:LRA=11:TP=-1.5" -metadata:s:a:0 "title=Stereo (AAC Normalized)" -metadata:s:a:0 "handler_name=Stereo (AAC Normalized)" -metadata:s:a:0 language=eng -disposition:a:0 +default-dub-original-comment-lyrics-karaoke-forced-hearing_impaired-visual_impaired-captions 
            # -c:a:1 ac3 -map 0:1 -ac:a:1 2 -b:a:1 256k -metadata:s:a:1 BPS=256000 -metadata:s:a:1 BPS-eng=256000 -filter:a:1 "lowpass=c=LFE:f=120,pan=stereo|FL=.3FL+.21FC+.3FLC+.3SL+.3BL+.21BC+.21LFE|FR=.3FR+.21FC+.3FRC+.3SR+.3BR+.21BC+.21LFE,compand=attacks=0:points=-80/-90|-45/-45|-27/-25|0/-7|20/-7,dynaudnorm=f=250:g=31,loudnorm=I=-16:LRA=11:TP=-1.5" -metadata:s:a:1 "title=Stereo (AC3 Normalized)" -metadata:s:a:1 "handler_name=Stereo (AC3 Normalized)" -metadata:s:a:1 language=eng -disposition:a:1 -default-dub-original-comment-lyrics-karaoke-forced-hearing_impaired-visual_impaired-captions 
            # -threads 0 -metadata:g encoding_tool=SMA -tag:v hvc1 -y "T:\series\The Big Bang Theory\Season 02\The.Big.Bang.Theory.S02E01.1080p.BluRay.x265.10bit.SoftSub.DigiMoviez.mkv"

            tags = []
            if is_compressed == False:
                ffmpeg_cmd.append('-af')
                
            # extract audio to wav and apply filter if necessary
            if channels > 2:
                #ffmpeg_cmd.append('-af')
                #ffmpeg_cmd.append('lowpass=c=LFE:f=120,pan=stereo|FL=.3FL+.21FC+.3FLC+.3SL+.3BL+.21BC+.21LFE|FR=.3FR+.21FC+.3FRC+.3SR+.3BR+.21BC+.21LFE')
                logger.info(f'Downmixing {str(channels)} and extracting WAV')
                # subprocess.run(["ffmpeg", "-hide_banner", "-y", "-i", file, "-af", "pan=stereo|FL=0.25*FL+FC+0.6*LFE|FR=0.25*FR+FC+0.6*LFE", "-vn", file + "-ffmpeg.wav"])
                subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", file, "-af", "pan=stereo|FL=1.0*FL+0.707*FC+0.707*SL+0.707*LFE|FR=1.0*FR+0.707*FC+0.707*SR+0.707*LFE,compand=attacks=0:points=-80/-90|-45/-45|-27/-25|0/-7|20/-7", "-vn", file + "-ffmpeg.wav"])
                tags.append('downmixed')
                tags.append('compand')
                tags.append('dynaudnorm')
                #subprocess.run(["ffmpeg", "-hide_banner", "-y", "-i", file, "-af", downmix_filter, "-vn", file + "-ffmpeg.wav"])
            # elif (channels == 2 and codec != "A_AAC-2"):
            elif (channels == 2 or codec != "A_AAC-2"):
                logger.info("Extracting WAV")
                subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", file, "-af", "compand=attacks=0:points=-80/-90|-45/-45|-27/-25|0/-7|20/-7", "-vn", file + "-ffmpeg.wav"])
                tags.append('compand')
                tags.append('dynaudnorm')
                
            # check if -ffmpeg.wav file exists
            if os.path.isfile(file + "-ffmpeg.wav"):
                loudnorm_values = getLoudNormValues(file + "-ffmpeg.wav")
                loudnorm_params = f"loudnorm=I={str(input_i)}:TP={str(input_tp)}:LRA={str(input_lra)}:measured_I={loudnorm_values['input_i']}:measured_LRA={loudnorm_values['input_lra']}:measured_TP={loudnorm_values['input_tp']}:measured_thresh={loudnorm_values['input_thresh']}:offset={loudnorm_values['target_offset']}:linear=true:print_format=summary"
                logger.info(loudnorm_params)
                logger.debug('Running loudnorm')
                subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", file + "-ffmpeg.wav", "-af", loudnorm_params, "-vn", file + "-ffmpeg_norm.wav"])
                tags.append('loudnorm')
                os.remove(file + "-ffmpeg.wav")
                os.rename(file + "-ffmpeg_norm.wav", file + "-ffmpeg.wav")

                logger.info("Converting to AAC")
                # convert wav to aac using qaac
                if sys.platform == "win32":
                    subprocess.run(["qaac64", file + "-ffmpeg.wav", "-c", "0", "-o", file + "-aac.m4a"])
                elif sys.platform == "darwin":
                    subprocess.run(["afconvert", "-q", "127", "-s", "0", "-b" , "320000", "-d", "aac", file + "-ffmpeg.wav", file + "-aac.m4a"])
                    # subprocess.run(["afconvert", "-q", "127", "-s", "3", "--quality", "2", "-d", "aach", file + "-ffmpeg.wav", file + "-aac.m4a"])
    
                # delete -ffmpeg.wav file
                logging.debug('Deleting wav file')
                os.remove(file + "-ffmpeg.wav")
    
                logger.info("Replacing Audio using mkvmerge")
                # replace audio track in original file with -qaac.m4a
                # subprocess.run(["mkvmerge", "-o", file + "_temp.mkv", file, "--no-audio", "--language", "0:eng", "--track-name", "0:Audio", file + "-aac.m4a"])
                #ffmpeg -i video.mp4 -i audio.wav -c:v copy -c:a aac -map 0:v:0 -map 1:a:0 output.mp4
                #subprocess.run(["ffmpeg", "-i", file, "-i", file + "-aac.m4a", "-c:v", "copy", "-c:a", "aac", "-map", "0:v:0", "-map", "1:a:0", file + "_temp.mkv"])
                subprocess.run(["mkvmerge", "-o", file + "_temp.mkv", "--no-audio", file, file + "-aac.m4a"])
    
                # delete -aac.mp4 file
                logger.debug('Deleting m4a file')
                os.remove(file + "-aac.m4a")
    
                logger.debug(f'Renaming {file} to { file + ".original2"}')
                os.rename(file, file + ".original2")
                # os.rename(file + "_temp.mkv", file)
                # os.remove(file + ".original.mkv")
                
                # set audio track's title using mkvpropedit
                # subprocess.run(["mkvpropedit", file, "--edit", "track:a1", "--set", "name=" + "Stereo (AAC Compressed & Normalized)"])
                codec = "A_AAC-2"
                channels = 2
            
            # check if .srt file exists
            if os.path.isfile(file.replace(".mkv", ".srt")):
                logger.info("Embedding subtitles")
                # merge .srt file into original file
                subprocess.run(["mkvmerge", "-o", file + "_temp.mkv", file, file.replace(".mkv", ".srt")])
                # os.rename(file + "_temp.mkv", file)
            
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
            ffmpeg_cmd.append(file )
            #'-threads', '0', '-metadata:g' , 'encoding_tool=SMA', file + "-ffmpeg_norm.mkv"]
            subprocess.run(ffmpeg_cmd)
            try:
                os.remove(file + "_temp.mkv")
            except:
                logger.error(f'error while removing file: {file + "_temp.mkv"}')
            #-metadata:s:a:0 "title=Stereo (AC3 Normalized)" -metadata:s:a:0 "handler_name=Stereo (AC3 Normalized)" -metadata:s:a:0 language=eng -disposition:a:0 +default-dub-original-comment-lyrics-karaoke-forced-hearing_impaired-visual_impaired-captions
#            subprocess.run(["ffmpeg", "-hide_banner", "-y", "-i", file, "-metadata:s:a:0", '"title=Stereo (AAC Compressed & Normalized)"', "-metadata:s:a:0", '"handler_name=Stereo (AAC Compressed & Normalized)"', '-threads', '0', '-metadata:g' , 'encoding_tool=SMA', file + "-ffmpeg_norm.mkv"])
            
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


            # Send a CURL POST request to https://apprise.pleximus.co.za/notify with JSON data
            # requests.post('https://apprise.pleximus.co.za/notify', json={
            #     'urls': 'tgram://5022461051:AAHjO6VfT25und8CdEKIN1pxXagER-oN3Uk/-1001647957502',
            #     'title': 'File normalisation complete',
            #     'body': file
            # })
