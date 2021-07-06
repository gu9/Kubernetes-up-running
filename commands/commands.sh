
#Verify that all three of your nodes are listed. It will look something like this:
kubectl get nodes

kubectl get node --show-labels

kubectl run mywebserver --image=nginx

kubectl get pods
kubectl get pods --show-labels

kubectl exec -it mywebserver -- /bin/bash

kubectl delete pod mywebserver

kubectl delete deploy mywebserver

kubectl api-resources

kubectl explain deployements

kubectl explain pod.spec.containers
# A pod in kubernetes represents a group of one or more containers and some shared resources for those containers.

#Create a Pod from Nginx Image



kubectl run [NAME-OF-POD] --image=[IMAGE=NAME] --restart=Never



kubectl run nginx --image=nginx --restart=Never

kubectl get rs

kubectl delete rs kplabs-replicasets




#Create a Pod and Expose a Port



kubectl run nginx --image=nginx --port=80 --restart=Never



#Output the Manifest File



kubectl run nginx --image=nginx --port=80 --restart=Never --dry-run -o yaml

kubectl describe deploy deployment-nginx

kubectl rollout history deployement.v1.apps/deployement-nginx
kubectl rollout history deployement.v1.apps/deployement-nginx --revision 1

kubectl rollout undo deploy.v1.apps/aks-web-app-deployment --to-revision=1

kubectl get service
kubectl expose pod nginx --port 8080 --target-port 9080

#Create a service - Exposing Pod



kubectl expose pod nginx --name nginx-svc --port=80 --target-port=80



#Create a service - Expose Deployment



kubectl expose deployment nginx --name nginx-dep-svc --port=80 --target-port=8000



#Create a NodePort Service

kubectl expose deployment nginx --name nodeport-svc --port=80 --target-port=8000 --type=NodePort

helm install stable/nginx-ingress --name nginx-ingress --set controller.publishService.enabled=true

kubectl get pods -n kube-system

kubectl get serviceaccount

kubectl create namespace kpsingh

kubectl get secret -n kpsingh

kubectl create namespace teamcanada
kubectl get namespace

kubectl get sa default -o yaml
# inside pod run secrets directory you can see token

kubectl create sa kpsinghsa #currently this sa does not have any permission
kubectl get secret

kubectl run nginx-sa --image=nginx --serviceaccount="kpsingsa"

kubectl get nodes

kubectl label node node-1 disk=hdd

kubectl taint nodes node-1 key=value:NoSchedule
#replace the IP and Token in the below command based on your environment

curl -k https://IP-HERE:/api/v1/ --header "Authorization: Bearer $TOKEN"

kubectl config get-contexts
kubectl config get-contexts
kubectl config current-context
kubectl config use-context gcpcluster-k8s-1