// The library's search service (decisions 0004 and 0019). Same settings as
// the service built for milestone 3, plus a system identity for the Foundry
// IQ comparison's vectorizer (decision 0028).

// Sweden Central could not create new search services when the region was
// chosen; Switzerland North offers Basic and semantic ranking (decision 0004).
param location string
param tags object

// 2025-05-01 is the newest stable version `az provider show` listed on 2026-11-05.
resource search 'Microsoft.Search/searchServices@2025-05-01' = {
  name: 'srch-hindcast-${take(uniqueString(resourceGroup().id), 6)}'
  location: location
  tags: tags
  sku: { name: 'basic' }
  identity: { type: 'SystemAssigned' }
  properties: {
    replicaCount: 1
    partitionCount: 1
    // Entra tokens only: every API key is refused, so the data roles are the
    // only way in. The endpoint stays public; no IP rule (decision 0019).
    disableLocalAuth: true
    publicNetworkAccess: 'Enabled'
    semanticSearch: 'standard'
  }
}

output name string = search.name
output endpoint string = 'https://${search.name}.search.windows.net'
output principalId string = search.identity.principalId
