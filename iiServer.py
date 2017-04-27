import datetime
import base64

from flask import Flask, jsonify
from flask     import request, make_response, current_app
from flask_jwt import JWT, jwt_required, current_identity
import jwt
from flask_api import status
from flask import send_from_directory

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
import os
from sqlalchemy import text


app = Flask(__name__)
app.debug = True
app.config['SECRET_KEY'] = 'imageimprove3077b47'

is_gunicorn = False

__version__ = '0.2.1' #our version string PEP 440


def fix_jwt_decode_handler(token):
    secret = current_app.config['JWT_SECRET_KEY']
    algorithm = current_app.config['JWT_ALGORITHM']
    leeway = current_app.config['JWT_LEEWAY']

    verify_claims = current_app.config['JWT_VERIFY_CLAIMS']
    required_claims = current_app.config['JWT_REQUIRED_CLAIMS']

    options = {
        'verify_' + claim: claim in verify_claims
        for claim in ['signature', 'exp', 'nbf', 'iat']
    }

    options.update({
        'require_' + claim: claim in required_claims
        for claim in ['exp', 'nbf', 'iat']
    })

    return jwt.decode(token, secret, options=options, algorithms=[algorithm], leeway=leeway)

# specify the JWT package's call backs for authentication of username/password
# and subsequent identity from the payload in the token
app.config['JWT_EXPIRATION_DELTA'] = datetime.timedelta(days=10)
app.config['JWT_LEEWAY'] = 20
app.config['JWT_VERIFY_CLAIMS'] = ['signature', 'exp'] # keep getting iat "in the future" failure

_jwt = JWT(app, usermgr.authenticate, usermgr.identity)
_jwt.jwt_decode_handler(fix_jwt_decode_handler)

@app.route("/protected")
@jwt_required()
def protected():
    return '%s' % current_identity

@app.route("/api/<path:path>")
#@app.route("/api", defaults={'path': 'dist/index.html'})
def api_spec(path):
    """
    Swagger UI
    ---
    parameters:
      - in: path
        name: path
        required: true
        type: string
    tags:
      - admin
    summary: "Swagger UI - displays our local API specification"
    operationId: swagger-specification
    consumes:
      - text/html
    security:
      - api_key: []
    produces:
      - text/html
    responses:
      200:
        description: "look at our beautiful specification"
      500:
        description: "serious error dude"
    """
    root_path = app.root_path
    swagger_path = root_path + '/swagger-ui'
    return send_from_directory(swagger_path, path)

@app.route("/spec/swagger.json")
def spec():
    """
    Specification
    ---
    tags:
      - admin
    summary: "A JSON formatted OpenAPI/Swagger document formatting the API"
    operationId: get-specification
    consumes:
      - text/html
    security:
      - api_key: []
    produces:
      - text/html
    responses:
      200:
        description: "look at our beautiful specification"
      500:
        description: "serious error dude"
    """
    swag = swagger(app)
    swag['info']['title'] = "ImageImprov API"
    swag['info']['version'] = __version__
    swag['info']['description'] = "The first version of the ImageImprov API is purely designed to interact "\
                                 "with the ImageImprov mobile clients. We are aiming for a secure interface that " \
                                 "will implement our needed features in a simple programming model\n"\
                                 "\n"\
                                 "All endpoints are only accessible via https and are located at"\
                                 "\n\n```api.imageimprov.com```\n\nUsers do not need to provide any information "\
                                 "in order to enjoy our service, we fully support anonymous registration & play"\
                                 "\n\n"\
                                 "## Limits\n"\
                                 "We are currently only allowing a single photo upload per category per period the "\
                                 "category is open for uploading\n"

    swag['info']['contact'] = {'name':'apimaster@imageimprov.com'}
    swag['schemes'] = ['http', 'https']
    swag['host'] = "api.endpoints.imageimprov.cloud.goog"

    swag['paths']["/auth"] = {'post':{'consumes': ['application/json'],
                                      'description':'JWT authentication',
                                      'operationId': 'jwt-auth',
                                      'produces' : ['application/json'],
                                      'parameters': [{'in': 'body',
                                                      'name': 'credentials',
                                                     'schema':
                                                        {'required': ['username', 'password'],
                                                         'properties':{'username':{'type':'string'},
                                                                        'password':{'type':'string'}},
                                                         }}],
                                      'responses': {'200':{'description': 'user authenticated',
                                                           'schema':
                                                               {'properties':
                                                                    {'access_token':
                                                                         {'type':'string'} } } },
                                                    '401':{'description': 'user authentication failed'}},
                                      'security': [{'api_key':[]}],
                                      'summary' : "JWT authentication",
                                      'tags':['user']}
                              }

