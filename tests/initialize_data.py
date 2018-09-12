import os
import unittest
import json
import base64
import requests
from tests import test_REST_login
from models import category
from werkzeug.datastructures import Headers
import _thread
import time
from utilities import get_photo_fullpath

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

class PhotoCache():
    _b64img = None

    def __init__(self, photo_name):
        try:
            ft = open(get_photo_fullpath(photo_name), 'rb')
            assert (ft is not None)
            ph = ft.read()
            assert (ph is not None)
            img = base64.standard_b64encode(ph)
            self._b64img = img.decode("utf-8")
        except Exception as e:
            pass

class InitEnvironment(unittest.TestCase):


    _photos = ('Cute_Puppy.jpg',
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
               'IMG_0307.JPG',
               '001-B-Moto-Z-Force-Droid-Samples.jpg',
               'moto-z-play-camera-sample.jpg',
               'moto_z_play_camera_samples_7.jpg',
               'sample1.jpg',
               'Moto-Z-Force-Droid.jpg',
               'IMG_1218.JPG',
               'sam_4089.jpg',
               'Passaic River.JPG',
               'Suki on Balcony.JPG',
               'Kirby on Log.JPG',
               'Flowering Tree.JPG',
               'Two Dogs.JPG',
               'Troegs start.JPG',
               'First Dance Burag and Kea.JPG',
               'Emma in Lithuania.JPG',
               'Suki on Dash.JPG',
               'Taplist.JPG',
               'Portrait_1.jpg',
               'Portrait_2.jpg',
               'Portrait_3.jpg',
               'Portrait_4.jpg',
               'Portrait_5.jpg',
               'Portrait_6.jpg',
               'Portrait_7.jpg',
               'Portrait_8.jpg',
               'Landscape_1.jpg',
               'Landscape_2.jpg',
               'Landscape_3.jpg',
               'Landscape_4.jpg',
               'Landscape_5.jpg',
               'Landscape_6.jpg',
               'Landscape_7.jpg',
               'Landscape_8.jpg',
               'ADXF2532.jpg',
               'IMG_3278.JPG',
               'IMG_3277.JPG',
               'IMG_3201.JPG',
               'IMG_3202.JPG',
               'IMG_3203.JPG',
               'IMG_3200.JPG',
               'IMG_3199.JPG',
               'IMG_3224.JPG',
               'IMG_3197.JPG',
               'IMG_3199.JPG',
               'IMG_3218.JPG',
               'IMG_3163.JPG',
               'IMG_3164.JPG',
               'IMG_3188.JPG',
               'IMG_2970.JPG',
               'IMG_2966.JPG',
               'IMG_2929.JPG',
               'IMG_2444.JPG',
               'IMG_2441.JPG',
               'IMG_2464.JPG',
               'IMG_1763.JPG',
               'IMG_1771.JPG',
               'IMG_1797.JPG',
               'IMG_1831.JPG',
               'IMG_1833.JPG',
               'IMG_1849.JPG',
               'IMG_0855.JPG',
               'IMG_0951.JPG',

               'Samsung G7-1.jpg',
               'Samsung G7-2.jpg',
               'Samsung G7-3.jpg',
               'Samsung G7-4.jpg',
               'Samsung G7-5.jpg',

               # iPad Mini 2 images
               'IMG_0243.JPG', #square
               'IMG_0244.JPG',
               'IMG_0245.JPG',
               'IMG_0246.JPG',
               'IMG_0247.JPG', # non-square
               'IMG_0248.JPG',
               'IMG_0249.JPG',
               'IMG_0250.JPG'

               #'Emma Passport.jpg',
               #'img_0264_edited-100686951-orig.jpg',
               #'img_0026.jpg',
               #'img_0034.jpg',
               #'apple-iphone-7-camera-samples-27.jpg',
               #'Apple-iPhone-7-camera-photo-sample-2.jpg',
               #'iphone-7-plus-camera-trout.jpg',
               #'iPhone-7-Camera-AndyNicolaides.jpg',
               #'img_0017.jpg',
               #'9lqqdnm.jpg',
               #'tf2fzhr.jpg',
               #'vetndhl.jpg',
               )

    _pcache = []

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
              'bp100a@hotmail.us',
              'testuser1@hotmail.com',
              'testuser2@hotmail.com',
              'testuser3@hotmail.com',
              'testuser4@hotmail.com'
              }

    _base_url = None

    def upload_photo(self, tu, pc, cid):

        # compose header with users authorization token
        h = Headers()
        h.add('content-type', 'application/json')
        h.add('Authorization', 'JWT ' + tu.get_token())

        # okay, we need to post this
        ext = 'JPEG'
        url = self._base_url + '/photo'

        # we can occasionally get a '502, Bad Gateway', let's retry if we do'
        for i in range(0,2):
            rsp = requests.post(url, data=json.dumps(dict(category_id=cid, extension=ext, image=pc._b64img)), headers=h)
            if rsp.status_code != 502:
                break;

        assert(rsp.status_code == 201)
        return

    def register_and_authenticate(self, tu):
        u = tu.get_username()
        p = tu.get_password()
        g = tu.get_guid()
        url = self._base_url + '/register'
        a_rsp = requests.post(url, data=json.dumps(dict(username=u, password=p, guid=g)), headers={'content-type':'application/json'})
#        assert(a_rsp.status_code == 400 or a_rsp.status_code == 201)
        if a_rsp.status_code != 400 and a_rsp.status_code != 201:
            return None

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

    def massive_photo_upload(self):

        # load up the photos into our cache
        for p in self._photos:
            pc = PhotoCache(p)
            self._pcache.append(pc)

        num_photos = len(self._pcache)
        photo_idx = 0

        th = []

        cid = None
        for idx in range(100):
            uname = 'test_user{}@gmail.com'.format(idx)
            tu = test_REST_login.TestUser()
            tu.create_user_with_name(uname)
            rsp = self.register_and_authenticate(tu)
            if rsp is not None:
                if cid is None:
                    cid = self.get_category_by_state(category.CategoryState.UPLOAD, tu.get_token())
                try:
                    _thread.start_new_thread(self.upload_photos, (), {'user':tu, 'category_id':cid})
                except Exception as e:
                    pass

        c = 1
        while(c > 0):
            time.sleep(0.010)    # sleep 10ms
            c = _thread._count()

    def upload_photos(self, *args, **kwargs):
        '''
        upload all the photos for a single user
        :param args: 
        :param kwargs: user = tu object,
                       cid = category id
        :return: 
        '''
        tu = kwargs.get('user')
        cid = kwargs.get('category_id')

        for p in self._pcache:
            self.upload_photo(tu, p, cid)

        _thread.exit()

    def register_tst_users(self):
        user_list = []
        for uname in self._users:
            tu = test_REST_login.TestUser()
            tu.create_user_with_name(uname)
            rsp = self.register_and_authenticate(tu)
            if rsp is not None:
                user_list.append(tu)

        return user_list


    def test_initialize_server(self):
        # okay, we're going to create users & upload photos
#        self._base_url = 'http://104.198.176.198:8080'
        self._base_url = "https://api.imageimprov.com"

        return self.massive_photo_upload()

        user_list = self.register_tst_users()

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
