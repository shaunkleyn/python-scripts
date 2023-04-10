# macOS/Linux
# You may need to run `sudo apt-get install python3-venv` first on Debian-based OSs
# python3 -m venv .venv
# source .venv/bin/activate 

import os
import zipfile
import rarfile
import mutagen
import subprocess
from pysplitcue import splitcue


def extract_files(file_path, dest_folder):
    if zipfile.is_zipfile(file_path):
        with zipfile.ZipFile(file_path, 'r') as zf:
            zf.extractall(dest_folder)
    elif rarfile.is_rarfile(file_path):
        with rarfile.RarFile(file_path, 'r') as rf:
            rf.extractall(dest_folder)
    else:
        raise Exception(f"{file_path} is not a supported archive file")

# def split_files(file_path):
#     if file_path.split('.')[-1] in ['cue']:
#         kwargs = {'filename': file_path}
#         split = PySplitCue(**kwargs)
#         split.open_cuefile()
#         split.do_operations()
#         split.cuefile.close()

def split_audio(file_path, dest_folder):
    wv_file = os.path.splitext(file_path)[0] + ".wv"
    if os.path.exists(wv_file):
        cue_file = file_path.replace('.wv', '.cue')
        if os.path.exists(cue_file):
            #splitcue(os.path.join(dest_folder, cue_file), os.path.join(dest_folder, file_path))
            subprocess.call(["wvunpack", "-c", cue_file, file_path])


            # cmd = 'ffmpeg -i "{}" -codec copy -map 0 -f segment -segment_format wv -segment_time_metadata 1 -i "{}" "{}%03d.wv"'.format(
            #     os.path.join(dest_folder, file_path),
            #     os.path.join(dest_folder, cue_file),
            #     os.path.join(dest_folder, os.path.splitext(file_path)[0])
            # )
            # subprocess.call(cmd, shell=True)
            os.remove(os.path.join(dest_folder, file_path))
    # cue_file = os.path.splitext(file_path)[0] + ".cue"
    # wv_file = os.path.splitext(file_path)[0] + ".wv"
    # if os.path.exists(cue_file) and os.path.exists(wv_file):
    #     dest_path = os.path.join(dest_folder, os.path.splitext(os.path.basename(file_path))[0] + ".m4a")
    #     os.system(f"wvunpack -q -c '{cue_file}' '{wv_file}' '{dest_path}'")
    #     os.remove(cue_file)
    #     os.remove(wv_file)

def convert_audio_to_m4a(file_path, dest_folder):
    audio = mutagen.File(file_path)
    if audio is None or audio.mime[0].split('/')[0] != 'audio':
        return
    if audio.mime[0].split('/')[1] in ['flac', 'alac', 'ape']:
        dest_path = os.path.join(dest_folder, os.path.splitext(os.path.basename(file_path))[0] + ".m4a")
        ffmpeg_command = f"ffmpeg -y -i '{file_path}' -c:v copy -vsync 2 -c:a libfdk_aac -b:a 320k -metadata comment='Processed by Python' '{dest_path}'"
        os.system(ffmpeg_command)
        os.remove(file_path)

def embed_album_art(file_path, dest_folder):
    try:
        audio = mutagen.File(file_path)
        if audio is None or audio.mime[0].split('/')[0] != 'audio':
            return
        for root, dirs, files in os.walk(dest_folder):
            for file in files:
                if file.lower().endswith(('.jpg', '.jpeg', '.png')):
                    art = mutagen.File(os.path.join(root, file))
                    if art is None or art.mime[0].split('/')[0] != 'image':
                        continue
                    audio.tags.add(
                        mutagen.id3.APIC(
                            encoding=3,
                            mime='image/jpeg',
                            type=3,
                            desc='Cover',
                            data=art.read()
                        )
                    )
                    audio.save()
                    os.remove(os.path.join(root, file))
    except:
        print('error')

def process_folder(folder_path):
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            file_path = os.path.join(root, file)
            if file_path.lower().endswith(('.zip', '.rar')):
                dest_folder = os.path.join(root, os.path.splitext(file)[0])
                extract_files(file_path, dest_folder)
                process_folder(dest_folder)
                #convert_audio_to_m4a(dest_folder, dest_folder)
                #embed_album_art(dest_folder, dest_folder)
                os.remove(file_path)
            else:
                #split_audio(file_path, root)
                convert_audio_to_m4a(file_path, root)
                embed_album_art(file_path, root)

if __name__ == '__main__':
    #folder_path = input("Enter the path to the folder to process: ")
    process_folder('/Users/shaunkleyn/Music')
   
