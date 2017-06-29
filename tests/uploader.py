import os
import initialize_data
from os import listdir
from os.path import isfile, join


_rootdir = '/mnt/seed_data'
def upload_images(subdir_name, rootdir, user_list):

    dirpath = rootdir + '/' + subdir_name
    file_list = [f for f in listdir(dirpath) if isfile(join(dirpath, f))]

    # iterate on these files and upload them
    for f in file_list:
        ext = f[-4:]
        if ext == '.jpg':
            # upload the photo
            # rename it so we won't upload it again
            newname = file + '.1'
            os.rename(file, newname)

    return

def folder_exists(subdir_name, rootdir):

    # append this to the root dir and see
    # if it exists
    dirpath = rootdir + '/' + subdir_name
    return os.path.isdir(dirpath)

def Upload_Category_Pictures():
    '''
    Do the following:
    1) download category list
    2) find folder for category in upload state
    3) upload any .jpg/jpeg files to the category
    4) rename uploaded files so they won't be uploaded again
    :return:
    '''

    # First setup the test uploader
    ie = initialize_data.InitializeEnvironment()

    ie._base_url = "https://api.imageimprov.com"

    # now get the current active categories

    user_list = ie.register_test_users()
    assert(len(user_list) > 0)

    # Now use the first user to get the category
    tu = user_list[0]
    token = tu.get_token()

    cl = ie.read_category(token)

    for c in cl:
        if c.is_uploading():
            theme = c.get_description()
            # see if we have a folder with this name
            if folder_exists(theme, _rootdir):
                upload_images(theme, _rootdir, user_list)


