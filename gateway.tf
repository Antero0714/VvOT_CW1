resource "yandex_api_gateway" "archives" {
  name      = "${local.prefix}archives-api"
  folder_id = var.folder_id

  spec = templatefile("${path.module}/openapi.yaml", {
    gateway_account_id = yandex_iam_service_account.accounts["gateway"].id
    folder_id          = var.folder_id
    tasks_queue_url    = yandex_message_queue.tasks.id
    database_path      = yandex_ydb_database_serverless.archives.database_path
    archive_table      = local.archive_table
    archive_key        = local.archive_key
    bucket_name        = yandex_storage_bucket.archives.bucket
  })

  depends_on = [
    terraform_data.archives_table,
    yandex_function_trigger.tasks,
    yandex_resourcemanager_folder_iam_member.roles["gateway-queue"],
    yandex_resourcemanager_folder_iam_member.roles["gateway-ydb"],
    yandex_resourcemanager_folder_iam_member.roles["gateway-storage"],
  ]
}

output "api_url" {
  description = "HTTPS URL on the API Gateway service domain."
  value       = "https://${yandex_api_gateway.archives.domain}"
}
