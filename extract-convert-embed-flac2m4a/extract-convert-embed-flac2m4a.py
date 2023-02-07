import os
import zipfile
import rarfile
import mutagen

def extract_files(file_path, dest_folder):
    if zipfile.is_zipfile(file_path):
        with zipfile.ZipFile(file_path, 'r') as zf:
            zf.extractall(dest_folder)
    elif rarfile.is_rarfile(file_path):
        with rarfile.RarFile(file_path, 'r') as rf:
            rf.extractall(dest_folder)
    else:
        raise Exception(f"{file_path} is not a supported archive file")

def convert_audio_to_m4a(file_path, dest_folder):
    audio = mutagen.File(file_path)
    if audio is None or audio.mime[0].split('/')[0] != 'audio':
        return
    if audio.mime[0].split('/')[1] in ['flac', 'alac', 'ape']:
        dest_path = os.path.join(dest_folder, os.path.splitext(os.path.basename(file_path))[0] + ".m4a")
        os.system(f"ffmpeg -i '{file_path}' -c:a aac -b:a 256k '{dest_path}'")
        os.remove(file_path)

def embed_album_art(file_path, dest_folder):
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

def process_folder(folder_path):
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            file_path = os.path.join(root, file)
            if file_path.lower().endswith(('.zip', '.rar')):
                dest_folder = os.path.join(root, os.path.splitext(file)[0])
                extract_files(file_path, dest_folder)
                os.remove(file_path)
            else:
                convert_audio_to_m4a(file_path, root)
                embed_album_art(file_path, root)

if __name__ == '__main__':
    folder_path = input("Enter the path to the folder to process: ")
   
