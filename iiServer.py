import datetime
import base64

from flask import Flask, jsonify
from flask     import request, abort, make_response
from flask_jwt import JWT, jwt_required, current_identity

import initschema
import dbsetup
from models import usermgr
from models import photo
from models import voting

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
        abort(400, message="no arguments")

    cid = request.json['category_id']
    return 'here is the leader board', 200

@app.route("/ballot", methods=['GET'])
def get_ballot():
    if not request.json:
        abort(400, message="no arguments")

    uid = request.json['user_id']
    cid = request.json['category_id']
    session = dbsetup.Session()
    if uid is None or cid is None or session is None:
        abort(500, message='invalid arguments')

    b = voting.Ballot.create_ballot(session, uid, cid)
    if b is None:
        abort(500, message='no ballot created!')

    # we have a ballot, turn it into JSON
    json_str = b.to_json()
    return make_response(jsonify(json_str), 200)

@app.route("/vote", methods=['POST'])
def cast_vote():
    if not request.json:
        abort(400, message="no arguments")

    uid = request.json['user_id']
    ballots=request.json['ballots']
    session = dbsetup.Session()

    voting.Ballot.tabulate_votes(session, uid, ballots)
    return 'thank you for voting', 200

@app.route("/photo", methods=['POST'])
#@jwt_required()
def photo_upload():
    if not request.json:
        abort(400, message="no arguments")

    image_data_b64 = request.json['image']
    image_type     = request.json['extension']
    cid    = request.json['category_id']
    uid = request.json['user_id']
    image_data = base64.b64decode(image_data_b64)
#    uid = current_identity
    session = dbsetup.Session()
    photo.Photo().save_user_image(session, image_data, image_type, uid, cid)

    return 'photo uploaded', 201

@app.route("/register", methods=['POST'])
def register():
    # an email address and password has been posted
    # let's create a user for this
    if not request.json:
        abort(400, message="no arguments")  # no data passed!

    emailaddress = request.json['username']
    password     = request.json['password']
    guid         = request.json['guid']

    if emailaddress is None or password is None:
        abort(400, message="insufficient arguements") # missing important data!

    # is the username really a guid?
    session = dbsetup.Session()
    if usermgr.AnonUser.is_guid(emailaddress, password):
        foundAnonUser = usermgr.AnonUser.find_anon_user(session, emailaddress)
        if foundAnonUser is not None:
            return make_response(jsonify({'error': "user already exists!"}),400)

        newAnonUser = usermgr.AnonUser.create_anon_user(session, emailaddress)
        if newAnonUser is None:
            return make_response(jsonify({'error': "error creating anon user"}),500)
    else:
        foundUser = usermgr.User.find_user_by_email(session, emailaddress)
        if foundUser is not None:
            return make_response(jsonify({'error': "user already exists!"}),400)

        # okay the request is valid and the user was not found, so we can
        # create their account
        newUser = usermgr.User.create_user(session, guid, emailaddress, password)
        if newUser is None:
            abort(500, message="error creating user")

    # user was properly created
    return 'account created', 201


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
