from unittest import TestCase
import initschema
import datetime
import os, errno
import uuid
from models import resources
from models import voting, category, usermgr, photo
from . import DatabaseTest

class TestLeaderBoard(DatabaseTest):

    def test_new_leader(self):
        self.setup()

        ft = open('../photos/Cute_Puppy.jpg', 'rb')
        assert (ft is not None)
        ph = ft.read()
        assert (ph is not None)

        # first we need a resource
        r = resources.Resource.create_resource(5555, 'EN', 'Kittens')
        resources.Resource.write_resource(self.session, r)

        # now create our category
        s_date = datetime.datetime.now()
        e_date =  s_date + datetime.timedelta(days=1)
        c = category.Category.create_category(r.resource_id, s_date, e_date, category.CategoryState.UPLOAD)
        c.set_state(category.CategoryState.UPLOAD) # potentially very bad
        category.Category.write_category(self.session, c)

        # create a user
        for idx in range(10):
            guid = 'AFA3540CCDD24B8686E3DDD75D84EF' + '{0:02d}'.format(idx)
            au = usermgr.AnonUser.create_anon_user(self.session, guid)
            if au is not None:
                email = 'testlb_{}@gmail.com'.format(idx)
                u = usermgr.User.create_user(self.session, au.guid, email, 'pa55w0rd')
            # Now add a photo for this user
                # read our test file
                fo = photo.Photo()
                assert (fo is not None)
                fo.category_id = c.id
                fo.save_user_image(self.session, ph, "JPEG", au.id,c.id)

                # now that the photo has been created, let's updated it's vote count
                fo.increment_vote_count()
                fo.increment_likes()
                fo.update_score(idx+1)
                self.session.commit() # this should fire the trigger

        return
