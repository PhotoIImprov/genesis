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
    if is_gunicorn == True:
        return "ImageImprov Hello World from Gunicorn!"

    return "ImageImprov Hello World from Flask!"

@app.route("/leaderboard", methods=['GET'])
def get_leaderboard():
    if not request.json:
        return make_response(jsonify({'error': "insufficient arguments"}),status.HTTP_400_BAD_REQUEST)

    cid = request.json['category_id']
    return make_response(jsonify({'message': "TBD - leader board not implemented"}), 200)

@app.route("/ballot", methods=['GET'])
def get_ballot():
    if not request.json:
        return make_response(jsonify({'error': "insufficient arguments"}),status.HTTP_400_BAD_REQUEST)

    uid = request.json['user_id']
    cid = request.json['category_id']
    session = dbsetup.Session()
    if uid is None or cid is None or session is None:
        session.close()
        return make_response(jsonify({'error': "invalid arguments"}),status.HTTP_500_INTERNAL_SERVER_ERROR)

    b = voting.Ballot.create_ballot(session, uid, cid)
    if b is None:
        session.close()
        return make_response(jsonify({'error': "no ballot created!"}),status.HTTP_500_INTERNAL_SERVER_ERROR)

    # we have a ballot, turn it into JSON
    ballots = b.to_json()
    session.close()
    return make_response(jsonify({'ballots': ballots}), status.HTTP_200_OK)

@app.route("/vote", methods=['POST'])
def cast_vote():
    if not request.json:
        return make_response(jsonify({'error': "insufficient arguments"}), status.HTTP_400_BAD_REQUEST)

    uid = request.json['user_id']
    ballots=request.json['ballots']
    session = dbsetup.Session()

    voting.Ballot.tabulate_votes(session, uid, ballots)
    session.close()
    return make_response(jsonify({'message': "thank you for voting"}), status.HTTP_200_OK)

@app.route("/photo", methods=['POST'])
#@jwt_required()
def photo_upload():
    if not request.json:
        return make_response(jsonify({'error': "insufficient arguments"}), status.HTTP_400_BAD_REQUEST)

    image_data_b64 = request.json['image']
    image_type     = request.json['extension']
    cid    = request.json['category_id']
    uid = request.json['user_id']
    image_data = base64.b64decode(image_data_b64)
#    uid = current_identity
    session = dbsetup.Session()
    photo.Photo().save_user_image(session, image_data, image_type, uid, cid)
    session.close()
    return make_response(jsonify({'message': "photo uploaded"}), status.HTTP_201_CREATED)

@app.route("/login", methods=['POST'])
def login():
    if not request.json:
        return make_response(jsonify({'error': "insufficient arguments"}), status.HTTP_400_BAD_REQUEST)

    emailaddress = request.json['username']
    password     = request.json['password']

    if emailaddress is None or password is None:
        return make_response(jsonify({'error': "insufficient arguments"}), status.HTTP_400_BAD_REQUEST)

    foundUser = usermgr.authenticate(emailaddress, password)
    if foundUser is None:
        return make_response(jsonify({'error': "no such user!"}), status.HTTP_403_FORBIDDEN)

    uid = foundUser.get_id()
    session = dbsetup.Session()
    c = category.Category.current_category(session, uid)
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
        return make_response(jsonify({'error': "insufficient arguments"}), status.HTTP_400_BAD_REQUEST)

    emailaddress = request.json['username']
    password     = request.json['password']
    guid         = request.json['guid']

    if emailaddress is None or password is None:
        return make_response(jsonify({'error': "insufficient arguments"}), status.HTTP_400_BAD_REQUEST)

    # is the username really a guid?
    session = dbsetup.Session()
    if usermgr.AnonUser.is_guid(emailaddress, password):
        foundAnonUser = usermgr.AnonUser.find_anon_user(session, emailaddress)
        if foundAnonUser is not None:
            session.close()
            return make_response(jsonify({'error': "user already exists"}), status.HTTP_400_BAD_REQUEST)

        newAnonUser = usermgr.AnonUser.create_anon_user(session, emailaddress)
        if newAnonUser is None:
            session.close()
            return make_response(jsonify({'error': "error creating anon user"}), status.HTTP_500_INTERNAL_SERVER_ERROR)
    else:
        foundUser = usermgr.User.find_user_by_email(session, emailaddress)
        if foundUser is not None:
            session.close()
            return make_response(jsonify({'error': "user already exists!"}), status.HTTP_400_BAD_REQUEST)

        # okay the request is valid and the user was not found, so we can
        # create their account
        newUser = usermgr.User.create_user(session, guid, emailaddress, password)
        if newUser is None:
            session.close()
            return make_response(jsonify({'error': "error creating user"}),status.HTTP_500_INTERNAL_SERVER_ERROR)

    # user was properly created
    session.close()
    return make_response(jsonify({'message': "account created"}), 201)


if __name__ == '__main__':
    dbsetup.metadata.create_all(bind=dbsetup.engine, checkfirst=True)

    session = dbsetup.Session()

    au = usermgr.AnonUser.create_anon_user(session, '99275132efe811e6bc6492361f002671')
    if au is not None:
        u = usermgr.User.create_user(session, au.guid, 'hcollins@gmail.com', 'pa55w0rd')
        if u is not None:
            # see if we can read it back
            foundUser = usermgr.User.find_user_by_email(session, 'hcollins@gmail.com')
            if foundUser != None:
                foundUser.change_password(session, 'pa55w0rd')

    if dbsetup._is_gunicorn == False:
        app.run(host='0.0.0.0', port=8080)
