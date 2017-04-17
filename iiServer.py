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
from flask_swagger import swagger
from leaderboard.leaderboard import Leaderboard
import random
import logging


app = Flask(__name__)
app.debug = True
app.config['SECRET_KEY'] = 'imageimprove3077b47'

is_gunicorn = False

__version__ = '0.2.0' #our version string PEP 440

# specify the JWT package's call backs for authentication of username/password
# and subsequent identity from the payload in the token
#JWT_AUTH = { 'JWT_EXPIRATION_DELTA': datetime.timedelta(days=10) } # 10 days before expiry
app.config['JWT_EXPIRATION_DELTA'] = datetime.timedelta(days=10)

jwt = JWT(app, usermgr.authenticate, usermgr.identity)

@app.route("/protected")
@jwt_required()
def protected():
    return '%s' % current_identity

@app.route("/spec")
def spec():
    swag = swagger(app)
    swag['info']['title'] = "ImageImprov API"
    swag['info']['version'] = __version__
    swag['info']['description'] = "The first version of the ImageImprov API is purely designed to interaction\n"\
                                 "with the ImageImprov mobile clients. We are aiming for a secure interface that\n" \
                                 "will implement our needed features in a simple programming model\n"\
                                 "\n"\
                                 "All endpoints are only accessible via https and are located at\n"\
                                 "\'api.imageimprove.com\'. Users do not need to provide any information\n"\
                                 "in order to enjoy our service, we fully support anonymous registration & play\n"\
                                 "\n\n"\
                                 "## Limits\n"\
                                 "We are currently only allowing a single photo upload per category per period the\n"\
                                 "category is open for uploading\n"
    swag['host'] = "echo-api.endpoints.ImageImprov.cloud.goog"
    swag['swagger'] = "2.0"
    return jsonify(swag)

@app.route("/")
def hello():
    htmlbody = "<html>\n<body>\n"
    if dbsetup.is_gunicorn():
        htmlbody += "<h1>ImageImprov Hello World from Gunicorn!</h1>"
        htmlbody += "<img src=\"/static/gunicorn_banner.jpg\"/>"
    else:
        htmlbody += "<h1>ImageImprov Hello World from Flask!</h1>"

    htmlbody += "<h2>Version {}</h2><br>".format(__version__)
    htmlbody += "<img src=\"/static/python_flask_mysql_banner.jpg\"/>\n"

    img_folder = dbsetup.image_store(dbsetup.determine_environment(None))
    htmlbody += "\n<br><b>image folder</b> =\"" + img_folder + "\""
    htmlbody += "\n<br>Flask instance path = \"" + app.instance_path + "\"\n"

    htmlbody += "<br>\n"

    # display current connection string, without username/password!
    cs = dbsetup.connection_string(None)
    cs2 = cs.split("@",1)
    htmlbody += "<h2>connection string:</h2>" + cs2[1] + "<br>\n"

    session = dbsetup.Session()

    rd = voting.ServerList().get_redis_server(session)
    if rd is not None:
        ip = rd['ip']
        port = str(rd['port'])
        htmlbody += "<h3>Redis server:</h3>" + ip + ':' + port + "<br>\n"
    else:
        htmlbody += "<h3>Error reading Redis server configuration!</h3><br>\n"

    cl = category.Category.active_categories(session, 1)
    if cl is None:
        htmlbody += "\n<br>No category information retrieved (ERROR)<br>"
    else:
        htmlbody += "\n<br><h3>Categories:</h3>"
        htmlbody += "\n<blockquote>"
        for c in cl:
            htmlbody += "\n<br>category_id = {}".format(c.get_id())
            htmlbody += "\n<br>description = \"{}\"".format(c.get_description())
            htmlbody += "\n<br>state = <b>{}</b>".format(category.CategoryState.to_str(c.state))
            htmlbody += "\n<br>start date={}".format(c.start_date)
            htmlbody += "\n<br>end date={}".format(c.end_date)
            num_photos = photo.Photo.count_by_category(session, c.get_id())
            htmlbody += "\n<br><u>number photos uploaded = <b>{}</b></u>".format(num_photos)
            htmlbody += "\n<br><br>"
        htmlbody += "\n</blockquote>"

    # let's see if we can access the leaderboard class, hence redis server is up
    lb_name = 'configtest'
    try:
        rd = voting.ServerList().get_redis_server(session)
        lb = Leaderboard(lb_name, host=rd['ip'], port=rd['port'], page_size=10)
        lb.check_member('no one')
        htmlbody += "<img src=\"/static/redis.png\"/>"
        htmlbody += "<br>leader board \'{}\' created<br>".format(lb_name)
        lb.delete_leaderboard()
    except:
        htmlbody += "\n<h2>Cannot create leaderboard!!</h2> (is redis server running?)<br>"

    au = usermgr.AnonUser.create_anon_user(session, '99275132efe811e6bc6492361f002671')
    if au is not None:
        u = usermgr.User.create_user(session, au.guid, 'hcollins@gmail.com', 'pa55w0rd')
        if u is not None:
            # see if we can read it back
            foundUser = usermgr.User.find_user_by_email(session, 'hcollins@gmail.com')
            if foundUser is not None:
                foundUser.change_password(session, 'pa55w0rd')
                htmlbody += "successfully created a test user<br>"
            else:
                htmlbody += "<h2>Problem finding user just created!</h2><br>"
        else:
            htmlbody += "<h2>Could not create a user account!!</h2><br>"
    else:
        htmlbody += "<h2>Could not create an anonymous user!!</h2><br>"

    # just some fun!
    quote, author = random.choice(dbsetup.QUOTES)
    htmlbody += "\n<br><b>Quote </b>&nbsp<i>{}</i>&nbsp by {}<br><br>".format(quote, author)
    htmlbody += "\n</body>\n</html>"

    session.close()

    return htmlbody