#    Definitions
    # [START securityDef]
#    securityDefinitions:
      # This section configures basic authentication with an API key.
#      api_key:
#        type: "apiKey"
#        name: "key"
#        in: "query"
    # [END securityDef]
    swag['securityDefinitions'] = {'api_key': {'type': 'apiKey', 'name': 'key', 'in': 'query'}}
    swag['securityDefinitions'] = {'JWT': {'type': 'apiKey', 'name': 'access_token', 'in': 'header'}}
    swag['swagger'] = "2.0"

    resp = make_response(jsonify(swag), status.HTTP_200_OK)
    resp.headers['Content-Type'] = "application/json"
    resp.headers['Access-Control-Allow-Origin'] = "*"
    resp.headers['Access-Control-Allow-Headers'] = "Content-Type"
    resp.headers['Access-Control-Allow-Methods'] = 'GET, POST'
    resp.headers['Server'] = 'Flask'
    return resp

@app.route("/healthcheck")
def healthcheck():
    """
    Health Check()
    perform some simple tests to see if the server is viable.
    Reporting 200 means that the loadbalancer can continue to use
    the server, anything else takes it out of rotation
    :return: 
    """
    http_status = status.HTTP_200_OK

    # check that database & redis are up
    try:
        session = dbsetup.Session()
        lb_name = 'configtest'
        rd = voting.ServerList().get_redis_server(session)
        lb = Leaderboard(lb_name, host=rd['ip'], port=rd['port'], page_size=10)
        lb.check_member('no one')
        lb.delete_leaderboard()
    except:
        http_status = status.HTTP_500_INTERNAL_SERVER_ERROR

    resp = make_response("healthcheck status", http_status)
    resp.headers['Content-Type'] = "text/html"
    resp.headers['Access-Control-Allow-Origin'] = "*"
    resp.headers['Access-Control-Allow-Headers'] = "Content-Type"
    resp.headers['Access-Control-Allow-Methods'] = 'GET'
    resp.headers['Server'] = 'iiServer'
    return resp

@app.route("/config")
def hello():
    """
    Configuration
    ---
    tags:
      - admin
    summary: "Simple page that checks some connections to make sure we are setup properly"
    operationId: get-configuration
    consumes:
      - text/html
    security:
      - api_key: []
    produces:
      - text/html
    responses:
      200:
        description: "everything is running well"
      500:
        description: "serious error dude"
    """
    htmlbody = "<html>\n<body>\n"
    if dbsetup.is_gunicorn():
        htmlbody += "<h1>ImageImprov Hello World from Gunicorn!</h1>"
#        htmlbody += "<img src=\"/static/gunicorn_banner.jpg\"/>"
        htmlbody += "<img src=\"/static/gunicorn_small.png\"/>"
    else:
        htmlbody += "<h1>ImageImprov Hello World from Flask!</h1>"

    htmlbody += "<h2>Version {}</h2><br>".format(__version__)
