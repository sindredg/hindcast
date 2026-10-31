// Everything inside the app's resource group. API versions are the newest
// stable ones listed by `az provider show` on 2026-10-30, except where a
// comment says otherwise. Microsoft.App uses 2026-01-01, the newest version
// Bicep 0.47/0.48 has types for: with 2026-07-01 it cannot check property
// names before deployment (BCP081).

param location string
param tags object
param monitoringResourceGroup string
param applicationInsightsName string
param logAnalyticsName string
param authClientId string
param authTenantId string
param allowedUserObjectId string
@secure()
param authClientSecret string
param imageName string
param githubSubjectPrefix string

// Built-in role definition IDs, read with `az role definition list` on 2026-10-30.
var acrPullRoleId = '7f951dda-4ed3-4680-a7ca-43fe172d538d'
var acrPushRoleId = '8311e382-0749-4cb8-b61a-304f252e45ec'

// The sign-in's client credential. Default: the app's managed identity, through
// a federated credential on the app registration (the post-provision hook
// creates it). The platform reads the identity's client ID from a container
// secret with this exact lowercase name; the value is an ID, not a credential.
// Fallback: a client secret, when the federated path fails (decision 0016).
var useClientSecret = !empty(authClientSecret)
var authSecretName = useClientSecret
  ? 'microsoft-provider-authentication-secret'
  : 'override-use-mi-fic-assertion-client-id'

// The image comes from the parameter on every provision, never from the
// running app: one source of truth, and the image switch is a provision, which
// also sets the port and the probes (azd deploy changes only the image). The
// public placeholder that fills the first provision listens on port 80 and has
// no health path, so the port and the probes follow the image: a revision
// whose probes never pass fails the deployment.
var placeholder = startsWith(imageName, 'mcr.microsoft.com/k8se/quickstart')
var appPort = placeholder ? 80 : 8501
var probes = placeholder ? [] : [
  { type: 'Liveness', httpGet: { path: '/_stcore/health', port: appPort }, initialDelaySeconds: 10, periodSeconds: 30 }
  { type: 'Readiness', httpGet: { path: '/_stcore/health', port: appPort }, initialDelaySeconds: 5, periodSeconds: 10 }
]

// Existing resources in the other resource group: read, never changed.
resource applicationInsights 'Microsoft.Insights/components@2020-02-02' existing = {
  name: applicationInsightsName
  scope: resourceGroup(monitoringResourceGroup)
}

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2026-03-01' existing = {
  name: logAnalyticsName
  scope: resourceGroup(monitoringResourceGroup)
}

// The app's identity: pulls the image, and later reaches Foundry and storage.
resource appIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2024-11-30' = {
  name: 'id-hindcast-app'
  location: location
  tags: tags
}

// The build's identity: the push job in this repository's "azure" deployment
// environment exchanges its OIDC token for it and pushes the image. No stored
// credential. A job in an environment presents the environment as its subject,
// not the branch; the environment's branch policy admits only main. The prefix
// carries the owner and repository IDs when the repository uses GitHub's
// immutable subjects, so the hook reads it from GitHub instead of building it.
resource ciIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2024-11-30' = {
  name: 'id-hindcast-ci'
  location: location
  tags: tags

  resource github 'federatedIdentityCredentials@2024-11-30' = {
    name: 'github-environment-azure'
    properties: {
      issuer: 'https://token.actions.githubusercontent.com'
      subject: '${githubSubjectPrefix}:environment:azure'
      audiences: ['api://AzureADTokenExchange']
    }
  }
}

// Basic has no private endpoints, and GitHub's runners push over the
// internet, so public network access stays on. Pulls and pushes need a role.
resource registry 'Microsoft.ContainerRegistry/registries@2025-11-01' = {
  name: 'crhindcast${take(uniqueString(resourceGroup().id), 6)}'
  location: location
  tags: tags
  sku: { name: 'Basic' }
  properties: {
    adminUserEnabled: false
    anonymousPullEnabled: false
    publicNetworkAccess: 'Enabled'
  }
}

