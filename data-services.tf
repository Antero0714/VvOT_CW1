resource "yandex_message_queue" "failed" {
  name                      = "${local.prefix}failed-tasks"
  region_id                 = local.region
  access_key                = yandex_iam_service_account_static_access_key.queues.access_key
  secret_key                = yandex_iam_service_account_static_access_key.queues.secret_key
  message_retention_seconds = 14 * 24 * 60 * 60
}

resource "yandex_message_queue" "tasks" {
  name                       = "${local.prefix}tasks"
  region_id                  = local.region
  access_key                 = yandex_iam_service_account_static_access_key.queues.access_key
  secret_key                 = yandex_iam_service_account_static_access_key.queues.secret_key
  visibility_timeout_seconds = 900
  receive_wait_time_seconds  = 20
  message_retention_seconds  = 24 * 60 * 60

  redrive_policy = jsonencode({
    deadLetterTargetArn = yandex_message_queue.failed.arn
    maxReceiveCount     = 1
  })
}

resource "yandex_storage_bucket" "archives" {
  bucket        = var.bucket_name
  folder_id     = var.folder_id
  max_size      = 10 * 1024 * 1024 * 1024
  force_destroy = true

  anonymous_access_flags {
    read        = false
    list        = false
    config_read = false
  }
}

resource "yandex_ydb_database_serverless" "archives" {
  name        = "${local.prefix}archives-db"
  folder_id   = var.folder_id
  location_id = local.region

  serverless_database {
    enable_throttling_rcu_limit = true
    throttling_rcu_limit        = 10
    storage_size_limit          = 1
  }
}

# The Document API endpoint becomes available after Terraform creates the database.
resource "terraform_data" "archives_table" {
  triggers_replace = [
    yandex_ydb_database_serverless.archives.id,
    local.archive_table,
    local.archive_key,
  ]

  provisioner "local-exec" {
    interpreter = ["bash", "-c"]
    working_dir = path.module
    command     = "python3 infra/create_table.py"
    environment = {
      DOCUMENT_API  = yandex_ydb_database_serverless.archives.document_api_endpoint
      TABLE_NAME    = local.archive_table
      KEY_ATTRIBUTE = local.archive_key
    }
  }
}
