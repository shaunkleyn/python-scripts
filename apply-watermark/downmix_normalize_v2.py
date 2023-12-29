import subprocess
import os
import sys
import logging
import configparser
from pathlib import Path
import pathlib
import decimal
from decimal import Decimal
import shutil

# As you can see, this is pretty much identical to your code
from argparse import ArgumentParser

# config_path = pathlib.Path(__file__).parent.absolute() / "config.ini"
#config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.ini')
#
#
#config = configparser.ConfigParser()
#config.read(config_file)
#downmix_filter = config['ffmpeg']['downmix_filter']


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

class AudioTrack:
    def __init__(self, channels, codec, title, format):
        self.channels = channels
        self.codec = codec
        self.title = title
        self.format = format

    def isStereo(self):
        return int(self.channels) == 2
    
    def isSurroundSound(self):
        return int(self.channels) > 2
    
    def isNormalized(self):
        return self.title.upper().find("NORMALIZED") >= 0
    
    def isAac(self):
        return self.codec.upper().find('AAC') >= 0
    
    def requireProcessing(self):
        return not int(channels) == 2 and title.upper().find("NORMALIZED") >= 0 and codec.upper().find('AAC') >= 0


audio_extensions = {
    'A_AC3' : 'm4a',
    'AC-3' : 'm4a',
    'A_AAC-2' : 'm4a',
    'AAC LC': 'm4a',
    'AAC': 'm4a',
    'A_PCM/INT/LIT': 'wav',
    'PCM': 'wav',
    'FLAC': 'flac',
    'MP4A-40-2': 'm4a',
    'MPEG-4': 'm4a',
    'M4A': 'm4a',
    'MPEG Audio': 'mp3'
}

def getVideoFormat(file):
    #mediainfo "--Inform=Video;%Format%" Mummies.2023.1080p.WEB-DL.x264.DD5.1-Pahe.in.mkv

    video_format = subprocess.run(['mediainfo', '--Inform=Video;%Format%', file], capture_output=True, text=True).stdout.strip()
    return video_format[0]


def getWritingApplication(file):
    writing_application = subprocess.run(['mediainfo', '--Inform=General;%Encoded_Application%', file], capture_output=True, text=True).stdout.strip().split('|')
    print(writing_application)
    return writing_application

def setWritingApplication(file, writing_application):
    #mkvpropedit Mummies.2023.1080p.WEB-DL.x264.DD5.1-Pahe.in.mkv --edit info --set "writing-application=My Encoder"
    writing_application = subprocess.run(['mkvpropedit', '--edit', 'info', '--set', f'writing-application={writing_application}', file])
    
def hasSurroundSoundTrack(file):
    channels = subprocess.run(['mediainfo', '--Inform=Audio;%Channel(s)%|', file], capture_output=True, text=True).stdout.strip().split('|')
    a = AudioTrack()
    for channel in channels:
        if int(channel) > 2:
            return True
    return False

def getAudioTracks(file):
    tracks = subprocess.run(['mediainfo', '--Inform=Audio;%Channel(s)%,%CodecID%,%Title%,%Format%|', file], capture_output=True, text=True).stdout.strip().split('|')
    tracksList = []
    for track in tracks:
        if track == '':
            continue
        trackInfo = track.split(',')
        trackItem = AudioTrack(int(trackInfo[0]), trackInfo[1], trackInfo[2], trackInfo[3])
        tracksList.append(trackItem)
    
    return tracksList

