data "archive_file" "worker" {
  type        = "zip"
  source_dir  = "${path.module}/function"
  output_path = "${path.module}/archiver-function.zip"
  excludes    = ["__pycache__", "__pycache__/**"]
}

resource "yandex_function" "worker" {
  name               = "${local.prefix}archive-function"
  folder_id          = var.folder_id
  runtime            = "python312"
  entrypoint         = "main.handler"
  memory             = 256
  execution_timeout  = "600"
  service_account_id = yandex_iam_service_account.accounts["worker"].id
  user_hash          = data.archive_file.worker.output_base64sha256

  content {
    zip_filename = data.archive_file.worker.output_path
  }

  environment = {
    ARCHIVE_BUCKET        = yandex_storage_bucket.archives.bucket
    ARCHIVE_TABLE         = local.archive_table
    ARCHIVE_KEY_ATTRIBUTE = local.archive_key
    DOCUMENT_API_ENDPOINT = yandex_ydb_database_serverless.archives.document_api_endpoint
    STORAGE_API_ENDPOINT  = "https://storage.yandexcloud.net"
    CLOUD_REGION          = local.region
    WORKER_ACCESS_KEY_ID  = yandex_iam_service_account_static_access_key.worker.access_key
    WORKER_SECRET_KEY     = yandex_iam_service_account_static_access_key.worker.secret_key
  }
}

resource "yandex_function_iam_member" "trigger" {
  function_id = yandex_function.worker.id
  role        = "functions.functionInvoker"
  member      = "serviceAccount:${yandex_iam_service_account.accounts["trigger"].id}"
}

resource "yandex_function_trigger" "tasks" {
  name      = "${local.prefix}tasks-trigger"
  folder_id = var.folder_id

  message_queue {
    queue_id           = yandex_message_queue.tasks.arn
    service_account_id = yandex_iam_service_account.accounts["trigger"].id
    batch_size         = "1"
    batch_cutoff       = "0"
  }

  function {
    id                 = yandex_function.worker.id
    service_account_id = yandex_iam_service_account.accounts["trigger"].id
  }

  depends_on = [
    terraform_data.archives_table,
    yandex_function_iam_member.trigger,
    yandex_resourcemanager_folder_iam_member.roles["trigger-queue"],
  ]
}
