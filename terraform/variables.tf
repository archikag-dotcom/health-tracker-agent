variable "gcp_project_id" {
  description = "The Google Cloud Project ID where resources will be provisioned."
  type        = string
  default     = "health-tracker-agent-prod"
}

variable "gcp_region" {
  description = "The Google Cloud Region for Cloud Run and Storage."
  type        = string
  default     = "us-central1"
}
