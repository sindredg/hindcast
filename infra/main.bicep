// The whole Hindcast environment in one resource group: Foundry and its model
// deployments, storage, monitoring, search, the registry, and the app, with
// every role (decision 0028). `azd up` builds it from empty; `azd down`
// removes all of it. The data comes from `python -m hindcast.load` afterwards.
targetScope = 'subscription'

@minLength(1)
@maxLength(40)
@description('azd environment name. The resource group is rg-<environmentName>; not "hindcast" or "hindcast-app", the groups built before this template.')
param environmentName string

@description('Region for every resource except search.')
param location string

// Sweden Central could not create new search services when the region was
// chosen; Switzerland North offers Basic and semantic ranking (decision 0004).
@description('Region for the search service.')
param searchLocation string = 'switzerlandnorth'

@description('Object ID of the operator, from azd\'s AZURE_PRINCIPAL_ID; empty skips the operator\'s roles.')
param principalId string = ''

@description('Application (client) ID of the Entra app registration the sign-in uses.')
param authClientId string

@description('Tenant that issues the sign-in tokens.')
param authTenantId string = tenant().tenantId

@description('Object ID of the one user allowed to open the app.')
param allowedUserObjectId string

@secure()
@description('Fallback only: a client secret for the sign-in when the federated credential does not work. Empty selects the federated credential.')
param authClientSecret string = ''

@description('Image the container app runs, from HINDCAST_IMAGE: a public placeholder until CI has pushed the app image, then the registry image. Every provision sets it.')
param imageName string

@description('Start of the OIDC subject GitHub issues for this repository, read by the pre-provision hook, for example repo:owner@1/name@2.')
param githubSubjectPrefix string

var tags = { 'azd-env-name': environmentName }
var libraryIndex = 'hindcast-library-1024'

// 2025-04-01: the newest stable version Bicep 0.49.2 has types for (2026-06-01
// is listed by `az provider show` on 2026-11-07, BCP081 without types).
resource group 'Microsoft.Resources/resourceGroups@2025-04-01' = {
  name: 'rg-${environmentName}'
  location: location
  tags: tags
}

module monitoring 'modules/monitoring.bicep' = {
  name: 'monitoring'
  scope: group
  params: { location: location, tags: tags }
}

module foundry 'modules/foundry.bicep' = {
  name: 'foundry'
  scope: group
  params: { location: location, tags: tags, environmentName: environmentName }
}

module storage 'modules/storage.bicep' = {
  name: 'storage'
  scope: group
  params: { location: location, tags: tags }
}

module search 'modules/search.bicep' = {
  name: 'search'
  scope: group
  params: { location: searchLocation, tags: tags }
}

// The settings hindcast.config reads, for the page and for the operator's
// commands: endpoints and names, never keys.
var settings = {
  HINDCAST_PROJECT_ENDPOINT: foundry.outputs.projectEndpoint
  HINDCAST_CHAT_DEPLOYMENT: 'gpt-6-luna'
  HINDCAST_COMPARE_DEPLOYMENT: 'gpt-6.1-sol'
  // Required by the model settings; the Foundry cloud evaluation's judge
  // deployment as in milestone 5. The page never calls it.
  HINDCAST_JUDGE_DEPLOYMENT: 'gpt-6.1-sol'
  HINDCAST_STORAGE_URL: storage.outputs.blobEndpoint
  HINDCAST_SEARCH_ENDPOINT: search.outputs.endpoint
  HINDCAST_SEARCH_INDEX: libraryIndex
  HINDCAST_EMBEDDING_ENDPOINT: foundry.outputs.resourceEndpoint
  HINDCAST_EMBEDDING_DEPLOYMENT: 'text-embedding-3-large'
  HINDCAST_EMBEDDING_DIMENSIONS: '1024'
  HINDCAST_SAFETY_ENDPOINT: foundry.outputs.resourceEndpoint
}

module app 'modules/app.bicep' = {
  name: 'app'
  scope: group
  params: {
    location: location
    tags: tags
    applicationInsightsName: monitoring.outputs.applicationInsightsName
    logAnalyticsName: monitoring.outputs.logAnalyticsName
    settings: settings
    authClientId: authClientId
    authTenantId: authTenantId
    allowedUserObjectId: allowedUserObjectId
    authClientSecret: authClientSecret
    imageName: imageName
    githubSubjectPrefix: githubSubjectPrefix
  }
}

module roles 'modules/roles.bicep' = {
  name: 'roles'
  scope: group
  params: {
    foundryAccountName: foundry.outputs.accountName
    foundryProjectName: foundry.outputs.projectName
    storageAccountName: storage.outputs.accountName
    searchName: search.outputs.name
    safetyCallerRoleId: foundry.outputs.safetyCallerRoleId
    appPrincipalId: app.outputs.appIdentityPrincipalId
    searchPrincipalId: search.outputs.principalId
    operatorPrincipalId: principalId
  }
}

// Outputs become azd environment values, which the load command and the
// operator's commands read through a settings file (deployment runbook). The
// CI identity's client ID and the registry name go into the repository's
// environment secrets by hand.
output AZURE_RESOURCE_GROUP string = group.name
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = app.outputs.registryLoginServer
output AZURE_CONTAINER_REGISTRY_NAME string = app.outputs.registryName
output CI_IDENTITY_CLIENT_ID string = app.outputs.ciIdentityClientId
output SERVICE_WEB_IDENTITY_PRINCIPAL_ID string = app.outputs.appIdentityPrincipalId
output SERVICE_WEB_URI string = app.outputs.appUri
output HINDCAST_PROJECT_ENDPOINT string = settings.HINDCAST_PROJECT_ENDPOINT
output HINDCAST_CHAT_DEPLOYMENT string = settings.HINDCAST_CHAT_DEPLOYMENT
output HINDCAST_COMPARE_DEPLOYMENT string = settings.HINDCAST_COMPARE_DEPLOYMENT
output HINDCAST_JUDGE_DEPLOYMENT string = settings.HINDCAST_JUDGE_DEPLOYMENT
output HINDCAST_STORAGE_URL string = settings.HINDCAST_STORAGE_URL
output HINDCAST_SEARCH_ENDPOINT string = settings.HINDCAST_SEARCH_ENDPOINT
output HINDCAST_SEARCH_INDEX string = settings.HINDCAST_SEARCH_INDEX
output HINDCAST_EMBEDDING_ENDPOINT string = settings.HINDCAST_EMBEDDING_ENDPOINT
output HINDCAST_EMBEDDING_DEPLOYMENT string = settings.HINDCAST_EMBEDDING_DEPLOYMENT
output HINDCAST_EMBEDDING_DIMENSIONS string = settings.HINDCAST_EMBEDDING_DIMENSIONS
output HINDCAST_SAFETY_ENDPOINT string = settings.HINDCAST_SAFETY_ENDPOINT
output APPLICATIONINSIGHTS_NAME string = monitoring.outputs.applicationInsightsName
