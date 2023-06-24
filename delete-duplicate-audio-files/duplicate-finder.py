#https://codereview.stackexchange.com/questions/278311/faster-way-to-find-duplicates-in-a-directory-using-python
import argparse
import os
import hashlib
from collections import defaultdict
from pathlib import Path
from typing import Iterator, Iterable, NamedTuple

CHUNK_SIZE = 4 * 1024 * 1024


class HashedFile(NamedTuple):
    size: int
    path: Path
    md5_hash: bytes

    def __str__(self) -> str:
        return str(self.path)

    @classmethod
    def load(cls, root: Path, name: str) -> 'HashedFile':
        path = root / name

        md5_hash = hashlib.md5()
        with path.open('rb') as f:
            for chunk in iter(lambda: f.read(CHUNK_SIZE), b''):
                md5_hash.update(chunk)

        return cls(path.stat().st_size, path, md5_hash.digest())


def file_listing(directory: str) -> Iterator[HashedFile]:
    for root, dirs, files in os.walk(directory):
        root_path = Path(root)
        for name in files:
            yield HashedFile.load(root_path, name)


def filter_by_extension(files: Iterable[HashedFile]) -> Iterator[HashedFile]:
    extension = input('Enter file extension to select, or press enter for all: ')
    if len(extension) == 0:
        yield from files
    else:
        for file in files:
            if file.path.suffix == '.' + extension:
                yield file


def print_by_size(files: Iterable[HashedFile]) -> None:
    print('Size sorting options:'
          '\n   d. Descending'
          '\n   a. Ascending')
    while True:
        order = input('Enter a sorting option: ')
        if order in {'a', 'd'}:
            break
        print('Invalid option')

    print()
    for file in sorted(files, reverse=order == 'd'):
        print(f'{file.size:9} bytes: {file}')


def ask_yn(prompt: str) -> bool:
    while True:
        answer = input(f'{prompt} (y|n)? ')[:1].lower()
        if answer in {'y', 'n'}:
            return answer == 'y'
        print('Invalid option')


def find_duplicates(files: Iterable[HashedFile]) -> Iterator[list[HashedFile]]:
    duplicates = defaultdict(list)
    for file in files:
        duplicates[file.size, file.md5_hash].append(file)

    for (size, md5_hash), dupe_files in duplicates.items():
        if len(dupe_files) > 1:
            print(f'Size: {size} bytes, MD5: {md5_hash.hex()}')
            for i, file in enumerate(dupe_files, 1):
                print(f'{i:4}. {file}')
            yield dupe_files


def delete_duplicates(duplicate_groups: Iterable[list[HashedFile]]) -> Iterator[int]:
    for files in duplicate_groups:
        while True:
            keep_str = input('Enter file number to keep: ')
            if keep_str.isdigit():
                keep_index = int(keep_str) - 1
                if 0 <= keep_index < len(files):
                    keep = files[keep_index]
                    break
            print('Invalid option')

        for file in files:
            if file is not keep:
                print(f'   Deleting {file}')
                file.path.unlink()
                yield file.size


def main() -> None:
    parser = argparse.ArgumentParser(description='Handle duplicate files')
    parser.add_argument('folder', help='folder to list files in dir and subdir')
    args = parser.parse_args()

    directory = file_listing(args.folder)
    directory = tuple(filter_by_extension(directory))
    print_by_size(directory)
    print()

    if ask_yn('Check for duplicates'):
        duplicates = find_duplicates(directory)
        if ask_yn('Delete duplicates'):
            bytes_removed = sum(delete_duplicates(duplicates))
            print(f'\nTotal freed up space: {bytes_removed} bytes')
        else:
            for _ in duplicates:  # consume iterator to print
                pass


if __name__ == '__main__':
    main()