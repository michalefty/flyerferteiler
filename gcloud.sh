#gcloud

gcloud compute instances create INSTANZ_NAME \
    --project=PROJEKT_ID \
    --zone=us-central1-a \
    --machine-type=e2-micro \
    --image-family=ubuntu-2204-lts \
    --image-project=ubuntu-os-cloud \
    --tags=http-server \
    --boot-disk-size=30GB



    gcloud compute firewall-rules create allow-http \
    --allow tcp:80 \
    --target-tags=http-server