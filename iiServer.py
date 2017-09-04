import datetime
import base64

from flask import Flask, jsonify
from flask     import request, redirect, make_response, current_app
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
from models import traction
from models import admin
from models import engagement
from models import event
from flask_swagger import swagger
from leaderboard.leaderboard import Leaderboard
import random
import logging
import os
from sqlalchemy import text
from sqlalchemy.orm import Session
from random import shuffle
from datetime import timedelta

from logsetup import logger, client_logger, timeit
from urllib.parse import urlparse
import uuid
from models import userprofile
from flask_cors import CORS, cross_origin
from controllers import categorymgr

app = Flask(__name__)
app.debug = True
app.config['SECRET_KEY'] = 'imageimprove3077b47'

is_gunicorn = False

__version__ = '1.5.7' #our version string PEP 440


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
_jwt.auth_response_callback = usermgr.auth_response_handler # so we can add to the response going back

@app.route("/spec/swagger.json")
@timeit()
def spec():
    """
    Specification
    A JSON formatted OpenAPI/Swagger document formatting the API
    ---
    tags:
      - admin
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
                                 "Currently there are no limits on how many photos a user can upload to a single category.\n"

    swag['info']['contact'] = {'name':'apimaster@imageimprov.com'}
    swag['schemes'] = ['https']
    swag['host'] = "api.imageimprov.com"

    swag['paths']["/auth"] = {'post':{'consumes': ['application/json'],
                                      'description':'JWT authentication',
                                      'operationId': 'jwt-auth',
                                      'produces' : ['application/json'],
                                      'parameters': [{'in': 'body',
                                                      'name': 'credentials',
                                                     'schema':
                                                        {'required': ['username', 'password'],
                                                         'properties':{'username':{'type':'string', 'example':'user@gmail.com'},
                                                                        'password':{'type':'string', 'example':'mysecretpassword'}},
                                                         }}],
                                      'responses': {'200':{'description': 'user authenticated',
                                                           'schema':
                                                               {'properties':
                                                                    {'access_token':
                                                                         {'type':'string', 'description': 'JWT access token', 'example' : 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJ0b3B0YWwuY29tIiwiZXhwIjoxNDI2NDIwODAwLCJodHRwOi8vdG9wdGFsLmNvbS9qd3RfY2xhaW1zL2lzX2FkbWluIjp0cnVlLCJjb21wYW55IjoiVG9wdGFsIiwiYXdlc29tZSI6dHJ1ZX0.yRQYnWzskCZUxPwaQupWkiUzKELZ49eM7oWxAQK_ZXw'},
                                                                     'email':
                                                                         {'type':'string', 'example': 'user@gmail.com'}
                                                                     }
                                                                }
                                                           },
                                                    '401':{'description': 'user authentication failed'}
                                                    },
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
@timeit()
def hello():
    """
    Configuration
    Simple page that checks some connections to make sure we are setup properly
    ---
    tags:
      - admin
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
                "<li>v1.5.0</li>" \
                "  <ul>" \
                "    <li>/newevent with user-specific categories</li>" \
                "  </ul>" \
                "<li>v1.5.1</li>" \
                "  <ul>" \
                "    <li>/category now returns user-specific categories createdc by /newevent</li>" \
                "  </ul>" \
                "<li>v1.5.2</li>" \
                "  <ul>" \
                "    <li>/category OPEN categories now includes PENDING</li>" \
                "  </ul>" \
                "<li>v1.5.3</li>" \
                "  <ul>" \
                "    <li>/newevent returns 'accesskey' on success</li>" \
                "    <li>'accesskey' values pulled from table randomized</li>" \
                "  </ul>" \
                "<li>v1.5.4</li>" \
                "  <ul>" \
                "    <li>/joinevent implemented & defined</li>" \
                "  </ul>" \
                "<li>v1.5.5</li>" \
                "  <ul>" \
                "    <li>/cors_auth for authentication from Javascript/browsers (admin tools)</li>" \
                "  </ul>" \
                "<li>v1.5.6</li>" \
                "  <ul>" \
                "    <li>/photo/<cid>/<dir>/<pid> for pathing photo ids</li>" \
                "    <li>added CORS tag to /category so Javascript can get category list</li>" \
                "  </ul>" \
                "<li>v1.5.7</li>" \
                "  <ul>" \
                "    <li>/event - lists all active events this user has rights to see</li>" \
                "  </ul>" \
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
    au = usermgr.AnonUser.get_anon_user_by_id(session, 1)
    cl = category.Category.active_categories(session, au)
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
                lb_list = tm.fetch_leaderboard(session, 0, c) # dummy user id
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
                if lb_list is None:
                    htmlbody += "\n<br>no leaderboard!"
                else:
                    htmlbody += "\n<br>found leaderboard"

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
                    lb = tm.get_leaderboard_by_category(session, c, check_exist=True)
                    lbname = tm.leaderboard_name(c)
                    lb_count = lb.total_members_in(lbname)
                    htmlbody += "<br>{} entries in the leaderboard".format(lb_count)
                except Exception as e:
                    logger.exception(msg='/config failed to get leaderboard count')
                    htmlbody += "<br><i>failure getting leaderboard count for category ({0})</i>".format(str(e))

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
@timeit()
def set_category_state():
    """
    Set Category State
    Sets the category state to a specific value - testing only! User account must have admin privileges.
    ---
    tags:
      - admin
    description: "Sets the category state to a specific value - testing only! User account must have admin privileges."
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
              example: 534
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

    u = current_identity
    if u.usertype != usermgr.UserType.IISTAFF.value:
        rsp = make_response(jsonify({'msg': error.error_string('RESTRICTED_API')}), status.HTTP_403_FORBIDDEN)

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
@cross_origin(origins='*')
@jwt_required()
@timeit()
def get_category():
    """
    Fetch Category
    Fetched specified category information
    ---
    tags:
      - category
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
              example: "Flowers"
            start:
              type: string
              description: "When the category starts and uploading can begin, UTC time"
              example: "2017-09-03 13:50"
            end:
              type: string
              description: "When voting on this category ends"
              example: "2017-09-06 15:50"
            state:
              type: string
              enum:
                - UPLOAD
                - VOTING
                - COUNTING
                - CLOSED
                - PENDING
              description: "The current state of the category (VOTING, UPLOADING, CLOSED, etc.)"
            round:
              type: integer
              description: "Which round of voting the category is in."
              example: 1
    """
    rsp = None
    try:
        session = dbsetup.Session()
        cm = categorymgr.CategoryManager()
        cl = cm.active_categories_for_user(session, current_identity._get_current_object())
        session.close()
        if cl is None:
#           categories = []
#           rsp = make_response(jsonify(categories), status.HTTP_200_OK)
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
@timeit()
def get_leaderboard():
    """
    Get Leader Board
    Returns a list of the top 10 photos as well as the caller's (so 11 in total)
    ---
    tags:
      - user
    operationId: get-leaderboard
    parameters:
      - in: query
        name: category_id
        description: "Category of the leaderboard being requested"
        example: 537
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
              example: "someuser@hotmail.com"
            rank:
              type: integer
              description: "overall rank in scoring"
              example: 3
            score:
              type: integer
              description: "actual score for this rank"
              example: 23775
            votes:
              type: integer
              description: "how many times this photo has been voted on"
              example: 47
            likes:
              type: integer
              description: "how many times this photo has been liked"
              example: 12
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
            c = category.Category.read_category_by_id(cid, session)
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
@timeit()
def get_ballot():
    """
    Get Ballot()
    A list of photos to be voted on, currently no more than 4
    ---
    tags:
      - voting
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
         schema:
           $ref: '#/definitions/CategoryBallots'
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
              description: 'the ballot id, uniquely identifies the ballot this entry is associated with'
              type: integer
            orientation:
              description: 'the EXIF orientation of photo (all should be 1!!)'
              type: integer
              enum:
                - 1
            votes:
              type: integer
              description: 'current number of votes for this photo'
            likes:
              type: integer
              description: 'current number of likes for this photo'
            score:
              type: integer
              description: 'current score for this photo'
            tags:
              type: array
              description: "list of pre-defined tags user can select from"
              items:
                type: string
              example: ['Fluff', 'Square', 'Yellow', 'Old']
            image:
              type: string
              description: 'base64 encoded string of JPEG image data'
      - schema:
          id: Ballots
          type: array
          items:
            $ref: '#/definitions/Ballot'
      - schema:
          id: CategoryBallots
          properties:
            category:
              $ref: '#/definitions/Category'
            ballots:
              $ref: '#/definitions/Ballots'
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
        Called to indicate a user has accepted a friend request
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
    Issue a friendship request, server will notify person to become a friend and join site if necessary
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
@timeit()
def cast_vote():
    """
     Cast Vote
     Cast votes for a ballot. Will return a ballot from a random category.
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
     security:
       - JWT: []
     responses:
       200:
         description: ballot of images user has voted on with originating category information
         schema:
           $ref: '#/definitions/CategoryBallots'
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
            tags:
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
    '''
    If category passed in is in the UPLOAD state, then we'll
    allow voting on it.
    :param session:
    :param uid:
    :param cid:
    :return:
    '''
    rsp = None
    try:
        bm = voting.BallotManager()
        if cid is None:
            cl = bm.active_voting_categories(session, uid)
            shuffle(cl)
            c = cl[0]
        else:
            c = category.Category.read_category_by_id(cid, session)

        allow_upload = c.state == category.CategoryState.UPLOAD.value

        ballots = bm.create_ballot(session, uid, c, allow_upload)
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
@timeit()
def image_download():
    """
    Image Download
    Download an image. If we have a filename, we can download the full image
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
@timeit()
def last_submission():
    """
    Get Last Submission
    returns the last submission for this user
    ---
    tags:
      - user
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

