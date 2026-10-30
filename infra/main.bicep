// The app's Azure resources: one resource group of its own, so that `azd down`
// cannot reach the resources built earlier (Foundry, storage, Application
// Insights). Those are read by name from their resource group and never
// created here (decision 0016).
targetScope = 'subscription'

@minLength(1)
@maxLength(40)
@description('azd environment name. The resource group is rg-<environmentName>.')
param environmentName string

@description('Region for every resource in this template.')
param location string

@description('Resource group that holds the existing Application Insights and Log Analytics resources.')
param monitoringResourceGroup string = 'rg-hindcast'

@description('Existing Application Insights resource the app writes traces to.')
param applicationInsightsName string

@description('Existing Log Analytics workspace the environment sends console logs to.')
param logAnalyticsName string

@description('Application (client) ID of the Entra app registration the sign-in uses.')
param authClientId string

@description('Tenant that issues the sign-in tokens.')
param authTenantId string = tenant().tenantId

@description('Object ID of the one user allowed to open the app.')
param allowedUserObjectId string

@secure()
@description('Fallback only: a client secret for the sign-in when the federated credential does not work. Empty selects the federated credential.')
param authClientSecret string = ''

@description('Image the container app runs. The default is a public placeholder for the first provision, before CI has pushed the app image.')
param imageName string = 'mcr.microsoft.com/k8se/quickstart@sha256:d278e30de23a1b5b5f4c987e830dbd915f9fafc1e2e574022eadf7e7ce1c05fb'

@description('Set by azd: true when the container app already exists, so provision keeps its current image.')
param webExists bool = false

@description('GitHub repository whose main branch may push images, as owner/name.')
param githubRepository string = 'sindredg/hindcast'

var tags = { 'azd-env-name': environmentName }

// Newest version the Bicep linter accepts on 2026-10-30.
resource group 'Microsoft.Resources/resourceGroups@2025-04-01' = {
  name: 'rg-${environmentName}'
  location: location
  tags: tags
}

module app 'app.bicep' = {
  name: 'app'
  scope: group
  params: {
    location: location
    tags: tags
    monitoringResourceGroup: monitoringResourceGroup
    applicationInsightsName: applicationInsightsName
    logAnalyticsName: logAnalyticsName
    authClientId: authClientId
    authTenantId: authTenantId
    allowedUserObjectId: allowedUserObjectId
    authClientSecret: authClientSecret
    imageName: imageName
    webExists: webExists
    githubRepository: githubRepository
  }
}

// Outputs become azd environment values. The CI identity's client ID and the
// registry name go into the repository secrets by hand (deployment runbook).
output AZURE_RESOURCE_GROUP string = group.name
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = app.outputs.registryLoginServer
output AZURE_CONTAINER_REGISTRY_NAME string = app.outputs.registryName
output CI_IDENTITY_CLIENT_ID string = app.outputs.ciIdentityClientId
output SERVICE_WEB_IDENTITY_PRINCIPAL_ID string = app.outputs.appIdentityPrincipalId
output SERVICE_WEB_URI string = app.outputs.appUri
