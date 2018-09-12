import os


def get_photo_fullpath(photo_file_name: str) -> str:
    """return a fully specified path & name for the photos folder"""
    dir_path = os.path.dirname(os.path.realpath(__file__))
    cwd = os.getcwd()
    if 'tests' in cwd:
        photo_dir = cwd.replace('tests', 'photos')
    else:
        photo_dir = cwd + "/photos"

    return photo_dir + '/' + photo_file_name