@app.route("/photo/<int:cid>/<string:dir>/<int:pid>", methods=['GET'])
@cross_origin(origins='*')
@jwt_required()
@timeit()
def category_photo_list(cid: int, dir: str, pid: int):
    """
    List of Categories Photos
    returns a list of photos in the specified category
    restricted usage, ImageImprov staff only!
    ---
    tags:
      - admin
    operationId: photo-list
    consumes:
      - text/html
    produces:
      - application/json
    parameters:
      - in: path
        name: cid
        description: "The category id we are inspecting"
        required: true
        type: integer
    security:
      - JWT: []
    responses:
      200:
         description: "list of photos that are in this category"
         schema:
          $ref: '#/definitions/PhotoInfo'
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
    definitions:
      - schema:
          id: PhotoInfo
          properties:
            id:
              type: integer
              description: Photo Identifier
              example: "27432"
            offensive:
              type: boolean
              description: indicates photo was deemed offensive (flagged)
            active:
              type: boolean
              description: "=True, record is active"
            likes:
              type: integer
              description: "# of likes this photo has"
              example: 3
    """
    u = current_identity
    if u.usertype != usermgr.UserType.IISTAFF.value:
        rsp = make_response(jsonify({'msg': error.error_string('RESTRICTED_API')}), status.HTTP_403_FORBIDDEN)

    session = dbsetup.Session()
    try:
        cm = categorymgr.CategoryManager()
        pl = cm.category_photo_list(session, dir, pid, cid)
        d_photos = cm.photo_dict(pl)
        rsp = make_response(jsonify(d_photos), status.HTTP_200_OK)

    except Exception as e:
        logger.exception(msg="[/photo/{0}/{1}/{2}".format(cid, dir, pid))
        rsp = make_response(jsonify({'msg': error.error_string('NOT_IMPLEMENTED')}), status.HTTP_500_INTERNAL_SERVER_ERROR)
    finally:
        session.close()
        if rsp is not None:
            return rsp

    return make_response(jsonify({'msg': error.error_string('NOT_IMPLEMENTED')}), status.HTTP_501_NOT_IMPLEMENTED)


