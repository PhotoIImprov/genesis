from flask import Flask, jsonify
from flask_jwt import JWT, jwt_required, current_identity
from flask     import request, abort
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

    foundUser = usermgr.User().FindUserByEmail(usermgr.Session(), emailaddress)
    if foundUser is not None:
        abort(400)  # user exists!

    # okay the request is valid and the user was not found, so we can
    # create their account
    newUser = usermgr.User().CreateUser(usermgr.Session(), emailaddress, password)
    if newUser is None:
        abort(500)

    # user was properly created
    return 'account created', 201

#check to see if we are running a server
is_gunicorn = "gunicorn" in os.environ.get("SERVER_SOFTWARE", "")

if __name__ == '__main__':
    usermgr.metadata.create_all(bind=usermgr.engine, checkfirst=True)

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
