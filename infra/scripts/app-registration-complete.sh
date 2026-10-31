#!/usr/bin/env bash
# azd postprovision hook: finish the app registration with values that exist
# only after provisioning: the app's URL (redirect URI) and the app identity's
# principal ID (the federated credential that replaces a client secret).
# Safe to run again.
set -euo pipefail

for name in AUTH_CLIENT_ID AUTH_TENANT_ID SERVICE_WEB_URI SERVICE_WEB_IDENTITY_PRINCIPAL_ID; do
  if [ -z "${!name:-}" ]; then
    echo "app-registration-complete: $name is not set in the azd environment" >&2
    exit 1
  fi
done

redirect="${SERVICE_WEB_URI}/.auth/login/aad/callback"
# The registration serves this one app, so its redirect list is exactly the
# app's current callback. A rebuilt environment gets a new domain, and the old
# callback goes instead of piling up.
current="$(az ad app show --id "$AUTH_CLIENT_ID" --query "join(' ', web.redirectUris)" -o tsv)"
if [ "$current" = "$redirect" ]; then
  redirect_state="present"
else
  az ad app update --id "$AUTH_CLIENT_ID" --web-redirect-uris "$redirect"
  redirect_state="set"
fi

# The platform signs in as the app by presenting the managed identity's token
# as a client assertion. Entra accepts it only through this credential: the
# subject is the identity's principal ID, the audience is the fixed exchange
# audience, the issuer is this tenant.
credential_name="container-app-identity"
parameters="$(printf '{"name":"%s","issuer":"https://login.microsoftonline.com/%s/v2.0","subject":"%s","audiences":["api://AzureADTokenExchange"]}' \
  "$credential_name" "$AUTH_TENANT_ID" "$SERVICE_WEB_IDENTITY_PRINCIPAL_ID")"
existing="$(az ad app federated-credential list --id "$AUTH_CLIENT_ID" \
  --query "[?name=='$credential_name'].id" -o tsv)"
if [ -z "$existing" ]; then
  az ad app federated-credential create --id "$AUTH_CLIENT_ID" --parameters "$parameters" > /dev/null
  credential_state="created"
else
  az ad app federated-credential update --id "$AUTH_CLIENT_ID" \
    --federated-credential-id "$existing" --parameters "$parameters" > /dev/null
  credential_state="updated"
fi

echo "redirect uri: $redirect_state"
echo "federated credential: $credential_state"
