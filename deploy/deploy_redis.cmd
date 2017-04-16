:: Create an instance
gcloud compute instances create example-redis%1 --scopes storage-full,sql-admin --metadata startup-script-url=gs://ii_photos/deploy_redis.sh --boot-disk-size=20GB --description="Redis server" --image-family ubuntu-1604-lts --image-project ubuntu-os-cloud --tags http-server