def splitAudioVideo(file):
    #ffmpeg -i out.mkv -map 0:a -acodec copy audio.mp4 -map 0:v -vcodec copy onlyvideo.mkv   
    output_filenames = {
        'v' : [],
        'a' : []
    }
    
    try:
    
        filename = os.path.splitext(file)[0]
        file_extension = os.path.splitext(file)[1]
        video_extension = file_extension

        index = 0
        audio_tracks = getAudioTracks(file)
        # audio_format = subprocess.run(['mediainfo', '--Inform=Audio;%Format%', file], capture_output=True, text=True).stdout.strip()
        video_file = f'{filename}_video_only{video_extension}'
        output_filenames['v'].append(video_file)

        for audio_track in audio_tracks:
            audio_extension = audio_extensions[audio_track.format]
            audio_file = f'{filename}_audio_only_idx{index}.{audio_extension}'

            if os.path.exists(video_file) and os.path.exists(audio_file):
                output_filenames['a'].append(audio_file)
            else:
                process = subprocess.run(["ffmpeg", "-hide_banner", "-y", "-i", file, "-map", f'0:a:{index}', '-acodec', 'copy', audio_file, '-map', '0:v', '-vcodec', 'copy', video_file])
                if process.returncode == 0:
                    output_filenames['a'].append(audio_file)

            index = index + 1
                #return output_filenames
        # index = 0

        # for audio_track in audio_tracks: 
        #     audio_file = f'{filename}_audio_only_idx{index}.{audio_extension}'  
        #     process = subprocess.run(["ffmpeg", "-hide_banner", "-y", "-i", file, "-map", f'0:a:{index}', '-acodec', 'copy', audio_file, '-map', '0:v', '-vcodec', 'copy', video_file])
        #     if process.returncode == 0:
        #         output_filenames['a'].append(audio_file)

        #     index = index + 1
    except:
        print('ERROR')
        
    return output_filenames
    #ffmpeg -i out.mkv -map 0:a -acodec copy audio.mp4 -map 0:v -vcodec copy onlyvideo.mkv


def extractAudioToWav(file):
    filename = os.path.splitext(file)[0] + '.wav'
    if os.path.exists(filename):
        return filename
    #file + ".wav"
    
    #if hasSurroundSoundTrack(file) == True:
    #    subprocess.run(["ffmpeg", "-hide_banner", "-y", "-i", file, "-af", "pan=stereo|FL=1.0*FL+0.707*FC+0.707*SL+0.707*LFE|FR=1.0*FR+0.707*FC+0.707*SR+0.707*LFE", "-vn", filename])
    #else:
    subprocess.run(["ffmpeg", "-hide_banner", "-y", "-i", file, "-vn", filename])
    return filename

def downmixAudio(waveFile, channels):
    filename = os.path.splitext(file)[0] + f'-{str(channels)}ch-stereo.wav'
    if os.path.exists(filename):
        return filename
    #pan=stereo|FL=FC+0.30*FL+0.30*BL|FR=FC+0.30*FR+0.30*BR
    #https://superuser.com/a/1616102

    #https://superuser.com/a/1663861
    #Gregory's ATSC formula (ffmpeg -ac 2)  FL<1.0*FL+0.707*FC+0.707*BL+0.707*SL|FR<1.0*FR+0.707*FC+0.707*BR+0.707*SR
    #Robert Collier's Nightmode Dialogue    FL=FC+0.30*FL+0.30*BL+0.30*SL|FR=FC+0.30*FR+0.30*BR+0.30*SR
    #Dave_750                               FL=0.5*FC+0.707*FL+0.707*BL+0.707*SL+0.5*LFE|FR=0.5*FC+0.707*FR+0.707*BR+0.707*SR+0.5*LFE
    #RFC 7845 Section 5.1.1.5               FL=0.374107*FC+0.529067*FL+0.458186*BL+0.458186*SL+0.264534*BR+0.264534*SR+0.374107*LFE|FR=0.374107*FC+0.529067*FR+0.458186*BR+0.458186*SR+0.264534*BL+0.264534*SL+0.374107*LFE
    if channels >= 7:
        FL = '0.274804*FC + 0.388631*FL + 0.336565*SL + 0.194316*SR + 0.336565*BL + 0.194316*BR + 0.274804*LFE'
        FR = '0.274804*FC + 0.388631*FR + 0.336565*SR + 0.194316*SL + 0.336565*BR + 0.194316*BL + 0.274804*LFE'
    elif channels >= 6:
        FL = '0.321953*FC + 0.455310*FL + 0.394310*SL + 0.227655*SR + 278819*BC + 0.321953*LFE'
        FR = '0.321953*FC + 0.455310*FR + 0.394310*SR + 0.227655*SL + 278819*BC + 0.321953*LFE'
    elif channels >= 5.1:
        FL = '0.374107*FC + 0.529067*FL + 0.458186*BL + 0.264534*BR + 0.374107*LFE'
        FR = '0.374107*FC + 0.529067*FR + 0.458186*BR + 0.264534*BL + 0.374107*LFE'
    elif channels == 5:
        FL = '0.460186*FC + 0.650802*FL + 0.563611*BL + 0.325401*BR'
        FR = '0.460186*FC + 0.650802*FR + 0.563611*BR + 0.325401*BL'
    elif channels == 4:
        FL = '0.422650*FL + 0.366025*BL + 0.211325*BR'
        FR = '0.422650*FR + 0.366025*BR + 0.211325*BL'
    elif channels == 3:
        FL = '0.414214*FC + 0.585786*FL'
        FR = '0.414214*FC + 0.585786*FR'

    subprocess.run(["ffmpeg", "-hide_banner", "-y", "-i", waveFile, '-c', 'pcm_s16le', '-vol', '425', '-af', f'pan=stereo|FL={FL}|FR={FR}', filename])

    #ffmpeg -i "sourcetrack.dts"                                 -c dca -vol 425 -af "pan=stereo|c0=0.5*c2+0.707*c0+0.707*c4+0.5*c3|c1=0.5*c2+0.707*c1+0.707*c5+0.5*c3" "outputstereo.dts"

    return filename


