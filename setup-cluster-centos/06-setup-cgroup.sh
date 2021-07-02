#Set the cgroup driver for Docker to systemd, reload systemd, then enable and start Docker:
sed -i '/^ExecStart/ s/$/ --exec-opt native.cgroupdriver=systemd/' /usr/lib/systemd/system/docker.service
systemctl daemon-reload
systemctl enable docker --now