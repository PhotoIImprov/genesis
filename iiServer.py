import datetime
import base64

from flask import Flask, jsonify
from flask     import request, make_response
from flask_jwt import JWT, jwt_required, current_identity
from flask_api import status

import initschema
import dbsetup
from models import usermgr
from models import photo
from models import voting
from models import category
from models import error
import json

app = Flask(__name__)
app.debug = True
app.config['SECRET_KEY'] = 'super-secret'

is_gunicorn = False

# specify the JWT package's call backs for authentication of username/password
# and subsequent identity from the payload in the token
jwt = JWT(app, usermgr.authenticate, usermgr.identity)
JWT_AUTH = { 'JWT_EXPIRATION_DELTA': datetime.timedelta(days=10) } # 10 days before expiry

@app.route("/protected")
@jwt_required()
def protected():
    return '%s' % current_identity

@app.route("/")
def hello():
    htmlbody = "<html>\n"
    if dbsetup.is_gunicorn():
        htmlbody += "<h1>ImageImprov Hello World from Gunicorn!</h1><br>"
    else:
        htmlbody += "<h1>ImageImprov Hello World from Flask!</h1><br>"

    img_folder = dbsetup.image_store(dbsetup.determine_environment(None))
    htmlbody += "\n<br>image folder =" + img_folder + "<br>"

    return htmlbody

@app.route("/setcategorystate", methods=['POST'])
def set_category_state():
    if not request.json:
        return make_response(jsonify({'error': error.error_string('NO_JSON')}), status.HTTP_400_BAD_REQUEST)

    try:
        cid = request.json['category_id']
        cstate = request.json['state']
    except KeyError as e:
        cid = None
        cstate = None

    if cid is None:
        return make_response(jsonify({'error': error.error_string('MISSING_ARGS')}), status.HTTP_400_BAD_REQUEST)

    session = dbsetup.Session()

    d = category.Category.read_category_by_id(session, cid)

    if d['error'] is not None:
        session.close()
        return make_response(jsonify({'error': error.iiServerErrors.error_message(d['error'])}), error.iiServerErrors.http_status(d['error']))

    c = d['arg']
    if c is not None:
        c.state = cstate
        session.commit()
        session.close()
        return make_response(jsonify({'message': error.error_string('CATEGORY_STATE')}),status.HTTP_200_OK)

    session.close()
    return make_response(jsonify({'error': error.error_string('CATEGORY_ERROR')}), status.HTTP_500_INTERNAL_SERVER_ERROR)


@app.route("/category", methods=['GET'])
def get_category():
    if not request.json:
        return make_response(jsonify({'error': error.error_string('NO_JSON')}),status.HTTP_400_BAD_REQUEST)

    try:
        uid = request.json['user_id']
    except KeyError as e:
        uid = None

    if uid is None:
        return make_response(jsonify({'error': error.error_string('MISSING_ARGS')}),status.HTTP_400_BAD_REQUEST)

    session = dbsetup.Session()

    cl = category.Category.active_categories(session, uid)
    session.close()
    if cl is None:
        return make_response(jsonify({'error': error.error_string('CATEGORY_ERROR')}), status.HTTP_500_INTERNAL_SERVER_ERROR)

    categories = category.Category.list_to_json(cl)
    return make_response(jsonify({'categories': categories}), status.HTTP_200_OK)

@app.route("/leaderboard", methods=['GET'])
def get_leaderboard():
    if not request.json:
        return make_response(jsonify({'error': error.error_string('NO_JSON')}),status.HTTP_400_BAD_REQUEST)

    try:
        cid = request.json['category_id']
    except KeyError:
        return make_response(jsonify({'error': error.error_string('MISSING_ARGS')}),status.HTTP_400_BAD_REQUEST)

    return make_response(jsonify({'message': "TBD - leader board not implemented"}), 200)

