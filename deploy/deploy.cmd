:: Create an instance
gcloud compute instances create iiserver-instance%1 --scopes storage-full,sql-admin --metadata startup-script-url=gs://ii_photos/deploy_iiserver.sh --boot-disk-size=20GB --description="iiServer Python" --image-family ubuntu-1604-lts --image-project ubuntu-os-cloud --tags http-server

