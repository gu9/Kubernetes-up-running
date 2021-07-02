az aks create \
--resource-group aks-sandbox-canada \
--name Cluster01 \
--node-count 2 \
--generate-ssh-keys \
--node-vm-size Standard_B2s \
--enable-managed-identity

