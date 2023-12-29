import os
import hashlib
import mutagen

def get_bitrate(file):
    audio = mutagen.File(file)
    bitrate = int(audio.info.bitrate / 1000)
    return bitrate

def get_file_hash(file):
    hasher = hashlib.sha1()
    with open(file, "rb") as f:
        chunk = f.read(4096)
        while chunk:
            hasher.update(chunk)
            chunk = f.read(4096)
    return hasher.hexdigest()

def delete_duplicates(path):
    for root, dirs, files in os.walk(path):
    #     for file in files:
    #         file_path = os.path.join(root, file)
    #         if file_path.lower().endswith(('.zip', '.rar')):
    #             dest_folder = os.path.join(root, os.path.splitext(file)[0])
    #             extract_files(file_path, dest_folder)
    #             os.remove(file_path)
    #         else:
    #             convert_audio_to_m4a(file_path, root)
    #             embed_album_art(file_path, root)


    # files = [f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))]
        duplicates = {}
        for file in files:
            if file.endswith((".m4a", ".aac", ".mp3")):
                print(file)
                try:
                    bitrate = get_bitrate(os.path.join(root, file))
                    file_hash = get_file_hash(os.path.join(root, file))
                    if bitrate not in duplicates:
                        duplicates[bitrate] = {}
                    if file_hash not in duplicates[bitrate]:
                        duplicates[bitrate][file_hash] = []
                    duplicates[bitrate][file_hash].append(file)
                except:
                    continue
        for bitrate in duplicates:
            for file_hash in duplicates[bitrate]:
                if len(duplicates[bitrate][file_hash]) > 1:
                    duplicates[bitrate][file_hash].sort()
                    with open("deleted_files.txt", "a") as f:
                        for file in duplicates[bitrate][file_hash][1:]:
                            audio = mutagen.File(os.path.join(root, file))
                            f.write(f"=============\n")
                            f.write(f"Deleting {os.path.join(root, file)}:\n")
                            f.write(f"\t\t{audio.pprint()}\n")
                            os.remove(os.path.join(root, file))

delete_duplicates("T:/itunes/iTunes/iTunes Media/Music/Bob Marley/Sun Is Shining")
