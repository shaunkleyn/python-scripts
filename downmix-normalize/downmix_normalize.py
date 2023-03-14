import subprocess
import os
import sys
# As you can see, this is pretty much identical to your code
from argparse import ArgumentParser
parser = ArgumentParser()
parser.add_argument("-f", "--folder", dest="directory", help="Folder containing items to normalize")
args = parser.parse_args()
directory = args.directory


# loop through all .mkv files in the current directory
# for file in os.listdir():
#for file in os.listdir(directory):
#    if file.endswith((".mkv", ".mp4")):
for root, dirs, files in os.walk(directory):
    for f in files:
        file = os.path.join(root, f)
        if file.endswith((".mkv", ".mp4", ".m4v")):
        # try to retrieve audio track information using mediainfo
            try:
                print("Processing " + file)
                info = subprocess.run(['mediainfo', '--Inform=Audio;%CodecID%,%Channel(s)%,%Title%', file], capture_output=True, text=True).stdout.strip().split(',')
                codec = info[0]
                channels = int(info[1])
                title = ""
                if len(info) > 2:
                    title = info[2]
                    
                # result = subprocess.run(["mediainfo", "--Inform=Audio;%Channels%", "--Inform=Audio;%CodecID%", "--Inform=Audio;%Title%", file], capture_output=True, text=True)
                # lines = result.stdout.split("\n")
                # channels = int(lines[0])
                # codec = lines[1]
                # title = ""
                # if lines.count > 1:
                #     title = lines[2]
            except:
                sys.exit(1)
            
            # extract audio to wav and apply filter if necessary
            if channels > 2:
                print("Downmixing " + str(channels) + " and extracting WAV")
                # subprocess.run(["ffmpeg", "-hide_banner", "-y", "-i", file, "-af", "pan=stereo|FL=0.25*FL+FC+0.6*LFE|FR=0.25*FR+FC+0.6*LFE", "-vn", file + "-ffmpeg.wav"])
                subprocess.run(["ffmpeg", "-hide_banner", "-y", "-i", file, "-af", "pan=stereo|FL=1.0*FL+0.707*FC+0.707*SL+0.707*LFE|FR=1.0*FR+0.707*FC+0.707*SR+0.707*LFE", "-vn", file + "-ffmpeg.wav"])
            elif (channels == 2 and codec != "A_AAC-2"):
                print("Extracting WAV")
                subprocess.run(["ffmpeg", "-hide_banner", "-y", "-i", file, "-vn", file + "-ffmpeg.wav"])
    
            # check if -ffmpeg.wav file exists
            if os.path.isfile(file + "-ffmpeg.wav"):
                print("Converting to AAC")
                # convert wav to aac using qaac
                if sys.platform == "win32":
                    subprocess.run(["qaac64", file + "-ffmpeg.wav", "-v", "127", "-o", file + "-aac.m4a"])
                elif sys.platform == "darwin":
                    subprocess.run(["afconvert", "-q", "127", "-s", "3", "--quality", "2", "-d", "aac", file + "-ffmpeg.wav", file + "-aac.m4a"])
    
                # delete -ffmpeg.wav file
                os.remove(file + "-ffmpeg.wav")
    
                print("Replacing Audio")
                # replace audio track in original file with -qaac.m4a
                # subprocess.run(["mkvmerge", "-o", file + "_temp.mkv", file, "--no-audio", "--language", "0:eng", "--track-name", "0:Audio", file + "-aac.m4a"])
                subprocess.run(["mkvmerge", "-o", file + "_temp.mkv", "--no-audio", file, file + "-aac.m4a"])
    
                # delete -aac.mp4 file
                os.remove(file + "-aac.m4a")
    
                os.rename(file, file + "-original.mkv")
                os.rename(file + "_temp.mkv", file)
                os.remove(file + "-original.mkv")
                
                # set audio track's title using mkvpropedit
                subprocess.run(["mkvpropedit", file, "--edit", "track:a1", "--set", "name=" + title])
                codec = "A_AAC-2"
                channels = 2
            
            # check if .srt file exists
            if os.path.isfile(file.replace(".mkv", ".srt")):
                print("Embedding subtitles")
                # merge .srt file into original file
                subprocess.run(["mkvmerge", "-o", file + "_temp.mkv", file, file.replace(".mkv", ".srt")])
                os.rename(file + "_temp.mkv", file)
            
            # normalize audio and update title if necessary
            if title != "Normalized":
                print("Normalizing audio for " + file)
                #subprocess.run(["ffmpeg-normalize", "-pr", "-f", file])
                subprocess.run(["ffmpeg-normalize", "-pr", "-ar", "48000", "-o", file, "-f"])
    
                subprocess.run(["mkvpropedit", file, "--edit", "track:a1", "--set", "name=Normalized"])
    
            # Send a CURL POST request to https://apprise.pleximus.co.za/notify with JSON data
            # requests.post('https://apprise.pleximus.co.za/notify', json={
            #     'urls': 'tgram://5022461051:AAHjO6VfT25und8CdEKIN1pxXagER-oN3Uk/-1001647957502',
            #     'title': 'File normalisation complete',
            #     'body': file
            # })
