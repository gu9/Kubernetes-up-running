ACR="acrgurpre1x"
RG="aks-sandbox-canada"
#Create a new Azure Container Registry
az acr create --resource-group $RG --name $ACR --sku Basic --admin-enabled true
az acr login --name acrgurpre1x.azurecr.io

#Build an Image and Push to ACR

#Clone the js-docker branch of the github repository:
git clone --branch js-docker https://github.com/linuxacademy/content-AZ-104-Microsoft-Azure-Administrator.git ./js-docker
cd js-docker/
#Build and push the image to Azure Container Registry using ACR Tasks and the Dockerfile provided (<IMAGE_NAME> can be anything you like e.g. js-docker:v1)
az acr build --image <IMAGE_NAME> --registry $ACR --file Dockerfile .