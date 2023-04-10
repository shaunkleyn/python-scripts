import os

def find_large_audio_files(path):
    audio_extensions = [".mp3", ".flac", ".wav", ".aac", ".m4a"]
    large_files = []

    for root, dirs, files in os.walk(path):
        for file in files:
            full_path = os.path.join(root, file)
            if any(file.endswith(ext) for ext in audio_extensions):
                file_size = os.path.getsize(full_path)
                if file_size > 100 * 1024 * 1024: # 100 MB
                    large_files.append((file, file_size))

    return large_files

if __name__ == "__main__":
    directory = input("Enter the directory path: ")
    large_files = find_large_audio_files(directory)
    for file, size in large_files:
        print("{}: {:.2f} MB".format(file, size / 1024 / 1024))
