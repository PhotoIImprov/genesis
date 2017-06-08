#!/bin/bash
#
# Redis server creation script.
# -------------------------
# Author: HjC
#
# This script will initialize a GCE instance to run the Redis
#
# 14-May-2017 HjC
#  - add ii_deploy GCS mount point (/mnt/gcs-deploy)
#  - add binding for local IP and 127.0.0.1
#  - disable registration of REDIS to db for DEBUGGING
#  - download /genesis project for sync_leaderboard daemon
#
# 15-May-2017 HjC
#  - remove setup for ii_photos GCS mount point (/mnt/gcs-photos)

# Check to see if this script has already been run
file="/home/bp100a/gcs-serviceaccount.json"
if [ -f "$file" ]
then
   echo "script already run, exiting"
   exit 0
else
   echo "first time running script, proceeding"
fi

# Step #1
# update and get necessary tools installed
apt-get update
if [ $IMAGE != 'jessie']
then
	apt-get install python3.5
	apt-get install --assume-y git
else
	echo "...installing git"
	apt-get install -y git
	echo "... git install complete"
fi

export SQLINSTANCE=imageimprov:us-central1:ii-sql001

echo "...installing python3-pip"
apt-get -y install python3-pip
echo "...python3-pip installation completed"
# We use GCSfuse to connection to the Google Storage bucket where all 
# the photos are, as well as some files we are going to need to complete
# installation

echo "...installing gcsfuse to map photo drive"
export GCSFUSE_REPO=gcsfuse-`lsb_release -c -s`
echo "deb http://packages.cloud.google.com/apt $GCSFUSE_REPO main" | tee /etc/apt/sources.list.d/gcsfuse.list
curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | apt-key add -
apt-get update
apt-get install -y gcsfuse
echo "...gcsfuse installation completed"

#*******************************************************************************
# Couldn't get deployment keys to work, created a read-only account
cd /home/bp100a
echo "...cloning github repository"
git clone https://bp100aRO:Imag3Impr0v!@github.com/PhotoIImprov/genesis.git
#
#*******************************************************************************

# install all the modules we are going to need
pip3 install --upgrade pip

# finally install our requirements to run python
cd /home/bp100a/genesis
echo "...pip3 install requirements.txt"
sudo -H pip3 install -r requirements.txt

# now mount our photo bucket! Note we use "allow_other" so that even though the root is mounting it, it will be accessible by all

cd /home/bp100a
echo '{' >gcs-serviceaccount.json
echo '  "type": "service_account",' >> gcs-serviceaccount.json
echo '  "project_id": "imageimprov",' >> gcs-serviceaccount.json
echo '  "private_key_id": "8ec8fe753476f7205d89020f3e38fcc003af8cab",' >> gcs-serviceaccount.json
echo '  "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQCnV9VTsyVs5Dkb\n1g3ezA3aKijodU0wl2D3LXaQ8Nt6RBSqFenq4eAS4AFw3Bud5xAn+qa6ulhAkqn1\nPpgJ4eiHr2LWHrDNMkXT6Ef0+1TBiWHkcf6Nhbj7Hv0jVKFqHUx6aB2YjLYRjv6q\ndwgxVm3Si0IIe8iLt4SZakauWh6YAd9K+yJFTnkweDZpzjVkeuh/aOw67MmjOY7B\ns/rTdlRMxBUnH6ouwZz+qIh44ZpJzxpaNvmdILwkrge7Twwbvqo1AWTTvtPL1oRc\n08M9vtkTeqe2pt5W2MD6rrV2tpHqcfk/R2M80jp6lXWyuyATinbimgHmMSxw4TMI\norJD0xZxAgMBAAECggEAP4Vyv8PX5/61wuA9AZ55f5/TSXIFa/V6ZDlIsXoMBdxD\n79BDq9ozwVZwlZOnlAe6tUJK+cR0bYZ+p04sTkwHhUHJBbg+qpVzth2M+uxQXuq0\nUxAGbVgeQIyh0EB2yR34Atr0qQx4rC+YccKfRIMnSu17klbSaF6wIcAatmIVDOPD\n2VZr4QmbgyHd3wmTgHO/NHUCZjzHVpJssq2RIX3Q65gbdPHEz5f0KBbKrs5Saa65\nWbXB2pxRLmtP6bRwKnMoGPt8xRqiRAenP64a9gOK0eWjhJpGf0Zh1C/mtS0kgw+x\ng9W/bqgW9I4vSb1Ly9Q76v2CtPRvSmJCY3bgl3xisQKBgQDU6ka2Yhm3l1qON/RQ\nWQ6xOvNJyfg9H8+A+YLY3KyFa6TN4yHc68QYb+BtERKUygwgpk5UKWhUl2NSWYiE\nunYys6QOShcdf3FuVWJNGBmEJF5H9Hzn5vgrQfjKWkN1r3qHAgha4bcgp/1qBhUL\nP/n/Q9anbo8TZWSTADC5j5J/9QKBgQDJNMVzQDp2PhS+yz+8Sx6BLDEm4Qyc3I3c\nyYmKm9xg44+PFVd3ccN908VE6WioiJGpkK7OoaAEka5MPg2Y5VRBFkjaGOrIWgU/\nHbqkUePub1ErxyrTdrtp/aPZYSwJPfWEFopbeBl3+ap/kXm5JVqb1KFQqnUIWvdK\nshVgNrzbDQKBgQCCc5AjyvNq0yc+n/XnDMm9uRq7CS45dTYUFcwfxwVFMfDl3NYw\nn5ukRVfCO4Wg+DJ6BqtTUZOE0MSf/g9xEzW8VuibgLWs8xqyuUnjZnKrzgSeHaQy\nCgffqSogATH39y4hbhNka4tiTMstnNBj9izcQ9pO96ReA++dSa6Q4vClyQKBgQDD\n8BT8aCbGcSxopKt7pTeemTeAYhaTRyELSmQbzC5vWAu8Tg8wbWPvy+PGePqHbP9U\nvmXNKY4YBPpUmvVI2MMU4yus4Cj7VNbZIQ1Z6blqv5KvbDQjW/OkgvElxsBIe8L0\nj7LK4okC0eoccsGz8FFtgUJauLRhn5xEbGnumT+OnQKBgGjfQ7EZ0U0Xj5aoK+2I\nk76c0nyQIvcvIxlwEhDbAOpSkc9LcXDGYPuPj+bfjDEqNsinLXj3mGvG+vvBwQGJ\nOL7I1zaZW9FTEJdqrK/lxuef6XHzbjfq53zToIu4+0nifTz2X+gz4MkgEw3Sm3Bk\naP0wP7YK4VMVV+FYHHAx4Vmn\n-----END PRIVATE KEY-----\n",' >> gcs-serviceaccount.json
echo '  "client_email": "362316770119-compute@developer.gserviceaccount.com",' >> gcs-serviceaccount.json
echo '  "client_id": "104319498204088238656",' >> gcs-serviceaccount.json
echo '  "auth_uri": "https://accounts.google.com/o/oauth2/auth",' >> gcs-serviceaccount.json
echo '  "token_uri": "https://accounts.google.com/o/oauth2/token",' >> gcs-serviceaccount.json
echo '  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",' >> gcs-serviceaccount.json
echo '  "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/362316770119-compute%40developer.gserviceaccount.com"' >> gcs-serviceaccount.json
echo '}' >> gcs-serviceaccount.json