def copyFile(sourceFile, destinationFile):
    # create a copy of the source file to the destination file
    success = False
    try:
        # perform the copy operation
        shutil.copy(sourceFile, destinationFile)
        success = True
    except shutil.Error as e:
        print(f"Error copying file: {e}")

    # check if the file copy was successful
    if success:
        if os.path.exists(sourceFile) and \
           os.path.samefile(sourceFile, destinationFile):
            print("File copy successful!")
        else:
            print("File copy failed.")
    
    return success

def removefile(f):
    success = False
    try:
        os.remove(f)
        if os.path.exists(f) == False:
            success = True
      
    except OSError:
        pass

    return success

def renameFile(curentFilePath, newFilePath):
    success = False
    # rename the file
    try:
        os.rename(curentFilePath, newFilePath)
        if os.path.exists(curentFilePath) == False and \
            os.path.exists(newFilePath) == True:
                success = True
                print("File renamed successfully!")
    except OSError as e:
        print(f"Error renaming file: {e}")
        
    return success

def addAudioFileToVideo(videoFilePath, audioFilePath, audioTitle):
    filename = os.path.splitext(file)[0] + '-temp' + os.path.splitext(file)[1]
    numberOfAudioTracks = len(getAudioTracks(videoFilePath))
    #ffmpeg -i video.mp4 -i audio.wav -c:v copy -c:a aac output.mp4
    if numberOfAudioTracks == 0:
        process = subprocess.run(["ffmpeg", "-hide_banner", "-y", "-i", videoFilePath, "-i", audioFilePath, "-vcodec", "copy", "-acodec", "copy", f"-metadata:s:a:{numberOfAudioTracks + 1}", f"title='{audioTitle}'", filename])
    else:
        #ffmpeg -hide_banner -y -i input.mkv -i audio.dts -map 0 -map 1 -c copy output.mkv
        #ffmpeg -hide_banner -y -i output3.mkv -i out3_audio_only_idx1-normalized.m4a -c copy -map 0 -map 1:a:0 -metadata:s:a:4 title='surround' output4.mkv
        process = subprocess.run(["ffmpeg", "-hide_banner", "-y", "-i", videoFilePath, "-i", audioFilePath, '-c', 'copy', "-map", "0", "-map", "1:a:0", f"-metadata:s:a:{numberOfAudioTracks}", f'title={audioTitle}', filename])
    if success := process.returncode == 0:
        backupFile = videoFilePath + '.backup'
        # make a backup of the original file before we attempt to replace it
        if success := copyFile(videoFilePath, backupFile) == True:
            # delete the original file
            if success := removefile(videoFilePath) == True:
                # change the temp file to the original file's name
                if success := renameFile(filename, videoFilePath) == True:
                    # delete the backup file because we successfully replace the original
                    removefile(backupFile)
                    #removefile(audioFilePath)

        if success == False:
            renameFile(backupFile, videoFilePath)
    
    return success
    

