---
title: Image Improve API
---

Anonymous Registration
----------------------

This is where the app gets a token for subsequent calls to the API. The endpoint
is the same as the “login” when there is a username/password, the inputs are
interpreted differently.

Inputs:

Username: 32-character unique identifier (probably a guid) that persists

Password: SHA224 of the above guid

Outputs:

OAuth 2.0 Token

The request should look something like (not working data):

POST /register HTTP/1.1

Host: localhost:5000

Content-Type: application/json

{

"username": " 78f65d7c99f94cc2bebb107f9ea4590a",

"password": "
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZGVudGl0eSI6MSwiaWF0IjoxNDQ0OTE3NjQwLCJ

uYmYiOjE0NDQ5MTc2NDAsImV4cCI6MTQ0NDkxNzk0MH0.KPmI6WSjRjlpzecPvs3q\_T3cJQvAgJvaQAPtk1abC\_E=="

}

Registration [method=POST]
--------------------------

Registering a new user. The username is the user’s email address. Successfully
only if an account can be created (i.e. username doesn’t already exist). The
“guid” is a 32-character unique identifier for the user created by the mobile
application as part of the anonymous registration process. This will allow
association to an existing anonymous account. This field is optional as a user
may login from a different mobile device that does not have access to this
information.

POST /register HTTP/1.1

Host: 192.168.1.124:5000

Content-Type: application/json

Cache-Control: no-cache

Postman-Token: ad8cb564-6fd3-7011-d0bc-09072fc3c60f

{

"username": "bp100a\@gmail.com",

"password": "pa55w0rd",

“guid”: “78f65d7c99f94cc2bebb107f9ea4590a”

}

Returns:

Status – success/failure

Login [method=POST]
-------------------

To facilitate testing this API provides a simplified login method that returns
the user context (user\_id) and the current available category (category\_id)
for this user.

Inputs:

Username (an email address)

Password (should this be hashed?)

Outputs:

User\_id =0 or not present indicates user was not found (something weird)

Category\_id =0 or not present indicates no available categories

The request should look something like this for username/password

POST /login HTTP/1.1

Host: localhost:5000

Content-Type: application/json

{

"username": "hcollins\@gmail.com",

"password": "pa55w0rd"

}

The response should look similar to:

HTTP/1.1 200 OK

Content-Type: application/json

{

“user\_id”:547,

“category\_id”:38

}

Authentication [method=POST]
----------------------------

This is where the app gets a token for subsequent calls to the API.

Inputs:

Username (an email address)

Password (should this be hashed?)

Outputs:

OAuth 2.0 Token

The request should look something like this for username/password

POST /auth HTTP/1.1

Host: localhost:5000

Content-Type: application/json

{

"username": "hcollins\@gmail.com",

"password": "pa55w0rd"

}

The response should look similar to:

HTTP/1.1 200 OK

Content-Type: application/json

{

"access\_token":
"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZGVudGl0eSI6MSwiaWF0IjoxNDQ0OTE3NjQwLCJuYmYiOjE0NDQ5MTc2NDAsImV4cCI6MTQ0NDkxNzk0MH0.KPmI6WSjRjlpzecPvs3q\_T3cJQvAgJvaQAPtk1abC\_E"

}

For authentication for anonymous users:

The request should look something like this for username/password

POST /auth HTTP/1.1

Host: localhost:5000

Content-Type: application/json

{

"username": "78f65d7c99f94cc2bebb107f9ea4590a",

"password": "
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZGVudGl0eSI6MSwiaWF0IjoxNDQ0OTE3NjQwLCJ

uYmYiOjE0NDQ5MTc2NDAsImV4cCI6MTQ0NDkxNzk0MH0.KPmI6WSjRjlpzecPvs3q\_T3cJQvAgJvaQAPtk1abC\_E=="

}

Where the “password” field is a hashing of the GUID passed in the username using
an agreed upon algorithm.

The response should look like the follow:

HTTP/1.1 200 OK

Content-Type: application/json

{

"access\_token":
"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZGVudGl0eSI6MSwiaWF0IjoxNDQ0OTE3NjQwLCJuYmYiOjE0NDQ5MTc2NDAsImV4cCI6MTQ0NDkxNzk0MH0.KPmI6WSjRjlpzecPvs3q\_T3cJQvAgJvaQAPtk1abC\_E"

}

Photo [method=POST]
-------------------

The REST i/f for uploading a file requires an access token from a previous call
to the Login service. A JWT token is passed (which encodes the user id) for
authorization. The image data is encoded Base64 and passed as a string in the
JSON body. Valid extensions are:

JPEG, JPG, PNG, BMP, TIFF

