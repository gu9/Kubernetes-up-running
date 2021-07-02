sudo kubeadm init --pod-network-cidr=10.244.0.0/16

#  set up the local kubeconfig

mkdir -p $HOME/.kube
sudo cp -i /etc/kubernetes/admin.conf $HOME/.kube/config
sudo chown $(id -u):$(id -g) $HOME/.kube/config

#make note that the kubeadm init command printed a long kubeadm join command to the screen.
# You will need that kubeadm join command in the