def normalizeAudioFile(file):
    filename = os.path.splitext(file)[0] + '-normalized' + os.path.splitext(file)[1]
    if os.path.exists(filename):
        return filename
    
    # process = subprocess.run(["ffmpeg-normalize", "-pr", file, "-f"])
    process = subprocess.run(["ffmpeg-normalize", "-pr", file, "-ar", "48000", "-c:a", "libfdk_aac", "-b:a", "192k", "-o", filename])
    #process = subprocess.run(["ffmpeg-normalize", "-pr", file, "-o", filename])
    #subprocess.run(["ffmpeg-normalize", audio_input, "-c:a", "libfdk_aac", "-b:a", "192k", "-ar", "48000", "-o", os.path.join(output_dir, os.path.splitext(input_file)[0] + 'normalized_surround_sound.aac')])


    return filename


def convertToAac(file, numberOfChannels):
    filename = os.path.splitext(file)[0] + f'-{numberOfChannels}ch.m4a'
    if os.path.exists(filename):
        return filename
    
    if sys.platform == "win32":
        subprocess.run(["qaac64", file, "-v", "127", "-o", filename])
    elif sys.platform == "darwin":
        try:
            #process = subprocess.run(["afconvert", "-q", "127", "-s", "3", "--quality", "2", "-d", "aac", file, filename])   
            process = subprocess.run(['afconvert', '-f', 'm4a', '-d', 'aac', '-b', '256000', file, filename], check=True)

            if process.returncode == 0:
                return filename
            #ffmpeg -channel_layout 5.1 -i infile.wav -af "pan=5.1|c0=c1|c1=c2|c2=c0|c3=c5|c4=c3|c5=c4" -c:a alac outfile.m4a
            #process = subprocess.run(["ffmpeg", "-hide_banner", "-y", "-i", file, "-map", "0", "-c", "copy", "-c:a", "aac", "-ac", f"{numberOfChannels}", filename])
            process = subprocess.run(["ffmpeg", "-hide_banner", "-y", "-i", file, "-map", "0", "-c", "copy", "-c:a", "aac", "-ac", f"{numberOfChannels}", filename])
            if process.returncode == 0:
                return filename
        except:
            try:
                process = subprocess.run(["ffmpeg", "-hide_banner", "-y", "-i", file, "-map", "0", "-c", "copy", "-c:a", "aac", "-ac", f"{numberOfChannels}", filename])
            except:
                try:
                    subprocess.run(["ffmpeg", "-hide_banner", "-y", "-i", file, "-map", "0", "-c", "copy", "-c:a", "libfdk_aac", "-ac", f"{numberOfChannels}", filename])
                except:
                    print('Could not encode')
    return filename 


def audioTrackTitleById(trackId):
    titles = subprocess.run(['mediainfo', '--Inform=Audio;%Title%|', file], capture_output=True, text=True).stdout.strip().split('|')
    if len(titles) > trackId:
        trackId = len(titles)

    return titles[trackId]

def audioTrackTitleByChannelCount(trackId):
    titles = subprocess.run(['mediainfo', '--Inform=Audio;%Title%|', file], capture_output=True, text=True).stdout.strip().split('|')
    if len(titles) > trackId:
        trackId = len(titles)

    return titles[trackId]

def convertVideoTo265(file):
    filename = os.path.splitext(file)[0] + '-h265.mkv'
    if os.path.exists(filename):
        return filename
    #start "BELOW NORMAL - %%~nxF" /BELOWNORMAL /WAIT ffmpeg -v quiet -stats -hide_banner -y -i "%%~nxF" -map 0:v -map 0:a -map 0:s? -map 0:d? -c copy -c:v:0 libx265 -max_muxing_queue_size 9999 -f matroska "%%~nF.tmp" 
    process = subprocess.run(["ffmpeg", "-hide_banner", "-y", "-i", file, "-map", '0:v', '-map', '0:a?', '-map', '0:s?', '-map', '0:d?', '-c', 'copy', '-c:v:0', 'libx265', '-max_muxing_queue_size', '9999', '-f', 'matroska', filename])

    return filename

