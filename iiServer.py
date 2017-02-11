from flask import Flask, jsonify
from flask_jwt import JWT, jwt_required, current_identity
from flask     import request, abort
import dbsetup

import os

import usermgr


app = Flask(__name__)
app.debug = True
app.config['SECRET_KEY'] = 'super-secret'

is_gunicorn = False

# specify the JWT package's call backs for authentication of username/password
# and subsequent identity from the payload in the token
jwt = JWT(app, usermgr.authenticate, usermgr.identity)

@app.route("/protected")
@jwt_required()
def protected():
    return '%s' % current_identity

@app.route("/")
def hello():
    if is_gunicorn == True:
        return "ImageImprov Hello World from Gunicorn!"

    return "ImageImprov Hello World from Flask!"

@app.route("/register_anon", methods=['POST'])
def register_anon():

    if not request.json:
        abort(400)  # no data passed

    guid = request.json['guid'] #uniquely identifies the user
    foundAnon = usermgr.AnonUser().find_anon_user(usermgr.Session(), guid)
    if foundAnon is not None:
        abort(400) # user exists!

    # create the anonymous account
    newAnon = usermgr.AnonUser().create_anon_user(usermgr.Session(), guid)
    if newAnon is None:
        abort(500)  # server side issue ??

    return "anonymous account created", 201

@app.route("/register", methods=['POST'])
def register():
    # an email address and password has been posted
    # let's create a user for this
    if not request.json:
        abort(400)  # no data passed!

    emailaddress = request.json['username']
    password     = request.json['password']
    if emailaddress is None or password is None:
        abort(400) # missing important data!

    foundUser = usermgr.User().find_user_by_email(usermgr.Session(), emailaddress)
    if foundUser is not None:
        abort(400)  # user exists!

    # okay the request is valid and the user was not found, so we can
    # create their account
    newUser = usermgr.User().create_user(usermgr.Session(), emailaddress, password)
    if newUser is None:
        abort(500)

    # user was properly created
    return 'account created', 201

#check to see if we are running a server
is_gunicorn = "gunicorn" in os.environ.get("SERVER_SOFTWARE", "")

if __name__ == '__main__':
    dbsetup.metadata.create_all(bind=usermgr.engine, checkfirst=True)

    session = usermgr.Session()

    new_anon = usermgr.AnonUser()
    new_anon.create_anon_user(session, '99275132efe811e6bc6492361f002671')

    new_user = usermgr.User()
    new_user.create_user(session, new_anon.guid, 'hcollins@gmail.com', 'pa55w0rd')

    # see if we can read it back
    foundUser = usermgr.User().find_user_by_email(session, 'hcollins@gmail.com')

    if foundUser != None:
        foundUser.change_password('pa55w0rd')

    if is_gunicorn == False:
        app.run(host='0.0.0.0', port=8080)
