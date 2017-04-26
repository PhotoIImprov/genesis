import os
import unittest
import json
import base64
import requests
from tests import test_REST_login
from models import category
from werkzeug.datastructures import Headers


# ************************************************************************
# ************************************************************************
# **                                                                    **
# ** INITIALIZE ENVIRONMENT                                             **
# ** When invoked this procedure will create accounts for the email     **
# ** addresses in the _users[] list and then upload all the photos in   **
# ** _photos[] list. If users have already been registered, it knows    **
# ** not to fail and just log them in.                                  **
# **                                                                    **
# ************************************************************************
# ************************************************************************

class InitEnvironment(unittest.TestCase):

    _photos = ('Cute_Puppy.jpg',
              'Emma Passport.jpg',
              'Galaxy Edge 7 (full res)jpg.jpg',
              'Galaxy Edge 7 Cat  (full res)jpg.jpg',
              'Galaxy Edge 7 Office Desk (full res, hdr).jpg',
              'Hawaii Palm Tree.JPG',
              'iPhone 6 Spider web (full res).JPG',
              'iPhone 7 statue and lake (full res).jpg',
              'iPhone 7 Yellow Rose (full res).jpg',
              'Netsoft USA Company Picture 1710.jpg',
              'PrimRib.JPG',
              'Suki.JPG',
              'Turtle.JPG',
               'Portrait.JPG',
               'Rotate90CW.JPG',
               'Rotate180CW.JPG',
               'Rotate270CW.JPG',

               '2012-05-23 19.45.55.jpg',
               '20130826_170610_A.jpg',
               'img_0264_edited-100686951-orig.jpg',
               'img_0026.jpg',
               'img_0034.jpg',
               'apple-iphone-7-camera-samples-27.jpg',
               'Apple-iPhone-7-camera-photo-sample-2.jpg',
               'iphone-7-plus-camera-trout.jpg',
               'IMG_0307.JPG',
               'iPhone-7-Camera-AndyNicolaides.jpg',
               'img_0017.jpg',
               '9lqqdnm.jpg',
               '001-B-Moto-Z-Force-Droid-Samples.jpg',
               'moto-z-play-camera-sample.jpg',
               'moto_z_play_camera_samples_7.jpg',
               'sample1.jpg',
               'Moto-Z-Force-Droid.jpg',
               'tf2fzhr.jpg',
               'IMG_1218.JPG',
               'sam_4089.jpg',
               'vetndhl.jpg'
               )

    _users = {'hcollins@gmail.com',
             'bp100a@hotmail.com',
             'dblankley@blankley.com',
             'regcollins@hotmail.com',
             'qaetre@hotmail.com',
             'hcollins@prizepoint.com',
             'hcollins@exit15w.com',
             'harry.collins@epam.com',
             'crazycow@netsoft-usa.com',
             'harry.collins@netsoft-usa.com',
             'hcollins@altaitech.com',
             'dblankley@uproar.com',

              'dblankley@uproar.us',
              'bp100a@hotmail.us'}

    _base_url = None

    def upload_photo(self, tu, photo_name, cid):

        dir_path = os.path.dirname(os.path.realpath(__file__))
        cwd = os.getcwd()

        # we have our user, now we need a photo to upload
        fn = 'photos/' + photo_name
        ft = open(fn, 'rb')
        assert (ft is not None)
        ph = ft.read()
        assert (ph is not None)

        # compose header with users authorization token
        h = Headers()
        h.add('content-type', 'application/json')
        h.add('Authorization', 'JWT ' + tu.get_token())

        # okay, we need to post this
        ext = 'JPEG'
        img = base64.standard_b64encode(ph)
        b64img = img.decode("utf-8")
        url = self._base_url + '/photo'
        rsp = requests.post(url, data=json.dumps(dict(category_id=cid, extension=ext, image=b64img)), headers=h)
        assert(rsp.status_code == 201)
        return

    def register_and_authenticate(self, tu):
        u = tu.get_username()
        p = tu.get_password()
        g = tu.get_guid()
        url = self._base_url + '/register'
        a_rsp = requests.post(url, data=json.dumps(dict(username=u, password=p, guid=g)), headers={'content-type':'application/json'})
        assert(a_rsp.status_code == 400 or a_rsp.status_code == 201)

         # now let's login this user
        url = self._base_url + '/auth'
        rsp = requests.post(url, data=json.dumps(dict(username=u, password=p)), headers={'content-type':'application/json'})

        if rsp.status_code == 200:
            data = json.loads(rsp.content.decode("utf-8"))
            token = data['access_token']
            tu.set_token(token)
        else:
            return None # this user didn't work!

        return rsp

    def read_category(self, token):

        # compose header with users authorization token
        h = Headers()
        h.add('content-type', 'text/html')
        h.add('Authorization', 'JWT ' + token)

        # now let's login this user
        url = self._base_url + '/category'
        rsp = requests.get(url, headers=h)
        assert(rsp.status_code == 200)

        cl = json.loads(rsp.content.decode("utf-8"))
        return cl

    def get_category_by_state(self, target_state, token):

        cl = self.read_category(token)
        assert(cl is not None)

        for c in cl:
            state = c['state']
            cid = c['id']
            desc = c['description']
            if state == 'VOTING' and target_state == category.CategoryState.VOTING:
                return cid
            if state == 'UPLOAD' and target_state == category.CategoryState.UPLOAD:
                return cid

        # we didn't find an upload category, set the first one to upload
        c = cl[0]
        cid = c['id']

        h = Headers()
        h.add('content-type', 'application/json')
        h.add('Authorization', 'JWT ' + token)

        url = self._base_url + '/setcategorystate'

        rsp = requests.post(url, data=json.dumps(dict(category_id=cid, state=target_state.value)),
                            headers=h)
        assert(rsp.status_code == 200)
        return cid

    def test_initialize_server(self):
        # okay, we're going to create users & upload photos
        self._base_url = 'http://104.198.176.198:8080'
        user_list = []
        for uname in self._users:
            tu = test_REST_login.TestUser()
            tu.create_user_with_name(uname)
            rsp = self.register_and_authenticate(tu)
            if rsp is not None:
                user_list.append(tu)

        if len(user_list) == 0:
            return

        # get the uploading category
        cid = self.get_category_by_state(category.CategoryState.UPLOAD, tu.get_token())

        # only upload a single photo in the category
        # for each user
        num_photos = len(self._photos)
        photo_idx = 0
        for tu in user_list:
            self.upload_photo(tu, self._photos[photo_idx], cid)
            photo_idx += 1
            if photo_idx > num_photos:
                photo_idx = 0

        return
