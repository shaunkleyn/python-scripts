# Ferdiga
# moves duplicate files in folder_a to trash
# 20220625
# credits to
# https://codereview.stackexchange.com/questions/133333/compare-files-by-name-in-two-folders-a-and-b-and-delete-duplicates-from-folder-a
import os
import filecmp
import argparse
# from send2trash import send2trash

def sub_files(folder):
    relpath = os.path.relpath
    join = os.path.join
    for path, _, files in os.walk(folder):
        relative = relpath(path, folder)
        for file in files:
            yield join(relative, file)

def remove_duplicates(folder_a, folder_b, shallow=False, dry_run=False):
    Trash = "/Users/ferdinand/.Trash"
    folders = [folder_a, folder_b]
    files = [set(sub_files(folder)) for folder in folders]
    duplicates, *_ = groups  = [files[0] , files[1]]
    if not shallow:
        duplicates, *_ = groups = filecmp.cmpfiles(*folders, duplicates)
    print('\n\n'.join(
        '{}:\n{}'.format(name, '\n'.join('    {}'.format(file) for file in files))
        for files, name in zip(groups, ('Duplicates', 'Non-Duplicates', 'Errors'))
        if files
    ))
    if not dry_run:
        join = os.path.join
        for file in duplicates:
            # send2trash(join(folder_a, file))
            #/Volumes/Music/trash
            print('will delete this')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('folder_a', help='folder to delete from')
    parser.add_argument('folder_b', help='folder to find duplicates in')
    parser.add_argument('-d', '--dry', help='dry-run the program', action="store_true")
    parser.add_argument('-s', '--shallow', help='only check file names for duplicates', action="store_true")
    args = parser.parse_args()

    remove_duplicates(args.folder_a, args.folder_b, shallow=args.shallow, dry_run=args.dry)
