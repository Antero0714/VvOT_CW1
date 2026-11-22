# VvOT_CW1
1. В файле terraform.tfvars для проверки необходимо изменить значения полей;
<br>
2. Выполнить команды:<br>
<br>
terraform init<br>
terraform validate<br>
<br>
yc config profile list<br>
<br>
export YC_TOKEN="$(yc iam create-token)"<br>
<br>
(БЕЗ ВПН!)<br>
terraform plan -out=deployment.tfplan<br>
<br>
terraform apply deployment.tfplan<br>
<br>
<br>
terraform output -raw api_url<br>
<br>
<br>
<br>
API_URL="$(terraform output -raw api_url)"<br>
<br>
python3 tests/smoke.py "$API_URL" --output demo.zip<br>
<br>
<br>
<br>
python3 -m zipfile -l demo.zip<br>
<br>
<br>
<br>
terraform state list<br>
export YC_TOKEN="$(yc iam create-token)"<br>
terraform destroy<br>
terraform state list<br>
<br>
(<br>
на всякий случай<br>
test -n "${YC_TOKEN:-}" && echo "задан" || echo "НЕ задан"<br>
)