cd /mnt
mkdir gcs-deploy
gcsfuse -o allow_other --key-file /home/bp100a/gcs-serviceaccount.json ii_deploy /mnt/gcs-deploy

# For now Redis is being built here and run locally, that'll change
sudo apt-get --assume-yes install build-essential tcl

cd /home/bp100a
tar xvzf /mnt/gcs-deploy/redis-stable.tar.gz
cd redis-stable
make
make test
sudo make install

# Redis is built, now we need to install it, this will re-start on boot as well
PORT=6379
CONFIG_FILE=/etc/redis/6379.conf
LOG_FILE=/var/log/redis_6379.log
DATA_DIR=/var/lib/redis/6379
EXECUTABLE=/usr/local/bin/redis-server

echo -e \
"${PORT}\n${CONFIG_FILE}\n${LOG_FILE}\n${DATA_DIR}\n${EXECUTABLE}\n" | \
sudo utils/install_server.sh

# Now allow Redis to take connections on the intranet address for this server
# Note: This may change on reboot, might need to be part of startup
cd /etc/redis
sed -i "s/bind 127.0.0.1/bind `hostname -I` 127.0.0.1/g" 6379.conf
sed -i "s/protected-mode yes/protected-mode no/g" 6379.conf

# restart redis to pickup our config changes
sudo /etc/init.d/redis_6379 restart

# we connect to cloud SQL via a proxy
cd /home/bp100a
wget https://dl.google.com/cloudsql/cloud_sql_proxy.linux.amd64
mv cloud_sql_proxy.linux.amd64 cloud_sql_proxy
chmod +x cloud_sql_proxy

# Start Cloud SQL proxy
./cloud_sql_proxy -instances=$SQLINSTANCE=tcp:3306 &

# install Redis client tools
echo 'installing redis client tools'
apt-get install -y redis-tools

# now modify the rc.local file to start required services
echo "...modify rc.local for startup"
cd /etc
sed -i "s/exit 0//g" rc.local
echo -e "cd /home/bp100a" >> rc.local
echo -e "./cloud_sql_proxy -instances=$SQLINSTANCE=tcp:3306 &" >> rc.local
echo -e "cd /mnt" >> rc.local
echo -e "gcsfuse -o allow_other --key-file /home/bp100a/gcs-serviceaccount.json ii_deploy /mnt/gcs-deploy" >> rc.local
echo -e "\n" >> rc.local
echo -e "cd /home/bp100a/genesis/daemon" >> rc.local
echo -e "sudo python3 sync_leaderboard.py ip=127.0.0.1 port=$PORT &"
echo -e "\nexit 0" >> rc.local

# get our intranet IP address
export IPADDR=`hostname -I`

# log the server into the database so the iiServers can find it
# get the mysql client
sudo apt-get --assume-yes install mysql-client

echo -e "insert into serverlist (type, ipaddress, hostname) VALUES('Redis','"$IPADDR"', '`hostname`')" > active_server.sql

# now connect to our SQL server and let iiServers know we are here
echo "logging server in database"
mysql --host=127.0.0.1 --user=python --password=python imageimprov < active_server.sql

# launch the leaderboard synchronization script
cd /home/bp100a/genesis/daemon
echo "launching sync_leaderboard"
python3 sync_leaderboard.py ip=127.0.0.1 port=$PORT &

echo 'startup script DONE'