#    htmlbody += "<img src=\"/static/python_flask_mysql_banner.jpg\"/>\n"
    htmlbody += "<img src=\"/static/python_small.png\"/>\n"

    img_folder = dbsetup.image_store(dbsetup.determine_environment(None))
    htmlbody += "\n<br><b>image folder</b> =\"" + img_folder + "\""
    htmlbody += "\n<br>Flask instance path = \"" + app.instance_path + "\"\n"
    htmlbody += "\n<br>Flask root path = \"" + app.root_path + "\"\n"

    htmlbody += "<br>\n"

    # display current connection string, without username/password!
    cs = dbsetup.connection_string(None)
    cs2 = cs.split("@",1)
    htmlbody += "<h3>connection string:<span>" + cs2[1] + "</span></h3><br>\n"

    session = dbsetup.Session()

    sql = text('select * from mysql.event;')
    try:
        result = dbsetup.engine.execute(sql)
        htmlbody += "<h3>Scheduled Events</h3>"
        if result is not None:
            for row in result:
                le = row['last_executed']
                if le is None:
                    last_executed = "never"
                else:
                    last_executed = le
                h = "&nbsp&nbsp><b>name: </b>{}, every {} {}, last executed: {}, status: {}".format(row['name'], row['interval_value'], row['interval_field'], last_executed, row['status'])
                htmlbody += h + "<br>"
        else:
            htmlbody += "<i>no events found</i><br>"
    except:
        htmlbody += "<h3>error reading event table</h3></br>\n"
        pass


    rd = voting.ServerList().get_redis_server(session)
    if rd is not None:
        ip = rd['ip']
        port = str(rd['port'])
        htmlbody += "<h3>Redis server:<span>" + ip + ':' + port + "</span></h3><br>\n"
    else:
        htmlbody += "<h3>Error reading Redis server configuration!</h3><br>\n"

    cl = category.Category.active_categories(session, 1)
    if cl is None:
        htmlbody += "\n<br>No category information retrieved (ERROR)<br>"
    else:
        htmlbody += "\n<br><h3>Categories:</h3>"
        htmlbody += "\n<blockquote>"
        for c in cl:
            htmlbody += "\n<br>state = <b>{}</b>".format(category.CategoryState.to_str(c.state))
            htmlbody += "\n<br>category_id = {}".format(c.get_id())
            htmlbody += "\n<br>description = <b><i>\"{}\"</b></i>".format(c.get_description())
            htmlbody += "\n<br>start date={} UTC".format(c.start_date)
            htmlbody += "\n<br>end date={} UTC".format(c.end_date)
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
      - admin
    summary: "Sets the category state to a specific value - testing only!"
    operationId: set-category-state
    consumes:
      - application/json
    security:
      - api_key: []
      - JWT: []
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
              enum:
                - 1
                - 2
                - 3
                - 4
    responses:
      200:
        description: "state changed"
      400:
        description: "missing required arguments"
      500:
        description: "error operating on category id specified"
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
    security:
      - api_key: []
    produces:
      - application/json
    responses:
      200:
        description: "category list retrieved"
        schema:
          id: categories
          type: array
          items:
            $ref: '#/definitions/Category'
      400:
        description: "missing required arguments"
      500:
        description: "error retrieving categories"
    definitions:
      - schema:
          id: Category
          properties:
            id:
              type: integer
              description: category identifier
            theme:
              type: string
              description: "A brief description of the category"
            start:
              type: string
              description: "When the category starts and uploading can begin"
            end:
              type: string
              description: "When the category ends and voting can begin"
            state:
              type: string
              enum:
                - "UPLOAD"
                - "VOTING"
                - "COUNTING"
                - "CLOSED"
              description: "The current state of the category (VOTING, UPLOADING, CLOSED, etc.)"
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
    summary: "Returns a list of the top 10 photos as well as the caller's (so 11 in total)"
    operationId: get-leaderboard
    parameters:
      - in: query
        name: category_id
        description: "Category of the leaderboard being requested"
        required: true
        type: integer
    security:
      - api_key: []
    responses:
      200:
        description: "leaderboard retrieved"
        schema:
          id: scores
          type: array
          items:
            $ref: '#/definitions/ranking'
      400:
        description: "missing required arguments"
      500:
        description: "error getting categories"
    definitions:
      - schema:
          id: ranking
          properties:
            username:
              type: string
              description: username of member of this rank
            rank:
              type: integer
              description: "overall rank in scoring"
            score:
              type: integer
              description: "actual score for this rank"
            you:
              type: string
              description: "if set, then this rank is yours"
            isfriend:
              type: string
              description: "if set, then this rank is for a friend of yours"
            image:
              type: string
              description: "base64 encoded thumbnail image of entry"
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
    summary: "A list of photos to be voted on, currently no more than 4"
    operationId: get-ballot
    parameters:
      - in: query
        name: category_id
        description: "The category we want to vote on"
        required: true
        type: integer
    security:
      - api_key: []
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
      403:
        description: "no such user"
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
            orientation:
              type: integer
              enum:
                - 1
                - 8
                - 3
                - 6
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
    return return_ballot(session, uid, cid)

