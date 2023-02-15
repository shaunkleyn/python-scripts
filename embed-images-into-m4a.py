import os
import mutagen
from mutagen.mp4 import MP4, MP4Cover
from PIL import Image

def embed_album_art(folder):
    for subdir, dirs, files in os.walk(folder):
        # Find all image files in the current directory
        image_files = [file for file in files if file.endswith(".jpg") or file.endswith(".jpeg") or file.endswith(".png")]
        # Check if the current directory is the parent directory
        if subdir == folder:
            # Find all .m4a files in the parent directory
            m4a_files = [file for file in files if file.endswith(".m4a")]
            # Embed all images as album art in each .m4a file
            for image_file in image_files:
                image_file_path = os.path.join(subdir, image_file)
                # Compress the image
                with Image.open(image_file_path) as img:
                    img.save(image_file_path, optimize=True, quality=85)
                with open(image_file_path, "rb") as f:
                    image_data = f.read()
                    for m4a_file in m4a_files:
                        m4a_file_path = os.path.join(subdir, m4a_file)
                        audio = MP4(m4a_file_path)
                        # Initialize the covr key if it's not already present
                        if "covr" not in audio:
                            audio["covr"] = []
                        # Embed the image as the main album art if it's named "cover" or "folder"
                        if image_file.lower() in ["cover", "folder"]:
                            audio["covr"] = [MP4Cover(image_data, imageformat=MP4Cover.FORMAT_JPEG)]
                        else:
                            # Embed the image as additional album art
                            audio["covr"].append(MP4Cover(image_data, imageformat=MP4Cover.FORMAT_JPEG))
                        audio.save()

# Example usage
folder = "/path/to/folder"
embed_album_art(folder)




# import os
# import mutagen
# from mutagen.mp4 import MP4, MP4Cover

# def embed_album_art(folder):
    # for subdir, dirs, files in os.walk(folder):
        # # Check if the current directory is the parent directory
        # if subdir == folder:
            # # Find all .m4a files in the parent directory
            # m4a_files = [file for file in files if file.endswith(".m4a")]
            # # Embed all images as album art in each .m4a file
            # for file in files:
                # # Check if file is an image
                # if file.endswith(".jpg") or file.endswith(".jpeg") or file.endswith(".png"):
                    # image_file_path = os.path.join(subdir, file)
                    # with open(image_file_path, "rb") as f:
                        # image_data = f.read()
                        # for m4a_file in m4a_files:
                            # m4a_file_path = os.path.join(subdir, m4a_file)
                            # audio = MP4(m4a_file_path)
                             # # Initialize the covr key if it's not already present
                            # if "covr" not in audio:
                                # audio["covr"] = []
                            # # Embed the image as additional album art
                            # audio["covr"].append(MP4Cover(image_data, imageformat=MP4Cover.FORMAT_JPEG))
                            # audio.save()
    # # for subdir, dirs, files in os.walk(folder):
        # # # Check if the current directory is the parent directory
        # # if subdir == folder:
            # # # Find all .m4a files in the parent directory
            # # m4a_files = [file for file in files if file.endswith(".m4a")]
            # # # Embed all images as album art in each .m4a file
            # # for file in files:
                # # # Check if file is an image
                # # if file.endswith(".jpg") or file.endswith(".jpeg") or file.endswith(".png"):
                    # # image_file_path = os.path.join(subdir, file)
                    # # with open(image_file_path, "rb") as f:
                        # # image_data = f.read()
                        # # for m4a_file in m4a_files:
                            # # m4a_file_path = os.path.join(subdir, m4a_file)
                            # # audio = mutagen.File(m4a_file_path)
                            # # # Embed the image as additional album art
                            # # audio.tags.add(
                                # # APIC(
                                    # # encoding=3,
                                    # # mime='image/jpeg',
                                    # # type=3, desc=u'Cover',
                                    # # data=image_data
                                # # )
                            # # )
                            # # audio.save()

# # Example usage
# folder = "H:/convert/2004 - My Prerogative (Jive 828766652581, 12 Inch, Promo, EU)/2004 - My Prerogative (Jive 828766652581, 12 Inch, Promo, EU)"
# embed_album_art(folder)
