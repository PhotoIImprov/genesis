:: Create an instance
gcloud compute instances create iiserver-instance%1 --metadata startup-script-url=gs://ii_deploy/debian_iiserver.sh,endpoints-service-name=echo-api.endpoints.imageimprov.cloud.goog,endpoints-service-config-id=2017-04-20r1 --scopes storage-full,sql-admin --boot-disk-size=20GB --description="iiServer Python" --image-family debian-8 --image-project debian-cloud --tags http-server,https-server