@app.route("/setcategorystate", methods=['POST'])
@jwt_required()
def set_category_state():
    """
    Set Category State
    ---
    tags:
      - category
    operationId: set-category-state
    consumes:
      - application/json
    produces:
      - application/json
    parameters:
      - in: body
        name: arguments
        schema:
          id: category_state
          required:
            - category_id
            - state
          properties:
            category_id:
              type: integer
            state:
              type: integer
    responses:
      '200':
        description: "state changed"
      '400':
        description: missing required arguments
      '500':
        description: error operating on category id specified
    """
    if not request.json:
        return make_response(jsonify({'msg': error.error_string('NO_JSON')}), status.HTTP_400_BAD_REQUEST)

    try:
        cid = request.json['category_id']
        cstate = request.json['state']
    except KeyError as e:
        cid = None
        cstate = None

    if cid is None:
        return make_response(jsonify({'msg': error.error_string('MISSING_ARGS')}), status.HTTP_400_BAD_REQUEST)

    session = dbsetup.Session()

    tm = voting.TallyMan()
    d = tm.change_category_state(session, cid, cstate)
    session.close()
    if d['error'] is not None:
        return make_response(jsonify({'msg': error.iiServerErrors.error_message(d['error'])}), error.iiServerErrors.http_status(d['error']))

    c = d['arg']
    if c is not None:
       return make_response(jsonify({'msg': error.error_string('CATEGORY_STATE')}),status.HTTP_200_OK)

    dbsetup.log_error(request, error.iiServerErrors.error_message(d['error']), None)

    return make_response(jsonify({'msg': error.iiServerErrors.error_message(d['error'])}), status.HTTP_500_INTERNAL_SERVER_ERROR)


@app.route("/category", methods=['GET'])
@jwt_required()
def get_category():
    """
    Fetch Category
    ---
    tags:
      - category
    summary: Fetched specified category information
    operationId: get-category
    consumes:
      - text/plain
    produces:
      - application/json
    responses:
      '200':
        description: state changed
        schema:
          id: categories
          type: array
          items:
            $ref: '#/definitions/Category'
      '400':
        description: "missing required arguments"
      '500':
        description: "error getting categories"
    definitions:
      - schema:
          id: Category
          properties:
            id:
              type: integer
              description: category identifier
            theme:
              type: string
              description: A brief description of the category
            start:
              type: string
              description: When the category starts and uploading can begin
            end:
              type: string
              description: When the category ends and voting can begin
            state:
              type: string
              description: The current state of the category (VOTING, UPLOADING, CLOSED, etc.)
    """
    uid = current_identity.id

    if uid is None:
        dbsetup.log_error(request, error.error_string('MISSING_ARGS'), None)
        return make_response(jsonify({'msg': error.error_string('MISSING_ARGS')}),status.HTTP_400_BAD_REQUEST)

    session = dbsetup.Session()

    cl = category.Category.active_categories(session, uid)
    session.close()
    if cl is None:
        dbsetup.log_error(request, error.error_string('CATEGORY_ERROR'), None)
        return make_response(jsonify({'msg': error.error_string('CATEGORY_ERROR')}), status.HTTP_500_INTERNAL_SERVER_ERROR)

    categories = category.Category.list_to_json(cl)
    return make_response(jsonify(categories), status.HTTP_200_OK)

