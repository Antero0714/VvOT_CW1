locals {
  prefix        = "${split("-", var.bucket_name)[0]}-"
  region        = "ru-central1"
  archive_table = "archives"
  archive_key   = "key"

  accounts = {
    gateway = "gateway"
    trigger = "trigger"
    worker  = "archiver"
    queues  = "queue-admin"
  }

  roles = {
    gateway-queue   = { account = "gateway", role = "ymq.writer" }
    gateway-ydb     = { account = "gateway", role = "ydb.viewer" }
    gateway-storage = { account = "gateway", role = "storage.viewer" }
    trigger-queue   = { account = "trigger", role = "ymq.reader" }
    worker-ydb      = { account = "worker", role = "ydb.editor" }
    worker-storage  = { account = "worker", role = "storage.uploader" }
    queues-admin    = { account = "queues", role = "ymq.admin" }
  }
}

resource "yandex_iam_service_account" "accounts" {
  for_each  = local.accounts
  folder_id = var.folder_id
  name      = "${local.prefix}${each.value}"
}

resource "yandex_resourcemanager_folder_iam_member" "roles" {
  for_each  = local.roles
  folder_id = var.folder_id
  role      = each.value.role
  member    = "serviceAccount:${yandex_iam_service_account.accounts[each.value.account].id}"
}

resource "yandex_iam_service_account_static_access_key" "queues" {
  service_account_id = yandex_iam_service_account.accounts["queues"].id
  description        = "Terraform management of Message Queue resources."
  depends_on         = [yandex_resourcemanager_folder_iam_member.roles["queues-admin"]]
}

resource "yandex_iam_service_account_static_access_key" "worker" {
  service_account_id = yandex_iam_service_account.accounts["worker"].id
  description        = "Document API and Object Storage access for the archiver."
  depends_on = [
    yandex_resourcemanager_folder_iam_member.roles["worker-ydb"],
    yandex_resourcemanager_folder_iam_member.roles["worker-storage"],
  ]
}
