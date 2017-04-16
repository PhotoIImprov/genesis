#
# iiServer creation script.
# -------------------------
# Author: HjC
#
# This script will initialize a GCE instance to run the ImageImprov
# Python application.


# Step #1
# update and get necessary tools installed
apt-get update
apt-get install python3.5
apt-get -y install python3-pip
apt-get install git

# We use GCSfuse to connection to the Google Storage bucket where all 
# the photos are, as well as some files we are going to need to complete
# installation

export GCSFUSE_REPO=gcsfuse-`lsb_release -c -s`
echo "deb http://packages.cloud.google.com/apt $GCSFUSE_REPO main" | tee /etc/apt/sources.list.d/gcsfuse.list
curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | apt-key add -
apt-get update
apt-get install gcsfuse

#*******************************************************************************
# THIS IS BAD!!! RIGHT NOW WE ARE USING OUR PASSWORD
cd /home/bp100a
git clone https://bp100a:Bars00mRegina@github.com/PhotoIImprov/genesis.git
#
#*******************************************************************************

# install all the modules we are going to need
pip3 install --upgrade pip
pip3 install -r /home/bp100a/genesis/requirements.txt

# this needs to be part of the startup so it's always there
/sbin/sysctl -w net.ipv4.tcp_keepalive_time=60 net.ipv4.tcp_keepalive_intvl=60 net.ipv4.tcp_keepalive_probes=5

# now mount our photo bucket! Note we use "allow_other" so that even though the root is mounting it, it will be accessible by all
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
mkdir gcs-photos
chmod +777 gcs-photos
gcsfuse -o allow_other --key-file /home/bp100a/gcs-serviceaccount.json ii_photos /mnt/gcs-photos

# For now Redis is being built here and run locally, that'll change
# apt-get install build-essential tcl

#cd /home/bp100a
#tar xvzf /mnt/gcs-photos/redis-stable.tar.gz
#cd redis-stable
#make
#make test
#sudo make install
#sudo mkdir /etc/redis
#sudo cp /home/bp100a/redis-stable/redis.conf /etc/redis
#sudo cp /mnt/gcs-photos/redis.service /etc/systemd/system
#sudo systemctl enable redis

# we connect to cloud SQL via a proxy
cd /home/bp100a
wget https://dl.google.com/cloudsql/cloud_sql_proxy.linux.amd64
mv cloud_sql_proxy.linux.amd64 cloud_sql_proxy
chmod +x cloud_sql_proxy

# Start Cloud SQL proxy
./cloud_sql_proxy -instances=imageimprov:us-east1:ii-metadata1=tcp:3306 &

# get our intranet IP address
export IPADDR=`hostname -I`

# get the mysql client
sudo apt-get --assume-yes install mysql-client

echo -e "insert into serverlist (type, ipaddress, hostname) VALUES('iiServer','"$IPADDR"', '`hostname`')" > active_server.sql
# now connect to our SQL server
mysql --host=127.0.0.1 --user=python --password=python imageimprov < active_server.sql
