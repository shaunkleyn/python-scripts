#!/usr/bin/env python
import os
import subprocess
import configparser
from tqdm import tqdm
import re
from ffmpeg_progress_yield import FfmpegProgress


config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../config.ini')
config = configparser.ConfigParser()
config.read(config_file)

flac_folder = config['FLAC2M4A']['flac_folder']
destination_folder = config['FLAC2M4A']['destination_folder']
delete_flac = config.getboolean('FLAC2M4A', 'delete_flac')
metadata_comment = config['FLAC2M4A']['metadata_comment']
encoder = config['FLAC2M4A']['encoder']
bitrate = config['FLAC2M4A']['bitrate']

new_file_extension = 'm4a'

def convert_to_m4a(file_path, file_name, file_extension):
    ffmpeg_command = [
        "ffmpeg", "-y", "-i", f"{file_path}/{file_name}.{file_extension}",
        "-c:v", "copy", "-vsync", "2", "-c:a", f"{encoder}",
        "-b:a", f"{bitrate}k", "-metadata", f"comment={metadata_comment}",
        f"{file_path}/{file_name}.{new_file_extension}"
    ]

    ff = FfmpegProgress(ffmpeg_command)
    inner_progress = tqdm(total=100, position=1, desc=file_name, leave=False)
    with inner_progress as pbar:
        for progress in ff.run_command_with_progress():
            pbar.update(progress - pbar.n)

    if delete_flac == True:
        os.remove(f"{file_path}/{file_name}.{file_extension}")

def move_to_destination(file_path, file_name, file_extension):
    os.rename(f"{file_path}/{file_name}.{file_extension}", f"{destination_folder}/{file_name}.{file_extension}")

def main():
    files_to_process = []
    for root, dirs, files in os.walk(flac_folder):
        for file in files:
            if file.endswith(".flac"):
                files_to_process.append(os.path.join(root, file))

    for file in tqdm(files_to_process, desc='Converting Files'):
        file_path, file_name_with_extension = os.path.split(os.path.join(root, file))
        file_name, file_extension = os.path.splitext(file_name_with_extension)

        lossless_file = os.path.join(root, file)
        m4a_file = os.path.splitext(lossless_file)[0] + f".{new_file_extension}"
        m4a_file = os.path.join(destination_folder, os.path.relpath(m4a_file, flac_folder))

        convert_to_m4a(file_path, file_name, file_extension[1:])
        if flac_folder != destination_folder:
            move_to_destination(file_path, file_name, f"{new_file_extension}")

if __name__ == "__main__":
    main()