#def downmixAudio(file):
#    subprocess.run(["ffmpeg", "-hide_banner", "-y", "-i", file, "-af", "pan=stereo|FL=1.0*FL+0.707*FC+0.707*SL+0.707*LFE|FR=1.0*FR+0.707*FC+0.707*SR+0.707*LFE", "-vn", file + "-ffmpeg.wav"])



# loop through all .mkv files in the current directory
# for file in os.listdir():
for root, dirs, files in os.walk(directory):
    for f in files:
        file = os.path.normpath(os.path.join(root, f))
        if file.endswith(".mkv") or file.endswith('.mp4'):
            trackIndex = 0
            ffmpegCommand = ''
        # try to retrieve audio track information using mediainfo
            try:
                logger.info("Processing " + file)
                writing_app = getWritingApplication(file)
                if str(writing_app[0]).upper().find('PYTHON') >= 0:
                    continue
                
                info = subprocess.run(['mediainfo', '--Inform=Audio;%CodecID%,%Channel(s)%,%Title%', file], capture_output=True, text=True).stdout.strip().split(',')
                codec = info[0]
                #channels = Decimal('6.1')
                channels = Decimal(info[1])
                title = ""
                if len(info) > 2:
                    title = info[2]
                
                # logger.info(f'Processing {file}')
                logger.info(f'Codec: {codec}')
                logger.info(f'Channels: {channels}')
                logger.info(f'Title: {title}')
                
            except:
                logger.fatal(f'Could not retrieve audio details for file {file}')
                #sys.exit(1)
            
            hasStereoTrack = False
            hasSurroundSoundTrack = False 
            audioTracks = getAudioTracks(file)
            for audioTrack in audioTracks:
                if audioTrack.isStereo():
                    hasStereoTrack = True
                    if audioTrack.isAac():
                        hasAacStereoTrack = True
                        if audioTrack.isNormalized():
                            hasNormalizedStereoTrack = True
                if audioTrack.isAac():
                    hasAacFormat = True
                if audioTrack.isNormalized():
                    isNormalized = True
            #====

            stereoTrackCreated = None
            hasAacTrack = False
            files = splitAudioVideo(file)
            audio_files = files['a']
            video_files = files['v']
            video_file = video_files[0]
            index = 0
            
            video_format = getVideoFormat(file)
            if video_format.upper().find('HEVC') < 0:
                video_file = convertVideoTo265(video_file)
            
            for audioTrack in audioTracks:
                title = f'{audioTrack.channels} Channels'
                audio_file = audio_files[index]
                if audioTrack.channels > 2:
                    success = addAudioFileToVideo(video_file, audio_file, f'Original ({audioTrack.channels} Channels)')
                    
                    if hasStereoTrack == False:
                        #create a stereo track
                        wavFile = extractAudioToWav(file)
                        downmixFile = downmixAudio(wavFile, audioTrack.channels)
                        removefile(wavFile)
                        normalizedFile = normalizeAudioFile(downmixFile)
                        removefile(downmixFile)
                        aacFile = convertToAac(normalizedFile, 2)
                        removefile(normalizedFile)
                        success = addAudioFileToVideo(video_file, aacFile, 'Stereo (Normalized) AAC')
                        removefile(aacFile)
                        hasStereoTrack = True
                    
                    removefile(audio_file)
                else:
                    if audioTrack.codec.upper().find('AAC') < 0:
                        wavFile = extractAudioToWav(file)
                        aacFile = convertToAac(wavFile, 2)
                        removefile(wavFile)
                        if audioTrack.title.upper().find("NORMALIZED") < 0:
                            aacFile = normalizeAudioFile(aacFile)
                        
                        success = addAudioFileToVideo(file, aacFile, f'{audioTrack.channels } Channel (Normalized) AAC')
                        removefile(aacFile)
                    else:
                        if audioTrack.title.upper().find("NORMALIZED") < 0:
                            #ffmpeg -i input.mkv -map 0:a:3 -c copy output.m4a
                            normalizedFile = normalizeAudioFile(audio_file)
                        
                            success = addAudioFileToVideo(video_file, normalizedFile, f'{audioTrack.channels } Channel (Normalized) AAC')
                            removefile(normalizedFile)
                            
                index = index + 1

            setWritingApplication(video_file, 'Downmix & Normalize using Python')
            removefile(file)
            renameFile(video_file, file)
            continue
        
            
            # # extract audio to wav and apply filter if necessary
            # if channels > 2:
            #     logger.info(f'Downmixing {str(channels)} and extracting WAV')
            #     # subprocess.run(["ffmpeg", "-hide_banner", "-y", "-i", file, "-af", "pan=stereo|FL=0.25*FL+FC+0.6*LFE|FR=0.25*FR+FC+0.6*LFE", "-vn", file + "-ffmpeg.wav"])
            #     subprocess.run(["ffmpeg", "-hide_banner", "-y", "-i", file, "-af", "pan=stereo|FL=1.0*FL+0.707*FC+0.707*SL+0.707*LFE|FR=1.0*FR+0.707*FC+0.707*SR+0.707*LFE", "-vn", file + "-ffmpeg.wav"])
            #     #subprocess.run(["ffmpeg", "-hide_banner", "-y", "-i", file, "-af", downmix_filter, "-vn", file + "-ffmpeg.wav"])
            # elif (channels == 2 and codec != "A_AAC-2"):
            #     logger.info("Extracting WAV")
            #     subprocess.run(["ffmpeg", "-hide_banner", "-y", "-i", file, "-vn", file + "-ffmpeg.wav"])
    
            # # check if -ffmpeg.wav file exists
            # if os.path.isfile(file + "-ffmpeg.wav"):
            #     logger.info("Converting to AAC")
            #     # convert wav to aac using qaac
            #     if sys.platform == "win32":
            #         subprocess.run(["qaac64", file + "-ffmpeg.wav", "-v", "127", "-o", file + "-aac.m4a"])
            #     elif sys.platform == "darwin":
            #         subprocess.run(["afconvert", "-q", "127", "-s", "3", "--quality", "2", "-d", "aac", file + "-ffmpeg.wav", file + "-aac.m4a"])
    
            #     # delete -ffmpeg.wav file
            #     os.remove(file + "-ffmpeg.wav")
    
            #     logger.info("Replacing Audio")
            #     # replace audio track in original file with -qaac.m4a
            #     # subprocess.run(["mkvmerge", "-o", file + "_temp.mkv", file, "--no-audio", "--language", "0:eng", "--track-name", "0:Audio", file + "-aac.m4a"])
            #     # subprocess.run(["mkvmerge", "-o", file + "_temp.mkv", "--no-audio", file, file + "-aac.m4a"])
            #     subprocess.run(["mkvmerge", "-o", file + "_temp.mkv", file, file + "-aac.m4a"])
    
            #     # delete -aac.mp4 file
            #     os.remove(file + "-aac.m4a")
    
            #     os.rename(file, file + "-original.mkv")
            #     os.rename(file + "_temp.mkv", file)
            #     os.remove(file + "-original.mkv")
                
            #     # set audio track's title using mkvpropedit
            #     subprocess.run(["mkvpropedit", file, "--edit", "track:a2", "--set", "name=" + title])
            #     codec = "A_AAC-2"
            #     channels = 2
            
            # # check if .srt file exists
            # if os.path.isfile(file.replace(".mkv", ".srt")):
            #     logger.info("Embedding subtitles")
            #     # merge .srt file into original file
            #     subprocess.run(["mkvmerge", "-o", file + "_temp.mkv", file, file.replace(".mkv", ".srt")])
            #     os.rename(file + "_temp.mkv", file)
            
            # # normalize audio and update title if necessary
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
