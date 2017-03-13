import os
import unittest
import json
import base64
import requests
from . test_REST_login import TestUser


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

    _photos = {'Cute_Puppy.jpg',
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
              'Turtle.JPG'}

    _users = {'hcollins@gmail.com',
             'bp100a@hotmail.com',
             'dblankley@blankley.com',
             'regcollins@hotmail.com',
             'qaetre@hotmail.com',
             'hcollins@prizepoint.com',
             'hcollins@exit15w.com',
             'harry.collins@epam.com',
             'crazycow@netsoft-usa.com'}

    _base_url = None

    def upload_photo(self, tu, photo_name):

        dir_path = os.path.dirname(os.path.realpath(__file__))
        cwd = os.getcwd()

        # we have our user, now we need a photo to upload
        fn = '../photos/' + photo_name
        ft = open(fn, 'rb')
        assert (ft is not None)
        ph = ft.read()
        assert (ph is not None)

        # okay, we need to post this
        uid = tu.get_uid()
        cid = tu.get_cid()
        ext = 'JPEG'
        img = base64.standard_b64encode(ph)
        b64img = img.decode("utf-8")
        url = self._base_url + '/photo'
        rsp = requests.post(url, data=json.dumps(dict(user_id=uid, category_id=cid, extension=ext, image=b64img)), headers={'content-type':'application/json'})
        assert(rsp.status_code == 201)
        return

    def register_and_login(self, tu):
        u = tu.get_username()
        p = tu.get_password()
        g = tu.get_guid()
        url = self._base_url + '/register'
        rsp = requests.post(url, data=json.dumps(dict(username=u, password=p, guid=g)), headers={'content-type':'application/json'})
        assert(rsp.status_code == 400 or rsp.status_code == 201)

         # now let's login this user
        url = self._base_url + '/login'
        rsp = requests.post(url, data=json.dumps(dict(username=u, password=p, guid=g)), headers={'content-type':'application/json'})
        assert(rsp.status_code == 200)

        if rsp.status_code == 200:
            data = json.loads(rsp.content.decode("utf-8"))
            uid = data['user_id']
            cid = data['category_id']
            tu.set_uid(uid)
            tu.set_cid(cid)

        return rsp

    def test_initialize_server(self):
        # okay, we're going to create users & upload photos
        self._base_url = 'http://104.198.176.198:8080'
        user_list = []
        for uname in self._users:
            tu = TestUser()
            tu.create_user_with_name(uname)
            rsp = self.register_and_login(tu)
            user_list.append(tu)

        # okay, we've registered & logged in our users
        # Now let's upload some images
        for tu in user_list:
            for pn in self._photos:
                self.upload_photo(tu, pn)

        return