@app.route("/ballot", methods=['GET'])
def get_ballot():
    if not request.json:
        return make_response(jsonify({'error': error.error_string('NO_JSON')}),status.HTTP_400_BAD_REQUEST)

    try:
        uid = request.json['user_id']
        cid = request.json['category_id']
    except KeyError:
        uid = None
        cid = None

    session = dbsetup.Session()
    if uid is None or cid is None or session is None:
        session.close()
        return make_response(jsonify({'error': error.error_string('MISSING_ARGS')}),status.HTTP_400_BAD_REQUEST)

    b = voting.Ballot.create_ballot(session, uid, cid)
    if b is None:
        session.close()
        return make_response(jsonify({'error': error.error_string('NO_BALLOT')}),status.HTTP_500_INTERNAL_SERVER_ERROR)

    # we have a ballot, turn it into JSON
    ballots = b.to_json()
    session.close()
    return make_response(jsonify({'ballots': ballots}), status.HTTP_200_OK)

@app.route("/acceptfriendrequest", methods=['POST'])
def accept_friendship():
    if not request.json:
        return make_response(jsonify({'error': error.error_string('NO_JSON')}), status.HTTP_400_BAD_REQUEST)

    try:
        uid = request.json['user_id']
        fid = request.json['request_id'] # id of the friendship request
        accepted = request.json['accepted'] == "true" # = True, then friendship accepted
    except KeyError:
        fid = None
        accepted = None

    if fid is None or accepted is None:
        return make_response(jsonify({'error': error.error_string('MISSING_ARGS')}), status.HTTP_400_BAD_REQUEST)

    session = dbsetup.Session()
    usermgr.FriendRequest.update_friendship(session, uid, fid, accepted)
    session.close()

    return make_response(jsonify({'message': error.error_string('FRIENDSHIP_UPDATED')}), status.HTTP_201_CREATED)

@app.route("/friendrequest", methods=['POST'])
def tell_a_friend():
    if not request.json:
        return make_response(jsonify({'error': error.error_string('NO_JSON')}), status.HTTP_400_BAD_REQUEST)

    try:
        uid = request.json['user_id']  # user that's notifying a friend
        friend = request.json['friend']  # email address of friend to notify
    except KeyError:
        uid = None
        friend = None

    if uid is None or friend is None:
        return make_response(jsonify({'error': error.error_string('MISSING_ARGS')}), status.HTTP_400_BAD_REQUEST)

    session = dbsetup.Session()
    request_id = usermgr.FriendRequest.write_request(session, uid, friend)
    session.close()

    if request_id != 0:
        return make_response(jsonify({'message': error.error_string('WILL_NOTIFY_FRIEND'), 'request_id':request_id}), status.HTTP_201_CREATED)

    return make_response(jsonify({'error': error.error_string('FRIEND_REQ_ERROR')}), status.HTTP_500_INTERNAL_SERVER_ERROR)

@app.route("/vote", methods=['POST'])
def cast_vote():
    if not request.json:
        return make_response(jsonify({'error': error.error_string('NO_JSON')}), status.HTTP_400_BAD_REQUEST)

    try:
        uid = request.json['user_id']
        votes = request.json['votes']  # list of dict() with the actual votes
    except KeyError:
        uid = None
        votes = None

    if uid is None or votes is None:
        return make_response(jsonify({'error': error.error_string('MISSING_ARGS')}), status.HTTP_400_BAD_REQUEST)

#    assert(len(votes) == 4)

    if len(votes) > 4:
        return make_response(jsonify({'error': error.error_string('TOO_MANY_BALLOTS')}), status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)


    session = dbsetup.Session()

    voting.Ballot.tabulate_votes(session, uid, votes)
    session.close()
    return make_response(jsonify({'message': error.error_string('THANK_YOU_VOTING')}), status.HTTP_200_OK)

@app.route("/photo", methods=['POST'])
#@jwt_required()
def photo_upload():
    if not request.json:
        return make_response(jsonify({'error': error.error_string('NO_JSON')}), status.HTTP_400_BAD_REQUEST)

    try:
        image_data_b64 = request.json['image']
        image_type     = request.json['extension']
        cid    = request.json['category_id']
        uid = request.json['user_id']
    except KeyError:
        cid = None
        uid = None

    if cid is None or uid is None:
        return make_response(jsonify({'error': error.error_string('MISSING_ARGS')}), status.HTTP_400_BAD_REQUEST)

    image_data = base64.b64decode(image_data_b64)
