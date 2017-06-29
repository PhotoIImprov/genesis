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
from sqlalchemy.orm import Session
from random import shuffle
from datetime import timedelta

from logsetup import logger, client_logger

app = Flask(__name__)
app.debug = True
app.config['SECRET_KEY'] = 'imageimprove3077b47'

is_gunicorn = False

__version__ = '0.9.9.1' #our version string PEP 440


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
    swag['host'] = "api.imageimprov.com"

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
#                                      'security': [{'api_key':[]}],
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
#    swag['definitions'] = {'Error': {'properties': {'msg':{'type':'string'}}}}
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
    session = dbsetup.Session()
    try:
        lb_name = 'configtest'
        rd = voting.ServerList().get_redis_server(session)
        lb = Leaderboard(lb_name, host=rd['ip'], port=rd['port'], page_size=10)
        lb.check_member('no one')
        lb.delete_leaderboard()
    except Exception as e:
        logger.exception(msg=str(e))
        http_status = status.HTTP_500_INTERNAL_SERVER_ERROR
    finally:
        session.close()

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
    produces:
      - text/html
    responses:
      200:
        description: "everything is running well"
      500:
        description: "serious error dude"
        schema:
          $ref: '#/definitions/Error'
    """
    logger.info(msg='/config page launched')
    htmlbody = "<html>\n<body>\n"
    dtNow = datetime.datetime.now()
    if dbsetup.is_gunicorn():
        htmlbody += "<h1>ImageImprov Hello World from Gunicorn & Nginx!</h1> last called {}".format(dtNow)
        htmlbody += "<img src=\"/static/gunicorn_small.png\"/>"
    else:
        htmlbody += "<h1>ImageImprov Hello World from Flask!</h1> last called {}".format(dtNow)

    htmlbody += "<h2>Version {}</h2><br>".format(__version__)
    htmlbody += "<ul>" \
                "<li>logging to db</li>" \
                "<li>Samsung orientation fix</li>" \
                "<li>prevent duplicate photos in ballot</li>" \
                "<li>square pictures</li>" \
                "<li>watermark images</li>" \
                "<li>normalized thumbnails</li>" \
                "<li>metadata tagging</li>" \
                "<li>Active Photos</li>" \
                "<li>cleaned ballot list</li>" \
                "</ul>"
    htmlbody += "<img src=\"/static/python_small.png\"/>\n"

    img_folder = dbsetup.image_store(dbsetup.determine_environment(None))
    htmlbody += "\n<br><b>image folder</b> =\"" + img_folder + "\""
    htmlbody += "\n<br>Flask instance path = \"" + app.instance_path + "\"\n"
    htmlbody += "\n<br>Flask root path = \"" + app.root_path + "\"\n"

    hostname = os.uname()[1]
    if hostname is None:
        hostname = '<i>unknown</i>!'
    htmlbody += "\n<br><b>hostname: </b>" + hostname
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
    except Exception as e:
        logger.exception(msg='error reading mysql.event table')
        htmlbody += "<h3>error reading event table</h3></br>\n"

    logger.info(msg='[config] Find Redis server')

    try:
        rd = voting.ServerList().get_redis_server(session)
        if rd is not None:
            ip = rd['ip']
            port = str(rd['port'])
            htmlbody += "<h3>Redis server:<span>" + ip + ':' + port + "</span></h3><br>\n"
    except Exception as e:
        logger.exception(msg='error reading serverlist')
        htmlbody += "<h3>Error reading Redis server configuration!</h3><br>\n"

    logger.info(msg='[config] Test Redis server')
    lb = None
    # let's see if we can access the leaderboard class, hence redis server is up
    try:
        lb_name = 'configtest'
        rd = voting.ServerList().get_redis_server(session)
        logger.info(msg='[config] lb_name:{0}, host={1}, port={2}'.format(lb_name, rd['ip'], rd['port']))
        lb = Leaderboard(lb_name, host=rd['ip'], port=rd['port'], page_size=10)
        lb.check_member('no one')
        htmlbody += "<img src=\"/static/redis.png\"/>"
        htmlbody += "<br>leader board \'{}\' created<br>".format(lb_name)
        lb.delete_leaderboard()
    except:
        logger.exception(msg='error creating leaderboard')
        htmlbody += "\n<h2>Cannot create leaderboard!!</h2> (is redis server running?)<br>"

    logger.info(msg='[config] List active categories')

    tm = voting.TallyMan()
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
            num_photos = photo.Photo.count_by_category(session, c.get_id())
            htmlbody += "\n<br>number photos uploaded = <b>{}</b>".format(num_photos)
            if c.state == category.CategoryState.VOTING.value:
                htmlbody += "\n<br>round={0} (Voting Round #{1})".format(c.round, c.round+1)
                num_voters = voting.Ballot.num_voters_by_category(session, c.get_id())
                htmlbody += "\n<br>number users voting = <b>{}</b>".format(num_voters)
                end_of_voting = c.start_date + timedelta(hours=(c.duration_vote + c.duration_upload))
                start_of_voting = c.start_date + timedelta(hours=c.duration_upload)
                htmlbody += "\n, voting ends @{}".format(end_of_voting)
                # display how close we are (% wise) to end of voting
                # % = (now - start) / (end - start)
                denominator = (end_of_voting - start_of_voting) / timedelta(seconds=1)
                numerator = (datetime.datetime.now() - start_of_voting) / timedelta(seconds=1)
                percent_done = numerator / denominator
                htmlbody += "\n, <b>{:6.2f}%</b> of voting done".format(percent_done * 100.0)
                if c.round == 1:
                    photo_cnt = session.query(photo.Photo).filter(photo.Photo.category_id == c.id).\
                                join(voting.VotingRound, voting.VotingRound.photo_id == photo.Photo.id).count()
                    htmlbody += "\n<br>{} photos in voting_round table<br>".format(photo_cnt)

            if c.state == category.CategoryState.UPLOAD.value:
                q = session.query(photo.Photo.user_id).distinct().filter(photo.Photo.category_id == c.get_id())
                n = q.count()
                htmlbody += "\n<br>number users uploading = <b>{}</b>".format(n)
                end_of_uploading = c.start_date + timedelta(hours=c.duration_upload)
                htmlbody += "\n, uploading ends @{}".format(end_of_uploading)
            else:
                # let's get # of votes and average vote/photo
                q = session.query(voting.BallotEntry).filter(voting.BallotEntry.category_id == c.get_id())
                total_votes = q.count()
                htmlbody += "\n<br>Total votes for category = <b>{}</b>".format(total_votes)
                htmlbody += "\n<br>Average votes per photo = "
                if num_photos != 0:
                    average_votes = total_votes / num_photos
                    htmlbody += "<b>{:6.2f}</b>".format(average_votes)
                else:
                    htmlbody += "<b><i>undefined</b></i>"

                try:
                    lbname = tm.leaderboard_name(c)
                    lb_count = lb.total_members_in(lbname)
                    htmlbody += "<br>{} entries in the leaderboard".format(lb_count)
                except Exception as e:
                    htmlbody += "<br><i>failure getting leaderboard count for category</i>"

            htmlbody += "\n<br><br>"
        htmlbody += "\n</blockquote>"

    logger.info(msg='[config] Test anon user registration')

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
        schema:
          $ref: '#/definitions/Error'
      500:
        description: "error operating on category id specified"
        schema:
          $ref: '#/definitions/Error'
    """
    if not request.json:
        return make_response(jsonify({'msg': error.error_string('NO_JSON')}), status.HTTP_400_BAD_REQUEST)

    try:
        cid = request.json['category_id']
        cstate = request.json['state']
    except KeyError as e:
        cid = None
        cstate = None

    session = dbsetup.Session()
    rsp = None
    try:
        if cid is None:
            rsp = make_response(jsonify({'msg': error.error_string('MISSING_ARGS')}), status.HTTP_400_BAD_REQUEST)
        else:
            tm = voting.TallyMan()
            d = tm.change_category_state(session, cid, cstate)
            session.commit()
            if d['error'] is not None:
                rsp = make_response(jsonify({'msg': error.iiServerErrors.error_message(d['error'])}), error.iiServerErrors.http_status(d['error']))
            else:
                c = d['arg']
                if c is not None:
                   rsp = make_response(jsonify({'msg': error.error_string('CATEGORY_STATE')}),status.HTTP_200_OK)
    except Exception as e:
        logger.exception(msg=str(e))
        rsp = make_response(jsonify({'msg': error.iiServerErrors.error_message(d['error'])}), status.HTTP_500_INTERNAL_SERVER_ERROR)
    finally:
        session.close()
        if rsp is None:
            rsp = make_response(jsonify({'msg': error.error_string('UNKNOWN_ERROR')}), status.HTTP_500_INTERNAL_SERVER_ERROR)
        return rsp

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
      - JWT: []
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
        schema:
          $ref: '#/definitions/Error'
      500:
        description: "error retrieving categories"
        schema:
          $ref: '#/definitions/Error'
    definitions:
      - schema:
          id: Category
          properties:
            id:
              type: integer
              description: category identifier
            description:
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
                - UPLOAD, VOTING, COUNTING, CLOSED
              description: "The current state of the category (VOTING, UPLOADING, CLOSED, etc.)"
            round:
              type: integer
              description: "Which round of voting the category is in."
    """
    rsp = None
    try:
        uid = current_identity.id
        session = dbsetup.Session()
        cl = category.Category.active_categories(session, uid)
        session.close()
        if cl is None:
           rsp = make_response(jsonify({'msg': error.error_string('CATEGORY_ERROR')}), status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
           categories = category.Category.list_to_json(cl)
           rsp = make_response(jsonify(categories), status.HTTP_200_OK)
    except Exception as e:
        logger.exception(msg=str(e))
        rsp = make_response(jsonify({'msg': error.error_string('CATEGORY_ERROR')}), status.HTTP_500_INTERNAL_SERVER_ERROR)
    finally:
        session.close()
        return rsp

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
      - JWT: []
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
        schema:
          $ref: '#/definitions/Error'
      500:
        description: "error getting categories"
        schema:
          $ref: '#/definitions/Error'
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
            orientation:
              type: integer
              enum:
                - 1
                - 8
                - 3
                - 6
              description: "EXIF orientation of the image"
            image:
              type: string
              description: "base64 encoded thumbnail image of entry"
    """
    if not request.args:
        return make_response(jsonify({'msg': error.error_string('NO_ARGS')}),status.HTTP_400_BAD_REQUEST)

    rsp = None
    try:
        session = dbsetup.Session()
        cid = request.args.get('category_id')
        u = current_identity
        uid = u.id
        if cid is None or cid == 'None' or uid is None:
            rsp = make_response(jsonify({'msg': error.error_string('MISSING_ARGS')}),status.HTTP_400_BAD_REQUEST)
        else:
            tm = voting.TallyMan()
            c = category.Category.read_category_by_id(session, cid)
            lb_list = tm.fetch_leaderboard(session, uid, c)
            if lb_list is not None:
                rsp = make_response(jsonify(lb_list), 200)
            else:
                rsp = make_response(jsonify({'msg': error.error_string('NO_LEADERBOARD')}), status.HTTP_500_INTERNAL_SERVER_ERROR)
    except Exception as e:
        logger.exception(msg=str(e))
        rsp = make_response(jsonify({'msg': error.error_string('NO_LEADERBOARD')}), status.HTTP_500_INTERNAL_SERVER_ERROR)
    finally:
        session.close()
        return rsp

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
        description: "The category we want to vote on. If not specified, a random category will be returned."
        required: false
        type: integer
    security:
      - JWT: []
    responses:
      200:
         description: 'list of images to vote on with their originating category'
         properties:
           ballots:
             type: array
             items:
               $ref: '#/definitions/Ballot'
           category:
             $ref: '#/definitions/Category'
      400:
        description: 'missing required arguments'
        schema:
          $ref: '#/definitions/Error'
      403:
        description: 'no such user'
        schema:
          $ref: '#/definitions/Error'
      500:
        description: 'no ballot'
        schema:
          $ref: '#/definitions/Error'
      default:
        description: 'unexpected error'
        schema:
          $ref: '#/definitions/Error'
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
            iitags:
              type: array
              description: "list of pre-defined tags user can select from"
              items:
                type: string
            image:
              type: string
    """
    u = current_identity
    uid = u.id
    if not request.args:
        cid = None
    else:
        cid = request.args.get('category_id')

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
          - JWT: []
        responses:
          201:
            description: "friendship updated"
          400:
            description: "missing required arguments"
            schema:
              $ref: '#/definitions/Error'
          500:
            description: "error operating on category id specified"
            schema:
              $ref: '#/definitions/Error'
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
    try:
        usermgr.FriendRequest.update_friendship(session, uid, fid, accepted)
        rsp = make_response(jsonify({'msg': error.error_string('FRIENDSHIP_UPDATED')}), status.HTTP_201_CREATED)
        session.commit()
    except Exception as e:
        logger.exception(msg=str(e))
        session.rollback()
        rsp = make_response(jsonify({'msg': error.error_string('NO_SUCH_FRIEND')}), status.HTTP_500_INTERNAL_SERVER_ERROR)
    finally:
        session.close()
        return rsp

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
      - JWT: []
    responses:
      201:
        description: "Will notify friend"
      400:
        description: "missing required arguments"
        schema:
          $ref: '#/definitions/Error'
      500:
        description: "error requesting friendship"
        schema:
          $ref: '#/definitions/Error'
      default:
        description: "unexpected error"
        schema:
          $ref: '#/definitions/Error'
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
    try:
        fr = usermgr.FriendRequest(uid, friend)
        fr.find_notifying_friend(session) # see if friend is already known
        session.add(fr)
        session.commit()
        request_id = fr.get_id()
        if request_id != 0 and request_id is not None:
            rsp = make_response(
                jsonify({'msg': error.error_string('WILL_NOTIFY_FRIEND'), 'request_id': request_id}),
                status.HTTP_201_CREATED)
        else:
            rsp = make_response(jsonify({'msg': error.error_string('FRIEND_REQ_ERROR')}), status.HTTP_500_INTERNAL_SERVER_ERROR)
    except Exception as e:
        session.rollback()
        logger.exception(msg=str(e))
        rsp = make_response(jsonify({'msg': error.error_string('FRIEND_REQ_ERROR')}), status.HTTP_500_INTERNAL_SERVER_ERROR)
    finally:
        session.close()
        return rsp

@app.route("/vote", methods=['POST'])
@jwt_required()
def cast_vote():
    """
     Cast Vote
     ---
     tags:
       - voting
     summary: "Cast votes for a ballot. Will return a ballot from a random category."
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
       - JWT: []
     responses:
       200:
         description: ballot of images user has voted on with originating category information
         properties:
           ballots:
             type: array
             items:
               $ref: '#/definitions/Ballot'
           category:
             $ref: '#/definitions/Category'
       400:
         description: "missing required arguments"
         schema:
           $ref: '#/definitions/Error'
       413:
         description: "too many votes being tallied"
         schema:
           $ref: '#/definitions/Error'
       500:
         description: "error creating ballot to return"
         schema:
            $ref: '#/definitions/Error'
     definitions:
      - schema:
          id: Error
          properties:
            msg:
              type: string
              description: "error message"
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
            offensive:
              type: string
              description: "If present, indicates user has found the image offensive"
            iitags:
              type: array
              description: "array of tags user has selected for the image"
              items:
                type: string

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
        voting.BallotManager().tabulate_votes(session, uid, votes)
    except BaseException as e:
        str_e = str(e)
        logger.exception(msg=str_e)
        session.close()
        return make_response(jsonify({'msg': error.error_string('TABULATE_ERROR')}), status.HTTP_500_INTERNAL_SERVER_ERROR)

    return return_ballot(session, uid, None)