@app.route("/photo", methods=['POST'])
@jwt_required()
@timeit()
def photo_upload():
    """
    Upload Photo
    Upload a photo for the specified category
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
              description: "the category id of the current category accepting uploads"
              example: 543
            extension:
              type: string
              enum:
                - JPEG
                - JPG
              description: "Extension/filetype of uploaded image"
            image:
              type: string
              description: "Base64 encoded image"
              example: "R0lGODlhPQBEAPeoAJosM//AwO/AwHVYZ/z595kzAP/s7P+goOXMv8+fhw/v739/f+8PD98fH/8mJl+fn/9ZWb8/PzWlwv6wWGbImAPgTEMImIN9gUFCEm"
    security:
      - JWT: []
    responses:
      200:
         description: 'list of images to vote on for the category just uploaded to (if at least 50 images in category)'
         schema:
           $ref: '#/definitions/CategoryBallots'
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
        cid = request.json['category_id']
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

    return store_photo(pi, uid, cid)

def store_photo(pi: photo.PhotoImage, uid: int, cid: int):
    rsp = None
    session = dbsetup.Session()
    num_photos_in_category = 0
    try:
        p = photo.Photo()
        d = p.save_user_image(session, pi, uid, cid)
        session.commit()
        if d['error'] is not None:
            rsp = make_response(jsonify({'msg': error.iiServerErrors.error_message(d['error'])}), error.iiServerErrors.http_status(d['error']))
        else:
            num_photos_in_category = photo.Photo.count_by_category(session, cid)
            rsp = make_response(jsonify({'msg': error.error_string('PHOTO_UPLOADED'), 'filename': d['arg']}), status.HTTP_201_CREATED)

    except Exception as e:
        session.rollback()
        logger.exception(msg=str(e))
    finally:
        session.close()
        if rsp is None:
            rsp = make_response(jsonify({'msg': error.error_string('UPLOAD_ERROR')}), status.HTTP_500_INTERNAL_SERVER_ERROR)

    # if the user has successfully uploaded a picture, and there are
    # at least 50 images in this category, then let's send back
    # a ballot for that category
    if rsp.status_code == status.HTTP_201_CREATED and num_photos_in_category > dbsetup.Configuration.UPLOAD_CATEGORY_PICS:
        try:
            return return_ballot(dbsetup.Session(), uid, cid)
        except Exception as e:
            pass     # Note: If anything goes wrong, forget the return ballot and just return success for the upload

    return rsp

@app.route("/jpeg/<int:cid>", methods=['POST'])
@jwt_required()
@timeit()
def jpeg_photo_upload(cid: int):
    """
    Upload Raw JPEG
    Upload a JPEG photo for the specified category
    ---
    tags:
      - image
    operationId: jpeg
    consumes:
      - image/jpeg
    produces:
      - application/json
    parameters:
      - in: path
        name: cid
        description: "The category id to upload the photo to"
        required: true
        type: integer
    security:
      - JWT: []
    responses:
      200:
         description: 'list of images to vote on for the category just uploaded to (if at least 50 images in category)'
         schema:
           $ref: '#/definitions/CategoryBallots'
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
#    if not request.json:
#        return make_response(jsonify({'msg': error.error_string('NO_JSON')}), status.HTTP_400_BAD_REQUEST)

    pi = photo.PhotoImage()
    try:
        pi._binary_image = request.data
        pi._extension = 'JPEG'
        u = current_identity
        uid = u.id
    except KeyError:
        uid = None
        pass
    except BaseException as e:
        logger.exception(msg=str(e))
        return make_response(jsonify({'msg': error.error_string('MISSING_ARGS')}), status.HTTP_400_BAD_REQUEST)

    if cid is None or uid is None or request.content_length < 100:
        return make_response(jsonify({'msg': error.error_string('MISSING_ARGS')}), status.HTTP_400_BAD_REQUEST)

    return store_photo(pi, uid, cid)

