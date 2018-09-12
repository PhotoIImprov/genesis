# genesis
The RESTful API for the Image Improv mobile app.

Using Flask, we expose a RESTful API for our iOS & Android apps. Pretty standard stack:

Python/Flask/SQLAlchemy
Gunicorn/Nginx
Redis
MySQL
<photo storage>

We are using JWT for security, and support oAuth2 to link up with Facebook, Google, etc.

Test suite provides good coverage. Can be hosted in Linux (Gunicorn/Nginx) or Windows (Waitress/Nginx)
