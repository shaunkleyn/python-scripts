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
    files = [f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))]
    duplicates = {}
    for file in files:
        if file.endswith((".m4a", ".aac", ".mp3")):
            bitrate = get_bitrate(os.path.join(path, file))
            file_hash = get_file_hash(os.path.join(path, file))
            if bitrate not in duplicates:
                duplicates[bitrate] = {}
            if file_hash not in duplicates[bitrate]:
                duplicates[bitrate][file_hash] = []
            duplicates[bitrate][file_hash].append(file)
    for bitrate in duplicates:
        for file_hash in duplicates[bitrate]:
            if len(duplicates[bitrate][file_hash]) > 1:
                duplicates[bitrate][file_hash].sort()
                with open("deleted_files.txt", "a") as f:
                    for file in duplicates[bitrate][file_hash][1:]:
                        audio = mutagen.File(os.path.join(path, file))
                        f.write(f"Deleting {file}: {audio.pprint()}\n")
                        os.remove(os.path.join(path, file))

delete_duplicates(".")
