# VvOT_CW1

1. В файле terraform.tfvars для проверки необходимо изменить значения полей;

2. Выполнить команды:

terraform init
terraform validate

yc config profile list

export YC_TOKEN="$(yc iam create-token)"

(БЕЗ ВПН!)
terraform plan -out=deployment.tfplan

terraform apply deployment.tfplan


terraform output -raw api_url



API_URL="$(terraform output -raw api_url)"

python3 tests/smoke.py "$API_URL" --output demo.zip



python3 -m zipfile -l demo.zip



terraform state list
export YC_TOKEN="$(yc iam create-token)"
terraform destroy
terraform state list

(
на всякий случай
test -n "${YC_TOKEN:-}" && echo "задан" || echo "НЕ задан"
)
