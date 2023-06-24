#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2017 Simon Erhardt
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import subprocess
import os
import json
import logging
import argparse
import re
#import numexpr

def run_command(command):
    process = subprocess.Popen(command, stdout=subprocess.PIPE)
    while True:
        output = process.stdout.readline()
        if output:
            print(output.strip())
        if process.poll() is not None:
            break

    return process.wait()

parser = argparse.ArgumentParser(description='Batch convert your media library to H264 and AAC.')
parser.add_argument('--quality', required=False, type=int, default=20, help='crf quality of libx264 (default: 20)')
parser.add_argument('--preset', required=False, type=str, default='veryslow', help='encoding preset for libx264 (default: veryslow)')
parser.add_argument('--resolution', required=False, type=int, default=1080, help='maximum resolution in height (default: 1080)')
parser.add_argument('--rate', required=False, type=int, default=25, help='maximum framerate (default: 25)')
# parser.add_argument('--folder', required=False, default="/Volumes/media/series/Abandoned Engineering", type=str, help='folder to scan')
parser.add_argument('folder', type=str, help='folder to scan')
args = parser.parse_args()

logFormatter = logging.Formatter('%(asctime)s %(levelname)s:%(name)s %(message)s')
consoleHandler = logging.StreamHandler()
consoleHandler.setFormatter(logFormatter)
logging.getLogger().addHandler(consoleHandler)
logging.getLogger().setLevel(logging.DEBUG)

regexp = re.compile('.*\.(mp4|avi|mov|mkv|divx|xvid|flv|webm|m2ts|m1v|m2v|ogm|ogv|wmv)')
regexpTmp = re.compile('.*\.ffprocess_tmp\.mkv')
fileNumber = 0

for root, dirnames, filenames in os.walk(str(args.folder)):
    for filename in filenames:
        # don't touch tmp files
        if regexpTmp.search(filename) is not None:
            continue

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
                    continue
                
                print(f'#{fileNumber}) {totalAudioStreams} audio streams')
                for stream in data['streams']:
                    if stream['codec_type'] == 'audio':
                        if 'title' in stream['tags']:
                            # Remove the normalized stream
                            if 'Normalized' in stream['tags']['title'] and streamsRemaining > 1:
                                print(f'#{fileNumber}) Removing Normalized audio: Track {audioStream + 1} of {totalAudioStreams}, Codec: {stream["codec_name"]}, Title: {stream["tags"]["title"]}')
                                ffmpegCmd.append("-map")
                                ffmpegCmd.append("-0:a:%d" % audioStream)
                                reconvert = True
                                streamsRemaining-=1
                            elif streamsRemaining > 1 and totalAudioStreams > 1 and hasSurroundAudio and int(stream['channels']) == 2:  # Remove the downmixed stream
                                print(f'#{fileNumber}) Removing downmixed audio: Track {audioStream + 1} of {totalAudioStreams}, Codec: {stream["codec_name"]}, Title: {stream["tags"]["title"]}')
                                ffmpegCmd.append("-map")
                                ffmpegCmd.append("-0:a:%d" % audioStream)
                                reconvert = True
                                streamsRemaining-=1
                            elif streamsRemaining > 1 and totalAudioStreams > 1 and int(stream['disposition']['default']) == 1: #
                                print(f'#{fileNumber}) Removing default audio: Track {audioStream + 1} of {totalAudioStreams}, Codec: {stream["codec_name"]}, Title: {stream["tags"]["title"]}')
                                ffmpegCmd.append("-map")
                                ffmpegCmd.append("-0:a:%d" % audioStream)
                                reconvert = True
                                streamsRemaining-=1
                        elif streamsRemaining > 1 and '(' in stream['tags']['title']: #stream['codec_name'] == 'ac3' and audioStream + 1 >= streamsRemaining:
                                print(f'#{fileNumber}) Removing additional stream: Track {audioStream + 1} of {totalAudioStreams}, Codec: {stream["codec_name"]}, Title: {stream["tags"]["title"]}')
                                ffmpegCmd.append("-map_metadata")
                                ffmpegCmd.append('-1')
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

                    filename, file_extension = os.path.splitext(filepath)
                    filepathTmp = filename + ".ffprocess_tmp.mkv"
                    filepathNew = filename + ".mkv"
                    cmd.append(filepathTmp)

                    logging.debug("Running cmd: %s" % cmd)
                    exitcode = run_command(cmd)

                    if exitcode == 0:
                        logging.info("Converting successfully, removing old stuff...")

                        os.remove(filepath)
                        os.rename(filepathTmp, filepathNew)

                        logging.info("Converting finished...")
                    else:
                        logging.error("Converting failed, continuing...")

                # else:
                #     logging.info("File is already good, nothing to do...")

            except (subprocess.CalledProcessError, KeyError):
                logging.error("Couldn't check file %s, continuing..." % filepath)
                continue