#    uid = current_identity
    session = dbsetup.Session()
    d = photo.Photo().save_user_image(session, image_data, image_type, uid, cid)
    session.close()
    if d['error'] is not None:
        return make_response(jsonify({'error': error.iiServerErrors.error_message(d['error'])}), error.iiServerErrors.http_status(d['error']))

    return make_response(jsonify({'message': error.error_string('PHOTO_UPLOADED')}), status.HTTP_201_CREATED)

@app.route("/login", methods=['POST'])
def login():
    if not request.json:
        return make_response(jsonify({'error': error.error_string('NO_JSON')}), status.HTTP_400_BAD_REQUEST)

    try:
        emailaddress = request.json['username']
        password     = request.json['password']
    except KeyError:
        emailaddress = None
        password = None

    if emailaddress is None or password is None:
        return make_response(jsonify({'error': error.error_string('MISSING_ARGS')}), status.HTTP_400_BAD_REQUEST)

    foundUser = usermgr.authenticate(emailaddress, password)
    if foundUser is None:
        return make_response(jsonify({'error': error.error_string('NO_SUCH_USER')}), status.HTTP_403_FORBIDDEN)

    uid = foundUser.get_id()
    session = dbsetup.Session()
    c = category.Category.current_category(session, uid, category.CategoryState.UPLOAD)
    session.close()
    if c is None:
        cid = 0
    else:
        cid = c.get_id()

    return make_response(jsonify({'user_id':uid, 'category_id':cid}), status.HTTP_200_OK)


@app.route("/register", methods=['POST'])
def register():
    # an email address and password has been posted
    # let's create a user for this
    if not request.json:
        return make_response(jsonify({'error': error.error_string('NO_JSON')}), status.HTTP_400_BAD_REQUEST)

    try:
        emailaddress = request.json['username']
        password     = request.json['password']
        guid         = request.json['guid']
    except KeyError:
        emailaddress = None
        password = None

    if emailaddress is None or password is None:
        return make_response(jsonify({'error': error.error_string('MISSING_ARGS')}), status.HTTP_400_BAD_REQUEST)

    # is the username really a guid?
    session = dbsetup.Session()
    if usermgr.AnonUser.is_guid(emailaddress, password):
        foundAnonUser = usermgr.AnonUser.find_anon_user(session, emailaddress)
        if foundAnonUser is not None:
            session.close()
            return make_response(jsonify({'error': error.error_string('ANON_ALREADY_EXISTS')}), status.HTTP_400_BAD_REQUEST)

        newAnonUser = usermgr.AnonUser.create_anon_user(session, emailaddress)
        if newAnonUser is None:
            session.close()
            return make_response(jsonify({'error': error.error_string('ANON_USER_ERROR')}), status.HTTP_500_INTERNAL_SERVER_ERROR)
    else:
        foundUser = usermgr.User.find_user_by_email(session, emailaddress)
        if foundUser is not None:
            session.close()
            return make_response(jsonify({'error':error.error_string('USER_ALREADY_EXISTS')}), status.HTTP_400_BAD_REQUEST)

        # okay the request is valid and the user was not found, so we can
        # create their account
        newUser = usermgr.User.create_user(session, guid, emailaddress, password)
        if newUser is None:
            session.close()
            return make_response(jsonify({'error': error.error_string('USER_CREATE_ERROR')}),status.HTTP_500_INTERNAL_SERVER_ERROR)

    # user was properly created
    session.close()
    return make_response(jsonify({'message': error.error_string('ACCOUNT_CREATED')}), 201)


if __name__ == '__main__':
    dbsetup.metadata.create_all(bind=dbsetup.engine, checkfirst=True)

    session = dbsetup.Session()

    au = usermgr.AnonUser.create_anon_user(session, '99275132efe811e6bc6492361f002671')
    if au is not None:
        u = usermgr.User.create_user(session, au.guid, 'hcollins@gmail.com', 'pa55w0rd')
        if u is not None:
            # see if we can read it back
            foundUser = usermgr.User.find_user_by_email(session, 'hcollins@gmail.com')
            if foundUser is not None:
                foundUser.change_password(session, 'pa55w0rd')

    if not dbsetup.is_gunicorn():
        app.run(host='0.0.0.0', port=8080)