@app.route("/leaderboard", methods=['GET'])
@jwt_required()
def get_leaderboard():
    """
    Get Leader Board
    ---
    tags:
      - user
    operationId: get-leaderboard
    parameters:
      - in: query
        name: category_id
        description: Category of the leaderboard being requested
        required: true
        type: integer
    responses:
      '200':
        description: leaderboard retrieved
        schema:
          id: scores
          type: array
          items:
            $ref: '#/definitions/ranking'
      '400':
        description: missing required arguments
      '500':
        description: error getting categories
    definitions:
      - schema:
          id: ranking
          properties:
            username:
              type: string
              description: username of member of this rank
            rank:
              type: integer
              description: overall rank in scoring
            score:
              type: integer
              description: actual score for this rank
            you:
              type: string
              description: if set, then this rank is yours
            isfriend:
              type: string
              description: if set, then this rank is for a friend of yours
    
    """
    if not request.args:
        return make_response(jsonify({'msg': error.error_string('NO_ARGS')}),status.HTTP_400_BAD_REQUEST)

    cid = request.args.get('category_id')
    u = current_identity
    uid = u.id

    if cid is None or cid == 'None' or uid is None:
        return make_response(jsonify({'msg': error.error_string('MISSING_ARGS')}),status.HTTP_400_BAD_REQUEST)

    tm = voting.TallyMan()
    session = dbsetup.Session()
    d = tm.create_leaderboard(session, uid, cid)
    session.close()

    if d is not None:
        return make_response(jsonify(d), 200)

    return make_response(jsonify({'msg': error.error_string('NO_LEADERBOARD')}), status.HTTP_500_INTERNAL_SERVER_ERROR)

@app.route("/ballot", methods=['GET'])
@jwt_required()
def get_ballot():
    """
    Get Ballot()
    ---
    tags:
      - voting
    operationId: get-ballot
    parameters:
      - in: query
        name: category_id
        description: "The category we want to vote on"
        required: true
        type: integer
    responses:
      200:
        description: "ballot"
        schema:
          id: category
          title: Categories
          type: array
          items:
            $ref: '#/definitions/Ballot'
      400:
        description: "missing required arguments"
      500:
        description: "no ballot"
      default:
        description: "unexpected error"
    definitions:
      - schema:
          id: Ballot
          properties:
            bid:
              type: integer
            image:
              type: string
    """
    if not request.args:
        return make_response(jsonify({'msg': error.error_string('NO_ARGS')}),status.HTTP_400_BAD_REQUEST)

    u = current_identity
    uid = u.id
    cid = request.args.get('category_id')

    if uid is None or cid is None or cid == 'None':
        return make_response(jsonify({'msg': error.error_string('MISSING_ARGS')}),status.HTTP_400_BAD_REQUEST)

    session = dbsetup.Session()
    # REALLY DON'T NEED THIS IF JWT token has identity!
    au = usermgr.AnonUser.get_anon_user_by_id(session, uid)
    session.close()
    if au is None:
        return make_response(jsonify({'msg': error.error_string('NO_SUCH_USER')}),status.HTTP_400_BAD_REQUEST)

    return return_ballot(session, uid, cid)