@app.route("/acceptfriendrequest", methods=['POST'])
@jwt_required()
def accept_friendship():
    """
        Accept Friend Request
        ---
        tags:
          - user
        summary: "Called to indicate a user has accepted a friend request"
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
                  description: "identifier from friend request this is a response to"
        security:
          - api_key: []
        responses:
          201:
            description: "friendship updated"
          400:
            description: "missing required arguments"
          500:
            description: "error operating on category id specified"
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
    summary: "Issue a friendship request, server will notify person to become a friend and join site if necessary"
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
              description: "email address of friend to send request to"
    security:
      - api_key: []
    responses:
      201:
        description: "Will notify friend"
      400:
        description: "missing required arguments"
      500:
        description: "error requesting friendship"
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
     summary: "Cast votes for a ballot. We choose the top photo, and then any likes"
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
     security:
       - api_key: []
     responses:
       200:
         description: "ballot"
         schema:
           items:
             $ref: '#/definitions/Ballot'
       400:
         description: "missing required arguments"
       413:
         description: "too many votes being tallied"
       500:
         description: "error creating ballot to return"
     definitions:
      - schema:
          id: ballotentry
          properties:
            bid:
              type: integer
              description: "ballot identifier"
            vote:
              type: integer
              description: "ranking in ballot"
            like:
              type: string
              description: "if present, indicates user liked the image"
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

    if len(votes) > 4:
        return make_response(jsonify({'msg': error.error_string('TOO_MANY_BALLOTS')}), status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)

    session = dbsetup.Session()

    try:
        cid = voting.Ballot.tabulate_votes(session, uid, votes)
    except:
        return make_response(jsonify({'msg': error.error_string('TABULATE_ERROR')}), status.HTTP_500_INTERNAL_SERVER_ERROR)

    rsp = return_ballot(session, uid, cid)
    return rsp

def return_ballot(session, uid, cid):
    d = voting.Ballot.create_ballot(session, uid, cid)
    session.close()
    b = d['arg']
    if b is None:
        if d['error'] is not None:
            return make_response(jsonify({'msg':error.iiServerErrors.error_message(d['error'])}),status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            return make_response(jsonify({'msg': error.error_string('NO_BALLOT')}),status.HTTP_500_INTERNAL_SERVER_ERROR)

    # we have a ballot, turn it into JSON
    ballots = b.to_json()
    return make_response(jsonify(ballots), status.HTTP_200_OK)

@app.route("/image", methods=['GET'])
@jwt_required()
def image_download():
    """
    Image Download
    ---
    tags:
      - image
    summary: "Download an image. If we have a filename, we can download the full image"
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
    security:
      - api_key: []
    responses:
      200:
        description: "image found"
        schema:
          id: download_image
          properties:
            image:
              type: string
              description: "base64 encoded image file"
      400:
        description: "missing required arguments"
      500:
        description: "photo not found"
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
    ---
    tags:
      - user
    summary: "returns the last submission for this user"
    operationId: last-submission
    consumes:
        - application/json
    security:
      - api_key: []
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
        description: "missing required arguments"
      500:
        description: "photo not found"
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
    summary: "Upload a photo for the specified category"
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
              description: "the category id of the current category accepting uploads"
            extension:
              type: string
              enum:
                - "JPEG"
                - "JPG"
              description: "Extension/filetype of uploaded image"
            image:
              type: string
              description: "Base64 encoded image"
    security:
      - api_key: []
    responses:
      201:
        description: "The image was properly uploaded!"
        schema:
          id: filename
          properties:
            filename:
              type: string
      400:
        description: "missing required arguments"
      500:
        description: "error uploading image"
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

@app.route("/register", methods=['POST'])
def register():
    """
    Register (Create new account)
    ---
    tags:
      - user
    summary: "register a user"
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
              description: "this is either a guid (anonymous registration) or an email address"
            password:
              type: string
              description: "password to log in user, special rules for anonymous users"
            guid:
              type: string
              description: "a UUID that uniquely identifies the user, in lieu of a username, this is their anonymous account handle"
    security:
      - api_key: []
    responses:
      201:
        description: "account created"
      400:
        description: "missing required arguments"
      500:
        description: "error creating account"
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