def return_ballot(session, uid, cid):
    rsp = None
    try:
        bm = voting.BallotManager()
        if cid is None:
            cl = bm.active_voting_categories(session, uid)
            shuffle(cl)
            c = cl[0]
        else:
            c = category.Category.read_category_by_id(session, cid)

        ballots = bm.create_ballot(session, uid, c)
        if ballots is None:
            rsp =  make_response(jsonify({'msg': error.error_string('NO_BALLOT')}),status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            ballots.read_photos_for_ballots(session)
            j_ballots = ballots.to_json()
            d = {'category': c.to_json(), 'ballots': j_ballots}
            rsp = make_response(jsonify(d), status.HTTP_200_OK)
            session.commit()
            logger.info(msg=ballots.to_log())
    except BaseException as e:
        session.rollback()
        str_e = str(e)
        logger.exception(msg=str_e)
    finally:
        session.close()
        if rsp is None:
            rsp = make_response(jsonify({'msg': error.error_string('NO_BALLOT')}), status.HTTP_500_INTERNAL_SERVER_ERROR)
        return rsp

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
      - JWT: []
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
        schema:
          $ref: '#/definitions/Error'
      500:
        description: "photo not found"
        schema:
          $ref: '#/definitions/Error'
      default:
        description: "unexpected error"
        schema:
          $ref: '#/definitions/Error'
    """
    if not request.args:
        return make_response(jsonify({'msg': error.error_string('NO_ARGS')}),status.HTTP_400_BAD_REQUEST)

    u = current_identity
    uid = u.id
    filename = request.args.get('filename')

    if uid is None or filename is None or filename == 'None':
        return make_response(jsonify({'msg': error.error_string('MISSING_ARGS')}), status.HTTP_400_BAD_REQUEST)

    session = dbsetup.Session()
    try:
        b64_photo = photo.Photo.read_photo_by_filename(session, uid, filename)
        session.commit()
        rsp = make_response(jsonify({'image':b64_photo.decode('utf-8')}), status.HTTP_200_OK)
    except BaseException as e:
        str_e = str(e)
        logger.exception(msg=str_e)
        session.rollback()
        rsp = make_response(jsonify({'msg':error.error_string('ERROR_PHOTO')}), status.HTTP_500_INTERNAL_SERVER_ERROR)
    finally:
        session.close()
        return rsp

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
      - JWT: []
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
        schema:
          $ref: '#/definitions/Error'
      500:
        description: "photo not found"
        schema:
          $ref: '#/definitions/Error'
      default:
        description: "unexpected error"
        schema:
          $ref: '#/definitions/Error'
    """
    u = current_identity
    uid = u.id
    rsp = None
    session = dbsetup.Session()
    try:
        d = photo.Photo.last_submitted_photo(session, uid)
        if d['arg'] is None:
            rsp = make_response(jsonify({'msg': error.error_string('NO_SUBMISSION')}), status.HTTP_200_OK)
        else:
            darg = d['arg']
            c = darg['category']
            i = darg['image']

            rsp = make_response(jsonify({'image':i.decode("utf-8"), 'category':c.to_json()}), status.HTTP_200_OK)
        session.commit()
    except Exception as e:
        session.rollback()
        logger.exception(msg=str(e))
        rsp = make_response(jsonify({'msg': error.error_string('NO_SUBMISSION')}),status.HTTP_500_INTERNAL_SERVER_ERROR)
    finally:
        session.close()
        if rsp is None:
            rsp = make_response(jsonify({'msg': error.error_string('NO_SUBMISSION')}), status.HTTP_500_INTERNAL_SERVER_ERROR)
        return rsp

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
                - JPEG, JPG
              description: "Extension/filetype of uploaded image"
            image:
              type: string
              description: "Base64 encoded image"
    security:
      - JWT: []
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
        schema:
          $ref: '#/definitions/Error'
      500:
        description: "error uploading image"
        schema:
          $ref: '#/definitions/Error'
      default:
        description: "unexpected error"
        schema:
          $ref: '#/definitions/Error'
    """
    if not request.json:
        return make_response(jsonify({'msg': error.error_string('NO_JSON')}), status.HTTP_400_BAD_REQUEST)

    pi = photo.PhotoImage()
    try:
        pi._binary_image = base64.b64decode(request.json['image'])
        pi._extension = request.json['extension']
        cid    = request.json['category_id']
        u = current_identity
        uid = u.id
    except KeyError:
        cid = None
        uid = None
        pass
    except BaseException as e:
        logger.exception(msg=str(e))
        return make_response(jsonify({'msg': error.error_string('MISSING_ARGS')}), status.HTTP_400_BAD_REQUEST)

    if cid is None or uid is None:
        return make_response(jsonify({'msg': error.error_string('MISSING_ARGS')}), status.HTTP_400_BAD_REQUEST)

    rsp = None
    session = dbsetup.Session()
    try:
        p = photo.Photo()
        d = p.save_user_image(session, pi, uid, cid)
        session.commit()
        if d['error'] is not None:
            rsp = make_response(jsonify({'msg': error.iiServerErrors.error_message(d['error'])}), error.iiServerErrors.http_status(d['error']))
        else:
            rsp = make_response(jsonify({'msg': error.error_string('PHOTO_UPLOADED'), 'filename': d['arg']}), status.HTTP_201_CREATED)
    except Exception as e:
        session.rollback()
        logger.exception(msg=str(e))
    finally:
        session.close()
        if rsp is None:
            rsp = make_response(jsonify({'msg': error.error_string('UPLOAD_ERROR')}), status.HTTP_500_INTERNAL_SERVER_ERROR)

        return rsp

@app.route("/file/<int:cid>", methods=['POST'])
@jwt_required()
def upload_file():
    """
    Upload file
    ---
    tags:
      - image
    summary: "upload a binary image to the site"
    operationId: upload-image
    consumes:
      - image/jpeg
    produces:
      - text/html
    parameters:
      - in: path
        name: cid
        description: "The id of the category to upload the file to"
        required: true
        type: integer
    security:
      - JWT: []
    responses:
      201:
        description: "The image was properly uploaded!"
        schema:
          id: filename
          properties:
            filename:
              type: string
      404:
        description: "image not found"
        schema:
          $ref: '#/definitions/Error'
    """
    rsp = None
    session = dbsetup.Session()
    try:
        uid = current_identity
        if 'file' not in request.files:
            rsp = make_response(jsonify({'msg': error.error_string('MISSING_ARGS')}), status.HTTP_400_BAD_REQUEST)
        else:
            file = request.files['file']
            pi = photo.PhotoImage()
            pi._binary_image = file
            pi._extension = file.filename.rsplit('.',1)[1].upper() # extract extension
            p = photo.Photo()
            d = p.save_user_image(session, pi, uid, cid)
            if d['error'] is not None:
                rsp = make_response(jsonify({'msg': error.iiServerErrors.error_message(d['error'])}), error.iiServerErrors.http_status(d['error']))
            else:
                session.commit()
                rsp = make_response(jsonify({'msg': error.error_string('PHOTO_UPLOADED'), 'filename': d['arg']}), status.HTTP_201_CREATED)
    except Exception as e:
        logger.exception(msg=str(e))
        rsp = make_response(jsonify({'msg': error.error_string('UPLOAD_ERROR')}), status.HTTP_500_INTERNAL_SERVER_ERROR)
    finally:
        session.close()

    return rsp

@app.route("/log", methods=['POST'])
@jwt_required()
def log_event():
    """
    Log ClientEvent
    ---
    tags:
      - admin
    summary: "log an error condition from the client"
    operationId: log
    consumes:
      - application/json
    produces:
      - application/json
    parameters:
      - in: body
        name: log-info
        required: true
        schema:
          id: upload_log
          required:
            - msg
          properties:
            msg:
              type: string
              description: "descriptive message of problem"
    security:
      - JWT: []
    responses:
      200:
        description: "The data was logged"
      400:
        description: "missing required arguments"
        schema:
          $ref: '#/definitions/Error'
      500:
        description: "error uploading log!"
        schema:
          $ref: '#/definitions/Error'
      default:
        description: "unexpected error"
        schema:
          $ref: '#/definitions/Error'
    """
    if not request.json:
        return make_response(jsonify({'msg': error.error_string('NO_JSON')}), status.HTTP_400_BAD_REQUEST)

    try:
        client_msg = request.json['msg']
        client_logger.error(msg=client_msg)
    except Exception as e:
        logger.exception(msg=str(e))
        return make_response(jsonify({'msg': error.error_string('UPLOAD_ERROR')}), status.HTTP_500_INTERNAL_SERVER_ERROR)

    return make_response(jsonify({'msg': 'OK'}), status.HTTP_200_OK)

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
      - JWT: []
    responses:
      201:
        description: "account created"
      400:
        description: "missing required arguments"
        schema:
          $ref: '#/definitions/Error'
      500:
        description: "error creating account"
        schema:
          $ref: '#/definitions/Error'
      default:
        description: "unexpected error"
        schema:
          $ref: '#/definitions/Error'
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

    try:
        rsp = None
        session = dbsetup.Session()
        if usermgr.AnonUser.is_guid(emailaddress, password):
            foundAnonUser = usermgr.AnonUser.find_anon_user(session, emailaddress)
            if foundAnonUser is not None:
                rsp = make_response(jsonify({'msg': error.error_string('ANON_ALREADY_EXISTS')}), status.HTTP_400_BAD_REQUEST)
            else:
                newAnonUser = usermgr.AnonUser.create_anon_user(session, emailaddress)
                if newAnonUser is None:
                    rsp = make_response(jsonify({'msg': error.error_string('ANON_USER_ERROR')}), status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            foundUser = usermgr.User.find_user_by_email(session, emailaddress)
            if foundUser is not None:
                rsp = make_response(jsonify({'msg':error.error_string('USER_ALREADY_EXISTS')}), status.HTTP_400_BAD_REQUEST)
            else:
                # okay the request is valid and the user was not found, so we can
                # create their account
                newUser = usermgr.User.create_user(session, guid, emailaddress, password)
                if newUser is None:
                    rsp =  make_response(jsonify({'msg': error.error_string('USER_CREATE_ERROR')}),status.HTTP_500_INTERNAL_SERVER_ERROR)

        if rsp is None:
            rsp = make_response(jsonify({'msg': error.error_string('ACCOUNT_CREATED')}), 201)
        session.commit()
    except:
        session.rollback()
        logger.exception(msg=str(e))
        rsp = make_response(jsonify({'msg': error.error_string('USER_CREATE_ERROR')}), status.HTTP_500_INTERNAL_SERVER_ERROR)
    finally:
        session.close()
        return rsp

@app.route('/preview/<int:pid>')
def download_photo(pid):
    """
    Preview Photo
    ---
    tags:
      - image
    summary: "download a watermarked thumbnail of a photo on the site"
    operationId: preview-image
    consumes:
      - text/html
    produces:
      - image/jpeg
    parameters:
      - in: path
        name: pid
        description: "The id of the photo to be downloaded"
        required: true
        type: integer
    responses:
      200:
        description: "image found"
        schema:
          id: download_image
          properties:
            image:
              type: string
              description: "base64 encoded image file"
      404:
        description: "image not found"
        schema:
          $ref: '#/definitions/Error'
    """
    p = photo.Photo()
    session = dbsetup.Session()
    rsp = None
    try:
        image_binary = p.read_thumbnail_by_id_with_watermark(session, pid)
        rsp = make_response(image_binary, status.HTTP_200_OK)
        rsp.headers['Content-Type'] = 'image/jpeg'
        rsp.headers['Content-Disposition'] = 'attachment; filename=img.jpg'
    except Exception as e:
        rsp = make_response('image not found', status.HTTP_404_NOT_FOUND)
    finally:
        session.close()

    return rsp

if __name__ == '__main__':
    dbsetup.metadata.create_all(bind=dbsetup.engine, checkfirst=True)
    if not dbsetup.is_gunicorn():
        if "DEBUG" in os.environ:
            if os.environ.get('DEBUG', '0') == '1':
                dbsetup._DEBUG = 1

        app.run(host='0.0.0.0', port=8080)
