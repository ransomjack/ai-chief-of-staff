#!/usr/bin/env bash
# One-time Azure setup for Chief of Staff. Run it in Azure Cloud Shell (Bash):
#   portal.azure.com -> the >_ icon at the top -> Bash
#   git clone https://github.com/ransomjack/ai-chief-of-staff && cd ai-chief-of-staff
#   bash scripts/azure_setup.sh
#
# It creates: a resource group, a storage account (tasks, reminders, the message queue),
# a Function App on the Flex Consumption plan (pay per use), a free-tier Speech resource
# (voice notes), and a Key Vault for every secret. The Function App reads secrets from
# Key Vault with its own managed identity, so no secret sits in app settings in plain text.
# Safe to re-run: Azure skips what already exists.
set -euo pipefail

LOC="${LOC:-centralindia}"
RG="${RG:-rg-chief-of-staff}"
SUFFIX="${SUFFIX:-$(az account show --query id -o tsv | tr -d '-' | cut -c1-6)}"
ST="stcos${SUFFIX}"
APP="func-cos-${SUFFIX}"
KV="kv-cos-${SUFFIX}"
SPEECH="speech-cos-${SUFFIX}"

if ! az functionapp list-flexconsumption-locations --query "[].name" -o tsv | grep -qx "$LOC"; then
  echo "Flex Consumption is not offered in $LOC. Re-run with LOC=<one of these>:"
  az functionapp list-flexconsumption-locations --query "[].name" -o tsv
  exit 1
fi

echo "== Resource group $RG in $LOC"
az group create -n "$RG" -l "$LOC" -o none

echo "== Storage $ST"
az storage account create -n "$ST" -g "$RG" -l "$LOC" --sku Standard_LRS \
  --min-tls-version TLS1_2 --allow-blob-public-access false -o none

echo "== Function App $APP (Python 3.12, Flex Consumption)"
if ! az resource show -g "$RG" -n "$APP" --resource-type Microsoft.Web/sites -o none 2>/dev/null; then
  az functionapp create -n "$APP" -g "$RG" --storage-account "$ST" \
    --flexconsumption-location "$LOC" --runtime python --runtime-version 3.12 -o none
else
  echo "   (already exists, skipping)"
fi
az functionapp identity assign -n "$APP" -g "$RG" -o none
PRINCIPAL=$(az functionapp identity show -n "$APP" -g "$RG" --query principalId -o tsv)

echo "== Speech $SPEECH (free tier)"
az cognitiveservices account create -n "$SPEECH" -g "$RG" -l "$LOC" --kind SpeechServices \
  --sku F0 --yes -o none || echo "   (free tier already used in this subscription? re-run with S0)"

echo "== Key Vault $KV"
az keyvault create -n "$KV" -g "$RG" -l "$LOC" --enable-rbac-authorization true -o none || true
KV_ID=$(az keyvault show -n "$KV" --query id -o tsv)
ME=$(az ad signed-in-user show --query id -o tsv)
az role assignment create --assignee "$ME" --role "Key Vault Secrets Officer" --scope "$KV_ID" -o none || true
az role assignment create --assignee-object-id "$PRINCIPAL" --assignee-principal-type ServicePrincipal \
  --role "Key Vault Secrets User" --scope "$KV_ID" -o none || true

echo "== Speech key into Key Vault"
SPEECH_KEY=$(az cognitiveservices account keys list -n "$SPEECH" -g "$RG" --query key1 -o tsv)
sleep 20  # role assignments take a moment to apply
az keyvault secret set --vault-name "$KV" -n speech-key --value "$SPEECH_KEY" -o none

ref() { echo "@Microsoft.KeyVault(VaultName=${KV};SecretName=$1)"; }

echo "== App settings (secrets are Key Vault references)"
az functionapp config appsettings set -n "$APP" -g "$RG" -o none --settings \
  OWNER_NAME="Abhinav" OWNER_TIMEZONE="Asia/Kolkata" \
  OWNER_WHATSAPP_NUMBER="$(ref owner-whatsapp-number)" \
  WHATSAPP_TOKEN="$(ref whatsapp-token)" \
  WHATSAPP_PHONE_NUMBER_ID="$(ref whatsapp-phone-number-id)" \
  WHATSAPP_APP_SECRET="$(ref whatsapp-app-secret)" \
  WHATSAPP_VERIFY_TOKEN="$(ref whatsapp-verify-token)" \
  ANTHROPIC_API_KEY="$(ref anthropic-api-key)" ANTHROPIC_MODEL="claude-sonnet-5-5" \
  SPEECH_KEY="$(ref speech-key)" SPEECH_REGION="$LOC" \
  GITHUB_OWNER="ransomjack" \
  WATCH_REPOS="ransomjack/ot-bulletin-newsletter,ransomjack/ot-bulletin-site,ransomjack/ai-soc-lab,ransomjack/ai-chief-of-staff"

cat <<EOF

Done. Names to keep:
  Resource group : $RG
  Function App   : $APP
  Key Vault      : $KV
  Webhook URL    : https://$(az resource show -g "$RG" -n "$APP" --resource-type Microsoft.Web/sites --query properties.defaultHostName -o tsv)/api/whatsapp

Next: add the secrets (docs/SETUP.md, step 4), e.g.
  az keyvault secret set --vault-name $KV -n whatsapp-token --value '<paste>'
Then set up deployment from GitHub (docs/SETUP.md, step 5).
EOF