# @app.route("/file/<int:cid>", methods=['POST'])
# @jwt_required()
# @timeit()
# def upload_file():
#     """
#     Upload file
#     ---
#     tags:
#       - image
#     description: "upload a binary image to the site"
#     operationId: upload-image
#     consumes:
#       - image/jpeg
#     produces:
#       - text/html
#     parameters:
#       - in: path
#         name: cid
#         description: "The id of the category to upload the file to"
#         required: true
#         type: integer
#     security:
#       - JWT: []
#     responses:
#       201:
#         description: "The image was properly uploaded!"
#         schema:
#           id: filename
#           properties:
#             filename:
#               type: string
#       404:
#         description: "image not found"
#         schema:
#           $ref: '#/definitions/Error'
#     """
#     rsp = None
#     session = dbsetup.Session()
#     try:
#         uid = current_identity
#         if 'file' not in request.files:
#             rsp = make_response(jsonify({'msg': error.error_string('MISSING_ARGS')}), status.HTTP_400_BAD_REQUEST)
#         else:
#             file = request.files['file']
#             pi = photo.PhotoImage()
#             pi._binary_image = file
#             pi._extension = file.filename.rsplit('.',1)[1].upper() # extract extension
#             p = photo.Photo()
#             d = p.save_user_image(session, pi, uid, cid)
#             if d['error'] is not None:
#                 rsp = make_response(jsonify({'msg': error.iiServerErrors.error_message(d['error'])}), error.iiServerErrors.http_status(d['error']))
#             else:
#                 session.commit()
#                 rsp = make_response(jsonify({'msg': error.error_string('PHOTO_UPLOADED'), 'filename': d['arg']}), status.HTTP_201_CREATED)
#     except Exception as e:
#         logger.exception(msg=str(e))
#         rsp = make_response(jsonify({'msg': error.error_string('UPLOAD_ERROR')}), status.HTTP_500_INTERNAL_SERVER_ERROR)
#     finally:
#         session.close()
#
#     return rsp

@app.route("/log", methods=['POST'])
@jwt_required()
@timeit()
def log_event():
    """
    Log ClientEvent
    Log an error condition from the client
    ---
    tags:
      - admin
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

def register_anonuser(session, guid):
    '''
    See if the specified anonymous user is in the system,
    if not create the acount.
    :param session:
    :param guid:
    :return:
    '''
    foundAnonUser = usermgr.AnonUser.find_anon_user(session, guid)
    if foundAnonUser is not None:
        logger.info(msg="[/register] anonymous user already exists for {0}".format(guid))
        return make_response(jsonify({'msg': error.error_string('ANON_ALREADY_EXISTS')}), status.HTTP_400_BAD_REQUEST)
    else:
        newAnonUser = usermgr.AnonUser.create_anon_user(session, guid)
        if newAnonUser is None:
            logger.error(msg='[/register] error creating anonymous user, guid = {0}'.format(guid))
            return make_response(jsonify({'msg': error.error_string('ANON_USER_ERROR')}), status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            session.commit()
            logger.info(msg="[/register] created anonymous user, guid = {0}".format(guid))
            return make_response(jsonify({'msg': error.error_string('ACCOUNT_CREATED')}), 201)

    return None

def register_legituser(session, emailaddress, password, guid):
    '''
    See if the specified user is in the system, if not then create
    a new account.
    :param session:
    :param emailaddress:
    :param password:
    :param guid:
    :return:
    '''
    foundUser = usermgr.User.find_user_by_email(session, emailaddress)
    if foundUser is not None:
        logger.info(msg='[/register] User already exists {0}'.format(emailaddress))
        return make_response(jsonify({'msg': error.error_string('USER_ALREADY_EXISTS')}), status.HTTP_400_BAD_REQUEST)

    newUser = usermgr.User.create_user(session, guid, emailaddress, password)
    if newUser is None:
        logger.error(msg="[/register] error creating user, emailaddress = {0}".format(emailaddress))
        return make_response(jsonify({'msg': error.error_string('USER_CREATE_ERROR')}),
                            status.HTTP_500_INTERNAL_SERVER_ERROR)
    session.commit()
    logger.info(msg="[/register] created user, emailaddress = {0}".format(emailaddress))
    return make_response(jsonify({'msg': error.error_string('ACCOUNT_CREATED')}), 201)

@app.route("/register", methods=['POST'])
@timeit()
def register():
    """
    Register (Create new account)
    Register a user
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
        logger.error(msg='[/register] Error reading json')
        return make_response(jsonify({'msg': error.error_string('NO_JSON')}), status.HTTP_400_BAD_REQUEST)

    try:
        emailaddress = request.json['username']
        password     = request.json['password']
        guid         = request.json['guid']
        logger.info(msg='[/register] registering username {0}, password {1}'.format(emailaddress, password))
        if guid is None or guid == "":
            guid = str(uuid.uuid1())
            guid = guid.upper().translate({ord(c): None for c in '-'})
            logger.info(msg='[/register] creating guid = {0}'.format(guid))
    except KeyError:
        emailaddress = None
        password = None

    if emailaddress is None or password is None:
        logger.error(msg='[/register] missing arguments')
        return make_response(jsonify({'msg': error.error_string('MISSING_ARGS')}), status.HTTP_400_BAD_REQUEST)

    session = dbsetup.Session()
    rsp = None
    try:
        if usermgr.AnonUser.is_guid(emailaddress, password):
            rsp = register_anonuser(session, emailaddress)
        else:
            rsp = register_legituser(session, emailaddress, password, guid)
    except:
        session.rollback()
        logger.exception(msg='[/register] registering user')
        rsp = make_response(jsonify({'msg': error.error_string('USER_CREATE_ERROR')}), status.HTTP_500_INTERNAL_SERVER_ERROR)
    finally:
        if rsp is None:
            logger.error(msg='[/register] response is empty!!')
            logger.error(msg="[/register] content ={0}".format(request.data.decode('utf-8')))
            rsp = make_response(jsonify({'msg': error.error_string('USER_CREATE_ERROR')}), status.HTTP_500_INTERNAL_SERVER_ERROR)
        session.close()
        return rsp

