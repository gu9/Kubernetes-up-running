resource "google_compute_network" "vpc_network" {
  name                    = "managmentnet"
  auto_create_subnetworks = false
}

resource "google_compute_subnetwork" "subnet-us" {
  name          = "managmentsubnet-us"
  region        = "us-central1"
  network       = google_compute_network.vpc_network.name
  ip_cidr_range = "10.130.0.0/20"
}

# configure the firewall rule
resource "google_compute_firewall" "managmentnet-allow-http-ssh-rdp-icmp" {
  name    = "managementnet-allow-http-ssh-icmp"
  network = google_compute_network.vpc_network.name
  allow {
    protocol = "tcp"
    ports    = ["22", "80", "3389"]
  }
  allow {
    protocol = "icmp"
  }
}
