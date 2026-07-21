output "cloud_run_service_url" {
  description = "The public HTTPS URL of the deployed Health Tracker Agent Cloud Run service."
  value       = google_cloud_run_v2_service.health_tracker_service.uri
}

output "artifact_repository_uri" {
  description = "Artifact Registry Docker repository URI."
  value       = google_artifact_registry_repository.app_repo.id
}

output "vector_backup_bucket_name" {
  description = "Cloud Storage bucket name for vector store backups."
  value       = google_storage_bucket.vector_memory_backup.name
}