@app.route("/acceptfriendrequest", methods=['POST'])
@jwt_required()
def accept_friendship():
    """
        Accept Friend Request
        ---
        tags:
          - user
        operationId: accept-friendship
        consumes:
          - application/json
        parameters:
          - in: body
            name: body
            schema:
              id: friendreq
              required:
                - request_id
              properties:
                request_id:
                  type: integer
        responses:
          200:
            description: "friendship updated"
          400:
            description: missing required arguments
          500:
            description: error operating on category id specified
        """
    if not request.json:
        return make_response(jsonify({'msg': error.error_string('NO_JSON')}), status.HTTP_400_BAD_REQUEST)

    try:
        u = current_identity
        uid = u.id
        fid = request.json['request_id'] # id of the friendship request
        accepted = request.json['accepted'] == "true" # = True, then friendship accepted
    except KeyError:
        fid = None
        accepted = None

    if fid is None or accepted is None:
        return make_response(jsonify({'msg': error.error_string('MISSING_ARGS')}), status.HTTP_400_BAD_REQUEST)

    session = dbsetup.Session()
    usermgr.FriendRequest.update_friendship(session, uid, fid, accepted)
    session.close()

    return make_response(jsonify({'message': error.error_string('FRIENDSHIP_UPDATED')}), status.HTTP_201_CREATED)

@app.route("/friendrequest", methods=['POST'])
@jwt_required()
def tell_a_friend():
    """
    Issue Friendship Request
    ---
    tags:
      - user
    operationId: tell-a-friend
    consumes:
        - application/json
    parameters:
      - in: body
        name: body
        schema:
          id: req_a_friend
          required:
            - friend
          properties:
            friend:
              type: string
    responses:
      201:
        description: "Will notify friend"
      400:
        description: missing required arguments
      500:
        description: error requesting friendship
      default:
        description: "unexpected error"
    """
    if not request.json:
        return make_response(jsonify({'msg': error.error_string('NO_JSON')}), status.HTTP_400_BAD_REQUEST)

    try:
        u = current_identity
        uid = u.id
        friend = request.json['friend']  # email address of friend to notify
    except KeyError:
        uid = None
        friend = None

    if uid is None or friend is None:
        return make_response(jsonify({'msg': error.error_string('MISSING_ARGS')}), status.HTTP_400_BAD_REQUEST)

    session = dbsetup.Session()
    request_id = usermgr.FriendRequest.write_request(session, uid, friend)
    session.close()

    if request_id != 0:
        return make_response(jsonify({'message': error.error_string('WILL_NOTIFY_FRIEND'), 'request_id':request_id}), status.HTTP_201_CREATED)

    return make_response(jsonify({'msg': error.error_string('FRIEND_REQ_ERROR')}), status.HTTP_500_INTERNAL_SERVER_ERROR)

@app.route("/vote", methods=['POST'])
@jwt_required()
def cast_vote():
    """
     Cast Vote
     ---
     tags:
       - voting
     operationId: cast-vote
     consumes:
       - application/json
     produces:
       - application/json
     parameters:
       - in: body
         name: body
         schema:
           id: vote_args
           required:
             - votes
           properties:
             votes:
               type: array
               items:
                 $ref: '#/definitions/ballotentry'
     responses:
       '200':
         description: "votes recorded"
       '400':
         description: missing required arguments
       '500':
         description: error operating on category id specified
     definitions:
      - schema:
          id: ballotentry
          properties:
            bid:
              type: integer
              description: ballot identifier
            vote:
              type: integer
              description: ranking in ballot
            like:
              type: string
              description: if present, indicates user "liked" the image
     """
    if not request.json:
        return make_response(jsonify({'msg': error.error_string('NO_JSON')}), status.HTTP_400_BAD_REQUEST)

    try:
        u = current_identity
        uid = u.id
        votes = request.json['votes']  # list of dict() with the actual votes
    except KeyError:
        uid = None
        votes = None

    if uid is None or votes is None:
        return make_response(jsonify({'msg': error.error_string('MISSING_ARGS')}), status.HTTP_400_BAD_REQUEST)

#    assert(len(votes) == 4)

    if len(votes) > 4:
        return make_response(jsonify({'msg': error.error_string('TOO_MANY_BALLOTS')}), status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)


    session = dbsetup.Session()

    cid = voting.Ballot.tabulate_votes(session, uid, votes)
    return return_ballot(session, uid, cid)

def return_ballot(session, uid, cid):
    d = voting.Ballot.create_ballot(session, uid, cid)
    b = d['arg']
    if b is None:
        session.close()
        return make_response(jsonify({'msg': error.error_string('NO_BALLOT')}),status.HTTP_500_INTERNAL_SERVER_ERROR)

    # we have a ballot, turn it into JSON
    ballots = b.to_json()
    session.close()
    return make_response(jsonify(ballots), status.HTTP_200_OK)