@app.route('/beta1')
def beta1():
    return landingpage('beta1')
@app.route('/beta2')
def beta2():
    return landingpage('beta2')
@app.route('/beta3')
def beta3():
    return landingpage('beta3')

@app.route('/play/<string:campaign>')
@app.route('/play')
@timeit()
def landingpage(campaign=None):
    session = dbsetup.Session()
    if campaign is None:
        campaign = 'none'

    o = urlparse(request.base_url)
    target_url = o.scheme + '://' + o.netloc + '/fun/index.html?campaign=' + campaign
    try:
        str_header = str(request.headers)
        str_referer = request.referrer
        tl = traction.TractionLog(campaign=campaign, header=str_header, referer=str_referer)
        session.add(tl)
        session.commit()
    except Exception as e:
        logger.exception(msg='error in traction logging')
        pass    # swallow up errors and redirect
    finally:
        session.close()
        return redirect(target_url, code=302)

@app.route('/preview/<int:pid>', methods=['GET'])
@cross_origin(origins='*')
@timeit()
def download_photo(pid):
    """
    Preview Photo
    Download a watermarked thumbnail of a photo on the site.
    Can be used to display images as URLs
    ---
    tags:
      - image
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
        logger.exception(msg="[/preview] error reading thumbnail!")
    finally:
        session.close()
        if rsp is None:
            rsp = make_response('image not found', status.HTTP_404_NOT_FOUND)

    return rsp

@app.route('/base')
@jwt_required()
@timeit()
def base_url():
    """
    Base URL
    Tell the app where the Base URL is located for this session e.g https://api.imageimprov.com or http:/104.38.47.3:8080
    ---
    tags:
      - admin
    operationId: base_url
    consumes:
      - text/html
    produces:
      - json/application
    security:
      - JWT: []
    responses:
      200:
        description: "base URL returned"
        schema:
          id: base
          properties:
            base:
              type: string
    """
    uid = current_identity.id
    session = dbsetup.Session()
    url = 'https://api.imageimprov.com/'
    try:
        url = usermgr.AnonUser.get_baseurl(session, uid)
    except Exception as e:
        logger.exception(msg="[/base] error fetching base for user {0}".format(uid))
        url = 'https://api.imageimprov.com/'
    finally:
        session.close()

    logger.info(msg="[/base] url = {0}, for user {1}".format(url, uid) )
    return make_response(jsonify({'base': url}), status.HTTP_200_OK)

@app.route('/forgotpwd')
@timeit()
def forgot_password():
    """
    Forgot Password
    Send a reset password link to a user's email address, password is NOT changed
    ---
    tags:
      - user
    operationId: forgot-password
    consumes:
      - text/html
    produces:
      - json/application
    parameters:
      - in: query
        name: email
        description: "The email address that has forgotten their password"
        required: true
        type: string
    responses:
      200:
        description: "password reset link sent to email address"
      404:
        description: "emailaddress not found!"
        schema:
          $ref: '#/definitions/Error'
    """
    session = dbsetup.Session()
    rsp = None
    try:
        emailaddress = request.args.get('email')
        logger.info(msg='[/forgotpwd] email = {}'.format(emailaddress))
        u = usermgr.User.find_user_by_email(session, emailaddress)
        if u is not None:
            cev = admin.CSRFevent(u.id, expiration_hours=24)
            if cev is not None:
                session.add(cev)
                cev.generate_csrf_token()
                http_status = admin.send_forgot_password_email(u.emailaddress, cev.csrf)
                session.commit()
                rsp = make_response('new password sent via email', status.HTTP_200_OK)
            else:
                msg = "error creating csrf token"
                logger.error(msg=msg)
                rsp = make_response(jsonify({'msg': msg}),status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            logger.error(msg="email address not found")
            rsp = make_response(jsonify({'msg': error.error_string('EMAIL_NOT_FOUND')}), status.HTTP_404_NOT_FOUND)
    except Exception as e:
        session.rollback()
        logger.exception(msg='[/forgotpwd]')
        rsp = make_response(jsonify({'msg': '[/forgotpwd] error'}), status.HTTP_500_INTERNAL_SERVER_ERROR)
    finally:
        session.close()
        if rsp is None:
            rsp = make_response(jsonify({'msg': 'weird error'}), status.HTTP_500_INTERNAL_SERVER_ERROR)
        return rsp

@app.route('/cors_auth', methods=['POST'])
@cross_origin(origins='*')
def CORS_auth():
    """
    CORS JWT Authentication
    Same as the /auth endpoint but allows CORS (Cross Origin Resource Sharing)
    access to the authentication endpoint. Utilizes the callback registered in
    Flask-JWT.
    Note: Inputs determine what type of authentication to perfor: username/password, anonymous or oAuth2 service provider
      1) If username is a hash of the password field, this is an anonymous user
      2) If username is the name of a defined service provider, then the password is an oAuth2 token
    ---
    tags:
      - admin
    operationId: cors-auth
    consumes:
      - application/json
    produces:
      - applications/json
    parameters:
      - in: body
        name: cors-credentials
        schema:
          id: auth_req
          required:
            - username
            - password
          properties:
            username:
              type: string
              description: "user to be authenticated"
              example: "someuser@gmail.com"
            password:
              type: string
              description: "clear text password"
              example: "mysecretpassw0rd!"
    responses:
      200:
        description: "user has been authenticated"
        schema:
          id: auth_info
          properties:
            access_token:
              type: string
              description: "JWT access token"
              example: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJ0b3B0YWwuY29tIiwiZXhwIjoxNDI2NDIwODAwLCJodHRwOi8vdG9wdGFsLmNvbS9qd3RfY2xhaW1zL2lzX2FkbWluIjp0cnVlLCJjb21wYW55IjoiVG9wdGFsIiwiYXdlc29tZSI6dHJ1ZX0.yRQYnWzskCZUxPwaQupWkiUzKELZ49eM7oWxAQK_ZXw"
            emailaddress:
              type: string
              description: "email address of user authenticated (if available)"
              example: "someuser@gmail.com"
      401:
        description: "error authenticating user"
        schema:
          $ref: '#/definitions/Error'
    """
    return _jwt.auth_request_callback()


@app.route('/resetpwd', methods=['POST'])
@cross_origin(origins='*')
@timeit()
def reset_password():
    """
    Reset Password
    Reset a user's password
    ---
    tags:
      - user
    operationId: reset-password
    consumes:
      - text/html
    produces:
      - text/html
    parameters:
      - in: query
        name: token
        description: "a csrf token that uniquely identifies this activity"
        required: true
        type: string
      - in: query
        name: pwd
        description: "The updated password"
        required: true
        type: string
    responses:
      200:
        description: "password reset, notification email set"
      403:
        description: "token is invalid"
        schema:
          $ref: '#/definitions/Error'
    """
    rsp = None
    session = dbsetup.Session()
    try:
        csrf = request.args.get('token')
        pwd = request.args.get('pwd')
        logger.info(msg='[/resetpwd] csrf = {}'.format(csrf))
        cev = admin.CSRFevent.get_csrfevent(session, csrf)
        if cev is None:
            logger.error(msg="csrf event not found!")
            http_status = status.HTTP_403_FORBIDDEN
        else:
            if not cev.isvalid():
                http_status = status.HTTP_403_FORBIDDEN
                logger.error(msg="[/resetpwd] csrf event is invalid, used or expired")
            else:
                u = usermgr.User.find_user_by_id(session, cev.user_id)
                # change the password
                u.change_password(session, pwd)
                http_status = status.HTTP_200_OK
                admin.send_reset_password_notification_email(u.emailaddress)
                cev.markused() # invalidate from future usage!
                session.commit()
                logger.info(msg="[/resetpwd] user password reset")

        if http_status == status.HTTP_200_OK:
            msg = 'password updated, notification sent'
        elif http_status == status.HTTP_403_FORBIDDEN:
            msg = 'csrf token expired or has been used'
        else:
            msg = 'something bad happened'

        rsp = make_response(jsonify({'msg': msg}), http_status)
    except Exception as e:
        session.rollback()
        logger.exception(msg="[/resetpwd] exception resetting user's password")
        rsp = make_response(jsonify({'msg': 'bad request'}), status.HTTP_500_INTERNAL_SERVER_ERROR)
    finally:
        session.close()

    return rsp

@app.route('/submissions')
@jwt_required()
def my_submissions_tst():
    '''
    needed to support /<campaign> route and testing
    :return:
    '''
    return my_submissions(None, None)

@app.route('/submissions/<string:dir>/<int:cid>')
@jwt_required()
@timeit()
def my_submissions(dir: str, cid: int):
    """
    My Submissions
    Retrieve a pageable list of photos the user has submitted
    ---
    tags:
      - user
    operationId: submission
    consumes:
      - text/html
    produces:
      - application/json
    parameters:
      - in: path
        name: dir
        description: "next/prev direction from specified category id for next page"
        required: true
        type: string
        enum:
          - next
          - prev
      - in: path
        name: cid
        description: "category id to start fetch from, if 0 fetch around active categories"
        required: true
        type: int
      - in: query
        name: num_categories
        description: "The number of categories to fetch in a single call, if not specified all will be fetched"
        required: false
        type: int
    security:
      - JWT: []
    responses:
      200:
        description: "page of submissions"
        schema:
          $ref: '#/definitions/SubmissionResp'
      404:
        description: "image not found"
        schema:
          $ref: '#/definitions/Error'
    definitions:
      - schema:
          id: PhotoDetail
          properties:
            pid:
              type: integer
              description: "unique photo identifier"
              example: 1380547
            url:
              type: string
              description: "URL to retrieve photo thumbnail .JPEG image, prefix baseURL and slash"
              example: "https://api.imageimprov.com/preview/537"
            votes:
              type: integer
              description: "number of votes photo has received"
              example: 3
            likes:
              type: integer
              description: "number of likes photo has received"
              example: 4
            score:
              type: integer
              description: "The score this photo has accumulated"
              example: 7438
            tags:
              type: array
              description: "List of tags associated with photo"
              example: ["fluffy", "colorful", "rough", "crude"]
      - schema:
          id: PhotoDetails
          type: array
          items:
            $ref: '#/definitions/PhotoDetail'
      - schema:
          id: CategoryPhotos
          properties:
            category:
              $ref: '#/definitions/Category'
            photos:
              $ref: '#/definitions/PhotoDetails'
      - schema:
          id: SubmissionResp
          properties:
            id:
              type: integer
              description: "image improv user identifier"
              example: 24738
            created_date:
              type: string
              description: "date which this user account was created"
              example: "2017-09-23 12:47"
            submissions:
              type: array
              items:
                $ref: '#/definitions/CategoryPhotos'
    """
    if dir is None or cid is None or dir not in ('next', 'prev'):
        return make_response(jsonify({'msg': error.error_string('MISSING_ARGS')}), status.HTTP_400_BAD_REQUEST)

    num_categories = None
    try:
        num_categories = request.args.get('num_categories')
        if num_categories is not None:
            num_categories = int(num_categories)
    except ValueError:
        return make_response(jsonify({'msg': 'num_categories is not an integer value'}), status.HTTP_400_BAD_REQUEST)

    session = dbsetup.Session()
    try:
        profile = userprofile.Submissions(uid=current_identity.id)
        d = profile.get_user_submissions(session, dir, cid, num_categories)
        rsp = make_response(jsonify(d), status.HTTP_200_OK)
    except Exception as e:
        logger.exception(msg='[/submissions] error fetching users profile')
        rsp = make_response('really, really bad thing occured', status.HTTP_500_INTERNAL_SERVER_ERROR)
    finally:
        session.close()

    return rsp

@app.route('/update/photo', methods=['PUT'])
@app.route('/update/photo/<int:pid>', methods=['PUT'])
@timeit()
@jwt_required()
def update_photometa(pid):
    """
    Update Photo Data
    Update information associated with an image
    ---
    tags:
      - image
    operationId: update-image
    consumes:
      - application/json
    produces:
      - application/json
    parameters:
      - in: path
        name: pid
        description: "The id of the photo whose data is to be updated"
        required: true
        type: integer
      - in: body
        name: photo-data
        required: true
        schema:
          id: upload_photometa
          properties:
            like:
              type: boolean
              description: "indicates user likes the image"
            flag:
              type: boolean
              description: "indicates the user things the image is offensive"
            tags:
              type: array
              description: "list of strings user wants associated with image"
              example: ["solid", "round", "square", "fluffy"]
              items:
                type: string

    security:
      - JWT: []
    responses:
      200:
        description: "image information updated"
      404:
        description: "image not found"
        schema:
          $ref: '#/definitions/Error'
    """
    json_data = request.get_json()
    try:
        u = current_identity
        uid = u.id
        like = json_data['like']
        offensive = json_data['flag']
        tags = json_data['tags']
    except KeyError as ke:
        logger.exception(msg='error with reading JSON input')
        return make_response(jsonify({'msg': 'input argument error'}), status.HTTP_400_BAD_REQUEST)

    session = dbsetup.Session()
    rsp = None
    try:
        fbm = engagement.FeedbackManager(uid=uid, pid=pid, like=like, offensive=offensive, tags=tags)
        fbm.created_feedback(session)
        session.commit()
        rsp = make_response(jsonify({'msg': 'feedback updated'}), status.HTTP_200_CREATED)
    except Exception as e:
        logger.exception(msg="[/update] error updating photo metadata")
        rsp = make_response('image not found', status.HTTP_404_NOT_FOUND)
    finally:
        session.close()

    return rsp

@app.route('/newevent', methods=['POST'])
@jwt_required()
@timeit()
def create_event():
    """
    Create Private Event
    Create a category that is limited to invited users
    ---
    tags:
      - category
    operationId: create_event
    consumes:
      - application/json
    produces:
      - application/json
    parameters:
      - in: body
        name: event-info
        required: true
        schema:
          id: create-event
          required:
            - event_name
            - num_players
            - start_time
            - upload_duration
            - voting_duration
            - categories
          properties:
            event_name:
              type: string
              description: "The name of the overarching event"
              example: "Company Picnic 2017"
            num_players:
              type: integer
              description: "# of players allowed in the event"
              example: 5
            start_time:
              type: string
              description: "The UTC date/time when the event should start"
              example: "2017-09-03 15:30:00"
            upload_duration:
              type: integer
              description: "how long uploading should last in hours"
              example: 24
            voting_duration:
              type: integer
              description: "how long voting should last in hours"
              example: 72
            categories:
              type: array
              description: "themes to associate with this event"
              example: ["Team", "Fun", "Beer"]
              items:
                type: string
            games_excluded:
              type: array
              description: "games that are not included in this event"
              example: ["MatchIt!", "GuessWho?"]
              items:
                type: string
    security:
      - JWT: []
    responses:
      201:
        description: "event created"
      400:
        description: "error in specified arguments"
        schema:
          $ref: '#/definitions/Error'
    """
    json_data = request.get_json()
    try:
        u = current_identity
        uid = u.id
        eventname = json_data['event_name']
        numplayers = json_data['num_players']
        upload_duration = json_data['upload_duration']
        voting_duration = json_data['voting_duration']
        categories = json_data['categories']
        startdate = json_data['start_time']
        games_excluded = json_data.get('games_excluded', None)
    except KeyError as ke:
        logger.exception(msg='error with reading JSON input')
        return make_response(jsonify({'msg': 'input argument error'}), status.HTTP_400_BAD_REQUEST)

    session = dbsetup.Session()
    try:
        em = categorymgr.EventManager(user=current_identity, name=eventname, start_date=startdate, num_players=numplayers, upload_duration=upload_duration, vote_duration=voting_duration, categories=categories)
        em.create_event(session)
        session.commit()
        logger.info(msg="[/newevent] user {0} has created event {1}".format(u.id, em._e.accesskey))
        return make_response(jsonify({'accesskey': em._e.accesskey}), status.HTTP_201_CREATED)
    except Exception as e:
        session.close()
        logger.exception(msg="[/newevent] error creating event")

        if e.args[1] == 'badargs':
            return make_response(jsonify({'msg': 'input argument error'}), status.HTTP_400_BAD_REQUEST)

        return make_response(jsonify({'msg': 'error creating event'}), status.HTTP_500_INTERNAL_SERVER_ERROR)

    return make_response(jsonify({'msg': 'something really bad happened...'}), status.HTTP_500_INTERNAL_SERVER_ERROR)

@app.route('/joinevent', methods=['POST'])
@jwt_required()
@timeit()
def join_event():
    """
    Join a Private Event
    join an event (one or more categories) that was organized by another party
    ---
    tags:
      - category
    operationId: join_event
    consumes:
      - text/html
    produces:
      - application/json
    parameters:
      - in: query
        name: accesskey
        description: "string that uniquely identifies an event to join"
        example: "able move"
        required: true
        type: string
    security:
      - JWT: []
    responses:
      200:
        description: "category list for event"
        schema:
          id: categories
          type: array
          items:
            $ref: '#/definitions/Category'
      400:
        description: "error in specified arguments"
        schema:
          $ref: '#/definitions/Error'
    """

    session = dbsetup.Session()
    try:
        accesskey = request.args.get('accesskey')
        cl = categorymgr.EventManager.join_event(session, accesskey, current_identity._get_current_object())
        if cl is not None:
            categories = category.Category.list_to_json(cl)
            logger.info(msg="[/joinevent] user {0} has joined event {1}".format(current_identity.id, accesskey))
            return make_response(jsonify(categories), status.HTTP_200_OK)
    except KeyError:
        session.close()
        return make_response(jsonify({'msg': 'input argument error'}), status.HTTP_400_BAD_REQUEST)

    return make_response(jsonify({'msg': 'event not found or not categories'}), status.HTTP_500_INTERNAL_SERVER_ERROR)

@app.route('/event', methods=['GET'])
@jwt_required()
@timeit()
def event_status():
    """
    Event Status for User
    returns a list of active events this user is registered in
    ---
    tags:
      - category
    operationId: event_status
    consumes:
      - text/html
    produces:
      - application/json
    security:
      - JWT: []
    responses:
      200:
        description: "list of active events for this user"
        schema:
          id: events
          type: array
          items:
            $ref: '#/definitions/Event'
      400:
        description: "error in specified arguments"
        schema:
          $ref: '#/definitions/Error'
    definitions:
      - schema:
          id: Event
          properties:
            id:
              type: integer
              description: "unique internal event identifier"
              example: 1347
            accesskey:
              type: string
              description: "key phrase used to join this event"
              example: "able move"
            name:
              type: string
              description: "name of this event"
              example: "2017 Company Picnic"
            created:
              type: string
              description: "date/time this event was created, UTC"
              example: "2017-09-04 14:25"
            max_players:
              type: int
              description: "maximum number of players allowed in event"
              example: 5
            created_by:
              type: string
              description: "the user that created this event, or 'me' if the user making this call"
              example: "someuser@gmail.com -or- Image Improv -or- me"
            categories:
              type: array
              items:
                $ref: '#/definitions/Category'
    """

    session = dbsetup.Session()
    try:
        d_el = categorymgr.EventManager.events_for_user(session, current_identity._get_current_object())
        return make_response(jsonify(d_el), status.HTTP_200_OK)
    except KeyError:
        session.close()
        return make_response(jsonify({'msg': 'input argument error'}), status.HTTP_400_BAD_REQUEST)

    return make_response(jsonify({'msg': error.error_string('NOT_IMPLEMENTED')}), status.HTTP_501_NOT_IMPLEMENTED)

@app.route('/<string:campaign>')
def default_path(campaign: str):
    return landingpage(campaign)

@app.route('/')
def root_path():
    o = urlparse(request.base_url)
    target_url = o.scheme + '://' + o.netloc + '/fun/index.html'
    return redirect(target_url, code=302)

if __name__ == '__main__':
    dbsetup.metadata.create_all(bind=dbsetup.engine, checkfirst=True)
    if not dbsetup.is_gunicorn():
        if "DEBUG" in os.environ:
            if os.environ.get('DEBUG', '0') == '1':
                dbsetup._DEBUG = 1

        app.run(host='0.0.0.0', port=8080)