resource acrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(registry.id, appIdentity.id, acrPullRoleId)
  scope: registry
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', acrPullRoleId)
    principalId: appIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource acrPush 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(registry.id, ciIdentity.id, acrPushRoleId)
  scope: registry
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', acrPushRoleId)
    principalId: ciIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

// Console logs go through a diagnostic setting (below), not a workspace key.
resource environment 'Microsoft.App/managedEnvironments@2026-01-01' = {
  name: 'cae-hindcast'
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: { destination: 'azure-monitor' }
    workloadProfiles: [{ name: 'Consumption', workloadProfileType: 'Consumption' }]
  }
}

// 2021-05-01-preview is the newest version the provider lists for diagnostic
// settings; the stable 2016-09-01 predates the Container Apps categories.
#disable-next-line use-recent-api-versions
resource environmentLogs 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: 'console-and-system-logs'
  scope: environment
  properties: {
    workspaceId: logAnalytics.id
    logs: [
      { category: 'ContainerAppConsoleLogs', enabled: true }
      { category: 'ContainerAppSystemLogs', enabled: true }
    ]
  }
}

// azd updates the image at deploy time. On a later provision the app already
// exists, and this reference keeps its image instead of resetting it to the
// imageName parameter (azd's "exists" pattern).
resource web 'Microsoft.App/containerApps@2026-01-01' = {
  name: 'ca-hindcast'
  location: location
  tags: union(tags, { 'azd-service-name': 'web' })
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${appIdentity.id}': {} }
  }
  properties: {
    environmentId: environment.id
    workloadProfileName: 'Consumption'
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: appPort
        transport: 'auto'
        allowInsecure: false
      }
      registries: [{ server: registry.properties.loginServer, identity: appIdentity.id }]
      secrets: [
        {
          name: authSecretName
          value: useClientSecret ? authClientSecret : appIdentity.properties.clientId
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'web'
          image: imageName
          resources: { cpu: json('0.5'), memory: '1Gi' }
          env: [
            // Configuration, not a credential: it can write telemetry and read
            // nothing (decision 0011).
            { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: applicationInsights.properties.ConnectionString }
            { name: 'HINDCAST_ENV', value: 'production' }
          ]
          probes: probes
        }
      ]
      // One replica at most: a Streamlit session lives on one container, and
      // there is no sticky routing. Zero when idle (decision 0009).
      scale: { minReplicas: 0, maxReplicas: 1 }
    }
  }
  dependsOn: [acrPull]
}

// Built-in authentication: every request without a session is redirected to
// Entra sign-in, except the platform's health probes. Only one user may enter.
resource auth 'Microsoft.App/containerApps/authConfigs@2026-01-01' = {
  parent: web
  name: 'current'
  properties: {
    platform: { enabled: true }
    globalValidation: {
      unauthenticatedClientAction: 'RedirectToLoginPage'
      redirectToProvider: 'azureactivedirectory'
      excludedPaths: ['/_stcore/health']
    }
    identityProviders: {
      azureActiveDirectory: {
        enabled: true
        registration: {
          clientId: authClientId
          #disable-next-line no-hardcoded-env-urls
          openIdIssuer: 'https://login.microsoftonline.com/${authTenantId}/v2.0'
          clientSecretSettingName: authSecretName
        }
        validation: {
          allowedAudiences: ['api://${authClientId}']
          defaultAuthorizationPolicy: {
            allowedPrincipals: { identities: [allowedUserObjectId] }
          }
        }
      }
    }
    login: { tokenStore: { enabled: false } }
  }
}

output registryLoginServer string = registry.properties.loginServer
output registryName string = registry.name
output ciIdentityClientId string = ciIdentity.properties.clientId
output appIdentityPrincipalId string = appIdentity.properties.principalId
output appUri string = 'https://${web.properties.configuration.ingress.fqdn}'
