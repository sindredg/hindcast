#!/usr/bin/env bash
# azd preprovision hook: the Entra app registration the sign-in uses.
#
# Bicep cannot create an app registration without the preview Graph
# extension, so this script does, once, and hands its IDs to the Bicep
# parameters through the azd environment. Safe to run again: it finds the
# registration by display name and only fills in what is missing.
set -euo pipefail

APP_NAME="${HINDCAST_AUTH_APP_NAME:-hindcast-app}"

app_id="$(az ad app list --display-name "$APP_NAME" --query "[0].appId" -o tsv)"
if [ -z "$app_id" ]; then
  # Single tenant; ID tokens on, because the built-in authentication signs
  # users in with OpenID Connect.
  app_id="$(az ad app create --display-name "$APP_NAME" \
    --sign-in-audience AzureADMyOrg \
    --enable-id-token-issuance true \
    --query appId -o tsv)"
  state="created"
else
  state="found"
fi

# The Application ID URI is the audience the auth config accepts.
az ad app update --id "$app_id" --identifier-uris "api://$app_id"

# A registration needs a service principal in the tenant before it can sign
# anyone in. Creating one twice fails, so check first.
if ! az ad sp show --id "$app_id" > /dev/null 2>&1; then
  az ad sp create --id "$app_id" > /dev/null
fi

azd env set AUTH_CLIENT_ID "$app_id"
azd env set AUTH_TENANT_ID "$(az account show --query tenantId -o tsv)"
# The one account allowed through the auth config: whoever runs the deployment.
azd env set AUTH_ALLOWED_USER_OBJECT_ID "$(az ad signed-in-user show --query id -o tsv)"

echo "app registration: $APP_NAME ($state)"
