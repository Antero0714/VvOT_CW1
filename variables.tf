variable "cloud_id" {
  type        = string
  description = "Yandex Cloud ID."
}

variable "folder_id" {
  type        = string
  description = "Yandex Cloud folder ID."
}

variable "bucket_name" {
  type        = string
  description = "Globally unique bucket name beginning with vvotNN-."

  validation {
    condition     = can(regex("^vvot[0-9]{2}-[a-z0-9]([a-z0-9.-]*[a-z0-9])?$", var.bucket_name)) && length(var.bucket_name) <= 63
    error_message = "Use a valid bucket name starting with vvotNN-, where NN is your two-digit student number."
  }
}
