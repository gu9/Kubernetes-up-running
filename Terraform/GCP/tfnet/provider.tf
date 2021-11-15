terraform {
  required_version = ">= 0.12"
}

provider "google" {
  alias  = "impersonated"
    scopes = [
    "https://www.googleapis.com/auth/cloud-platform",
    "https://www.googleapis.com/auth/userinfo.email",
  ]
}

data "google_service_account_access_token" "default" {
 provider = "google.impersonated"
 target_service_account = "admin-sa@rh-lab-327604.iam.gserviceaccount.com"
 scopes = ["userinfo-email", "cloud-platform"]
 lifetime = "300s"
}

provider "google"  {
  project = var.gcp_project
  access_token = data.google_service_account_access_token.default.access_token
}

