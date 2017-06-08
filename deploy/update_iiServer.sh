sudo pkill -f /var/run/iiServer.pid
cd ~/genesis
sudo git pull
sudo gunicorn --bind 127.0.0.1:8081 --name iiServer --workers=5 --timeout 120 --log-file /var/log/iiServer/error.log --access-logfile /var/log/iiServer/access.log iiServer:app --pid /var/run/iiServer.pid &
echo "...started gunicorn on 127.0.0.1:8081"
