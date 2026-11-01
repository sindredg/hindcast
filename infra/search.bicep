// The library's search service, deployed to the foundation's resource group
// with `az deployment group create` (decision 0019). Not part of the azd
// template: azd owns only the app's resource group. Microsoft.Search uses
// 2025-05-01, the newest stable version listed by `az provider show` on
// 2026-11-01.

@description('Search service name; globally unique, so it comes from the operator.')
param name string

// Sweden Central could not create new search services when the region was
// chosen; Switzerland North offers Basic and semantic ranking (decision 0004).
param location string = 'switzerlandnorth'

@description('Object ID of the user who builds and queries the index.')
param developerPrincipalId string

param tags object = {
  project: 'hindcast'
}

// Built-in role definition IDs, read with `az role definition list` on 2026-11-01.
var searchServiceContributorRoleId = '7ca78c08-252a-4471-8644-bb5ff32d4ba0'
var searchIndexDataContributorRoleId = '8ebe5a00-799e-43f5-93ac-243d3dce84a7'

resource search 'Microsoft.Search/searchServices@2025-05-01' = {
  name: name
  location: location
  tags: tags
  sku: {
    name: 'basic'
  }
  properties: {
    replicaCount: 1
    partitionCount: 1
    // Entra tokens only: every API key is refused, so the data roles below
    // are the only way in. The endpoint stays public; no IP rule (decision 0019).
    disableLocalAuth: true
    publicNetworkAccess: 'Enabled'
    semanticSearch: 'standard'
  }
}

// Index definitions: create, replace, delete.
resource serviceContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(search.id, developerPrincipalId, searchServiceContributorRoleId)
  scope: search
  properties: {
    principalId: developerPrincipalId
    principalType: 'User'
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      searchServiceContributorRoleId
    )
  }
}

// Documents: upload and query.
resource indexDataContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(search.id, developerPrincipalId, searchIndexDataContributorRoleId)
  scope: search
  properties: {
    principalId: developerPrincipalId
    principalType: 'User'
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      searchIndexDataContributorRoleId
    )
  }
}

output endpoint string = 'https://${search.name}.search.windows.net'
