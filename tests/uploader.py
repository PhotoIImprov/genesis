import os
import initialize_data
from os import listdir
from os.path import isfile, join
import json
import base64
import requests
import uuid
from werkzeug.datastructures import Headers
from models import category

_rootdir = '/mnt/seed_data'
_base_url = 'https://api.imageimprov.com'

def login_user(u=None):
    url = _base_url + '/auth'
    if u is None:
        u = 'bp100a@hotmail.com'
    p = 'pa55w0rd'
    l_rsp = requests.post(url, data=json.dumps(dict(username=u, password=p)),
                        headers={'content-type': 'application/json'})
    if l_rsp.status_code != 200:
        return None

    data = json.loads(l_rsp.content.decode("utf-8"))
    token = data['access_token']
    return token

def upload_image(fn, cid):

    # register user
    token = login_user()
    if token is None:
        return

    # upload file on behalf of user
    try:
        ft = open(fn, 'rb')
        if ft is None:
            return
        ph = ft.read()
        ft.close()
        if ph is None:
            return

        # compose header with users authorization token
        h = Headers()
        h.add('Authorization', 'JWT ' + token)
        h.add('content-type', 'image/jpeg')

        # okay, we need to post this
        ext = 'JPEG'
        url = _base_url + '/jpeg/{0}'.format(cid)

        # we can occasionally get a '502, Bad Gateway', let's retry if we do'
        for i in range(0,2):
            rsp = requests.post(url=url, headers=h, data=ph)
            if rsp.status_code != 502:
                return

    except Exception as e:
        return

    return

def upload_images(subdir_name, rootdir, cid):

    dirpath = rootdir + '/' + subdir_name
    file_list = [f for f in listdir(dirpath) if isfile(join(dirpath, f))]

    # iterate on these files and upload them
    idx = 0
    for f in file_list:
        ext = f[-4:]
        if ext in ('.jpg', '.JPG'):
            # upload the photo
            # rename it so we won't upload it again
            full_name = dirpath + '/' + f
            idx += 1
            upload_image(full_name, cid)

    return

def setcategorystate(token: str, cid: int, category_state: int) -> bool:
    '''
    change the category state
    :param token: JWT token needed to upload
    :param cid:
    :param category_state:
    :return:
    '''
    h = Headers()
    h.add('content-type', 'application/json')
    h.add('Authorization', 'JWT ' + token)

    url = _base_url + '/setcategorystate'
    rsp = requests.post(url, data=json.dumps(dict(category_id=cid, state=category_state)), headers=h)
    return rsp.status_code == 200


def folder_exists(subdir_name, rootdir):

    # append this to the root dir and see
    # if it exists
    dirpath = rootdir + '/' + subdir_name
    return os.path.isdir(dirpath)

if __name__ == '__main__':
    '''
    Do the following:
    1) download category list
    2) find folder for category in upload state
    3) upload any .jpg/jpeg files to the category
    4) rename uploaded files so they won't be uploaded again
    :return:
    '''

    # First setup the test uploader
    ie = initialize_data.InitEnvironment()

    ie._base_url = "https://api.imageimprov.com"

    # now get the current active categories

    # Now use the first user to get the category
    token = login_user() # this user has to have a usertype of 'IISTAFF' to change category state
    cl = ie.read_category(token)

    for c in cl:
        cid = c['id']
        if cid < 25683:
            continue

        theme = c['description']
        current_state = c['state']
        if current_state in ('VOTING', 'PENDING'):
            if folder_exists(theme, _rootdir):
                status = setcategorystate(token, cid, category.CategoryState.UPLOAD.value)
                upload_images(theme, _rootdir, cid)

            state = category.CategoryState.UNKNOWN.value
            if current_state == 'VOTING':
                state = category.CategoryState.VOTING.value
            status = setcategorystate(token, cid, state)

        if c['state'] == 'UPLOAD':
            # see if we have a folder with this name
            if folder_exists(theme, _rootdir):
                upload_images(theme, _rootdir, cid)