@app.route("/image", methods=['GET'])
@jwt_required()
def image_download():
    """
    Image Download
    ---
    tags:
      - image
    operationId: image-download
    consumes:
      - text/html
    produces:
      - application/json
    parameters:
      - in: query
        name: filename
        description: "The filename you wish to retrieve"
        required: true
        type: string
    responses:
      200:
        description: "image found"
        schema:
          id: download_image
          properties:
            image:
              type: string
              description: base64 encoded image file
      400:
        description: missing required arguments
      500:
        description: photo not found
      default:
        description: "unexpected error"
    """
    if not request.args:
        return make_response(jsonify({'msg': error.error_string('NO_ARGS')}),status.HTTP_400_BAD_REQUEST)

    u = current_identity
    uid = u.id
    filename = request.args.get('filename')

    if uid is None or filename is None or filename == 'None':
        return make_response(jsonify({'msg': error.error_string('MISSING_ARGS')}), status.HTTP_400_BAD_REQUEST)

    session = dbsetup.Session()
    b64_photo = photo.Photo.read_photo_by_filename(session, uid, filename)
    session.close()
    if b64_photo is not None:
        return make_response(jsonify({'image':b64_photo.decode('utf-8')}), status.HTTP_200_OK)

    return make_response(jsonify({'msg':error.error_string('NO_PHOTO')}), status.HTTP_500_INTERNAL_SERVER_ERROR)

@app.route("/lastsubmission", methods=['GET'])
@jwt_required()
def last_submission():
    """
    Get Last Submission
    ###
    tags:
      - user
    operationId: last-submission
    consumes:
        - application/json
    responses:
      200:
        description: "last submission found"
        schema:
          id: image
          type: string
          id: category
          title: Category
          items:
            $ref: '#/definitions/Category'
      400:
        description: missing required arguments
      500:
        description: photo not found
      default:
        description: "unexpected error"
    """
    u = current_identity
    uid = u.id

    session = dbsetup.Session()
    d = photo.Photo.last_submitted_photo(session, uid)
    session.close()
    if d['arg'] is None:
        return make_response(jsonify({'msg': error.error_string('NO_SUBMISSION')}), status.HTTP_200_OK)

    darg = d['arg']
    c = darg['category']
    i = darg['image']

    return make_response(jsonify({'image':i.decode("utf-8"), 'category':c.to_json()}), status.HTTP_200_OK)

@app.route("/photo", methods=['POST'])
@jwt_required()
def photo_upload():
    """
    Upload Photo
    ---
    tags:
      - image
    operationId: photo
    consumes:
      - application/json
    produces:
      - application/json
    parameters:
      - in: body
        name: photo-info
        required: true
        schema:
          id: upload_photo
          required:
            - category_id
            - extension
            - image
          properties:
            category_id:
              type: integer
              description: the category id of the current category accepting uploads
            extension:
              type: string
              description: Extension/filetype of uploaded image
            image:
              type: string
              description: Base64 encoded image
    responses:
      201:
        description: "The image was properly uploaded!"
        schema:
          id: filename
          properties:
            filename:
              type: string
      400:
        description: missing required arguments
      500:
        description: error uploading image
      default:
        description: "unexpected error"
    """
    if not request.json:
        return make_response(jsonify({'msg': error.error_string('NO_JSON')}), status.HTTP_400_BAD_REQUEST)

    try:
        image_data_b64 = request.json['image']
        image_type     = request.json['extension']
        cid    = request.json['category_id']
        u = current_identity
        uid = u.id
    except KeyError:
        cid = None
        uid = None

    if cid is None or uid is None:
        return make_response(jsonify({'msg': error.error_string('MISSING_ARGS')}), status.HTTP_400_BAD_REQUEST)

    image_data = base64.b64decode(image_data_b64)
    session = dbsetup.Session()
    d = photo.Photo().save_user_image(session, image_data, image_type, uid, cid)
    session.close()
    if d['error'] is not None:
        return make_response(jsonify({'msg': error.iiServerErrors.error_message(d['error'])}), error.iiServerErrors.http_status(d['error']))

    return make_response(jsonify({'msg': error.error_string('PHOTO_UPLOADED'), 'filename': d['arg']}), status.HTTP_201_CREATED)