Success is indicated by an HTTP status code of 2xx (probably **202** “Accepted”,
indicating the file was decoded and written to the file system). If the image
does not conform to a known type, then a 4xx response code will be returned.

POST /photo HTTP/1.1

Host: 192.168.1.124:5000

Cache-Control: no-cache

Postman-Token: ad8cb564-6fd3-7011-d0bc-09072fc3c60f

Authorization: JWT
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZGVudGl0eSI6MSwiaWF0IjoxNDQ0OTE3NjQwLCJuYmYiOjE0NDQ5MTc2NDAsImV4cCI6MTQ0NDkxNzk0MH0.KPmI6WSjRjlpzecPvs3q\_T3cJQvAgJvaQAPtk1abC\_E

Content-Type: application/json

{

“image”:
“/9j/4AAQSkZJRgABAQAAAQABAAD/2wCEAAkGBhMSERUUExQVFRUWGBwYFhYWGBccGhoXGBcYFxoY

GBcaHSceFx0jGhcWHy8gJCcpLCwsFx4xNTAqNSYrLCkBCQoKBQUFDQUFDSkYEhgpKSkpKSkpKSkp”,

“extension”: “JPEG”,

“category\_id”: 19,

“user\_id” : 67

}

**Note:** The JSON entry “user\_id” is for testing without authorization tokens,
this user id will be encoded in the JWT token.

Lost Password (TBD)
-------------------

If the user has forgotten their password, we can generate an email to send them
to a web page for recovery (standard recover password work flow).

Email Address

Outputs:

Email to address specified that links to a web page for resetting password

Challenge [method=GET]
----------------------

The challenge (theme) for the day.

Token

Returns:

{

>   “category\_id”:1478,

>   “category\_description”:”Cute Puppies”,

>   “start”:”2017-03-08T15:07:55Z”,

>   “end”:”2017-03-09T13:04:47Z”

}

Ballot [method=GET]
-------------------

Returns an array of “ballots” that contain the ballot entry id (uniquely
identifying a voting instance) and the thumbnail image data as a Base64 encoded
value.

Input:

user\_id - user identifier, unique to user returned by login/registration

category\_id - category for which this voting is to be applied (*do we need
this?*)

Output:

{

“ballots”:

[

{“bid”: 1234, “image”:
“/9j/4AAQSkZJRgABAQAAAQABAAD/2wCEAAkGBhMSERUUExQVFRUWGBwYFhYWGBccGhoXGBcY”},

{“bid”: 1235, “image”: “/9j/4AAQSkZJRgABAQAAAQABAAD/2wCEAAkGBhMSERUU/”},

>   {“bid”: 2435, “image”:
>   “/9j/4AAQSkZJRgABAQAAAD/2wCEAAkGBhMSERUUExQVFRUWGBwYFhYWGBccGhoXGBpKSkpKSkp=”},

>   {“bid”: 3892, “image”:
>   “/9j/4AAQSkZJRgABAQAQABAAD/2wCEAAkGBhMSERUxQRUWGBwYFhYWGBccGoXGBSkpKSkpKSkp==”}

]

}

Vote [method=POST]
------------------

Results of the vote, pretty simple, the results from a previously retrieved
ballot are posted to the server for tabulation.

Token - JWT token, retrieved from login (/auth)

user\_id - integer internal user id (retrieved from login [/auth] or
registration)

votes - ballot entries and their votes

{

“user\_id”: 478921,

“votes”:

[

>   {“bid”:1234, “vote”:1, “like”:true},

>   {“bid”:1235, “vote”:3},

>   {“bid”:2435, “vote”:2, “like”:true},

>   {“bid”:3892, “vote”:-1}

]

}

**Note**: The *category\_id* is omitted since it’s implied with the *bid*
(ballot entries) being voted on. Since the ballot entry information is
de-normalized, it also includes the user\_id as well (so we can avoid having a
user vote on the same photo twice, though this could be a feature)

Leader Board [method=GET]
-------------------------

Can request the leaderboard for the day, return a list of current leaders.

Token

Returns:

{

“category\_id”: 5553,

“ranking”:

[

>   {“name”:”bp100a”, “score”:1010, “rank”:1},

>   {“name”:”elonmusk”, “score”:895, “rank”:3},

>   {“name”:”dblankley”, “score”:900, “rank”:2},

>   {“name”:”luke”, “score”:875, “rank”:4, “isfriend”: true}

]

}

Get Image Thumbnails (TBD)
--------------------------

Can get a series of thumbnails (9, for 3x3 ?) for a date range for the current
user. Perhaps we need an interface for paging through this information. Like
ballots, may need hotspots for retrieving an image selected.

Token

Date range ?

Returns

Thumbnails of Images uploaded

Get Image (TBD)
---------------

Token

Thumbnail chosen

Returns:

Full resolution image + metadata
