# Terraform IaC Configuration for Health Tracker Agent Infrastructure

terraform {
  required_version = ">= 1.3.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 4.50"
    }
  }
}

provider "google" {
  project = var.gcp_project_id
  region  = var.gcp_region
}

# 1. Google Cloud Secret Manager for API Keys
resource "google_secret_manager_secret" "gemini_api_key" {
  secret_id = "gemini-api-key"
  replication {
    automatic = true
  }
}

# 2. Google Cloud Storage Bucket for Vector Store Backups
resource "google_storage_bucket" "vector_memory_backup" {
  name          = "${var.gcp_project_id}-health-tracker-vector-backup"
  location      = var.gcp_region
  force_destroy = true

  uniform_bucket_level_access = true
}

# 3. Google Artifact Registry Repository
resource "google_artifact_registry_repository" "app_repo" {
  location      = var.gcp_region
  repository_id = "health-tracker-agent"
  description   = "Docker container repository for Health Tracker Agent"
  format        = "DOCKER"
}

# 4. Google Cloud Run v2 Service
resource "google_cloud_run_v2_service" "health_tracker_service" {
  name     = "health-tracker-agent-app"
  location = var.gcp_region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    containers {
      image = "${var.gcp_region}-docker.pkg.dev/${var.gcp_project_id}/${google_artifact_registry_repository.app_repo.repository_id}/app:latest"

      resources {
        limits = {
          cpu    = "2"
          memory = "2Gi"
        }
      }

      env {
        name = "GEMINI_API_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.gemini_api_key.secret_id
            version = "latest"
          }
        }
      }
    }
  }
}

# 5. IAM Policy for Cloud Run Unauthenticated Public Invocation
resource "google_cloud_run_v2_service_iam_member" "public_access" {
  project  = var.gcp_project_id
  location = var.gcp_region
  name     = google_cloud_run_v2_service.health_tracker_service.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