@app.route("/login", methods=['POST'])
def login():
    """
    Login User
    ---
    tags:
      - user
    operationId: login
    consumes:
      - application/json
    produces:
      - application/json
    parameters:
      - in: body
        name: login-info
        required: true
        schema:
          id: login_user
          required:
            - username
            - password
          properties:
            username:
              type: string
              description: username being logged in, can be a GUID
            password:
              type: string
              description: password to log in user, special rules for anonymous users
    responses:
      200:
        description: "User logged in"
        schema:
          id: logged_in
          properties:
            user_id:
              type: integer
              description: the user's internal identifier
            category_id:
              type: integer
              description: Current category that is accepting Uploads for this users
      400:
        description: missing required arguments
      500:
        description: error uploading image
      default:
        description: "unexpected error"
    """
    if not request.json:
        return make_response(jsonify({'msg': error.error_string('NO_JSON')}), status.HTTP_400_BAD_REQUEST)

    try:
        emailaddress = request.json['username']
        password     = request.json['password']
    except KeyError:
        emailaddress = None
        password = None

    if emailaddress is None or password is None:
        return make_response(jsonify({'msg': error.error_string('MISSING_ARGS')}), status.HTTP_400_BAD_REQUEST)

    foundUser = usermgr.authenticate(emailaddress, password)
    if foundUser is None:
        return make_response(jsonify({'msg': error.error_string('NO_SUCH_USER')}), status.HTTP_403_FORBIDDEN)

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
    """
    Register (Create new account)
    ---
    tags:
      - user
    operationId: register
    consumes:
      - application/json
    produces:
      - application/json
    parameters:
      - in: body
        name: registration-info
        required: true
        schema:
          id: register_user
          required:
            - username
            - password
            - guid
          properties:
            username:
              type: string
              description: this is either a guid (anonymous registration) or an email address
            password:
              type: string
              description: password to log in user, special rules for anonymous users
            guid:
              type: string
              description: a UUID that uniquely identifies the user, in lieu of a username, this is their anonymous account handle
    responses:
      201:
        description: "account created"
      400:
        description: missing required arguments
      500:
        description: error creating account
      default:
        description: "unexpected error"
    """
    # an email address and password has been posted
    # let's create a user for this
    if not request.json:
        return make_response(jsonify({'msg': error.error_string('NO_JSON')}), status.HTTP_400_BAD_REQUEST)

    try:
        emailaddress = request.json['username']
        password     = request.json['password']
        guid         = request.json['guid']
    except KeyError:
        emailaddress = None
        password = None

    if emailaddress is None or password is None:
        return make_response(jsonify({'msg': error.error_string('MISSING_ARGS')}), status.HTTP_400_BAD_REQUEST)

    # is the username really a guid?
    session = dbsetup.Session()
    if usermgr.AnonUser.is_guid(emailaddress, password):
        foundAnonUser = usermgr.AnonUser.find_anon_user(session, emailaddress)
        if foundAnonUser is not None:
            session.close()
            return make_response(jsonify({'msg': error.error_string('ANON_ALREADY_EXISTS')}), status.HTTP_400_BAD_REQUEST)

        newAnonUser = usermgr.AnonUser.create_anon_user(session, emailaddress)
        if newAnonUser is None:
            session.close()
            return make_response(jsonify({'msg': error.error_string('ANON_USER_ERROR')}), status.HTTP_500_INTERNAL_SERVER_ERROR)
    else:
        foundUser = usermgr.User.find_user_by_email(session, emailaddress)
        if foundUser is not None:
            session.close()
            return make_response(jsonify({'msg':error.error_string('USER_ALREADY_EXISTS')}), status.HTTP_400_BAD_REQUEST)

        # okay the request is valid and the user was not found, so we can
        # create their account
        newUser = usermgr.User.create_user(session, guid, emailaddress, password)
        if newUser is None:
            session.close()
            return make_response(jsonify({'msg': error.error_string('USER_CREATE_ERROR')}),status.HTTP_500_INTERNAL_SERVER_ERROR)

    # user was properly created
    session.close()
    return make_response(jsonify({'message': error.error_string('ACCOUNT_CREATED')}), 201)


if __name__ == '__main__':
    dbsetup.metadata.create_all(bind=dbsetup.engine, checkfirst=True)
    if not dbsetup.is_gunicorn():
        app.run(host='0.0.0.0', port=8080)
