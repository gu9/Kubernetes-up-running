#Initialize the cluster using the IP range for Flannel:
kubeadm init --pod-network-cidr=10.244.0.0/16

#Copy the kubeadmn join command that is in the output. We will need this later.
# run join command which you copy above to node only