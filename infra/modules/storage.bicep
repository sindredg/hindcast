// Blob Storage: the captured sources, the extracts the index build checks
// against, the page's runtime files, and the page's runs (decision 0028).
// Entra tokens only, as the account built by hand for milestone 1.

param location string
param tags object

var containers = ['sources', 'extracted', 'runtime', 'runs']

// 2026-09-01 is the newest stable version `az provider show` listed on 2026-11-07.
resource account 'Microsoft.Storage/storageAccounts@2026-09-01' = {
  name: 'sthindcast${take(uniqueString(resourceGroup().id), 8)}'
  location: location
  tags: tags
  kind: 'StorageV2'
  sku: { name: 'Standard_LRS' }
  properties: {
    accessTier: 'Hot'
    allowSharedKeyAccess: false
    allowBlobPublicAccess: false
    allowCrossTenantReplication: false
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
  }
}

resource blobs 'Microsoft.Storage/storageAccounts/blobServices@2026-09-01' = {
  parent: account
  name: 'default'
}

resource container 'Microsoft.Storage/storageAccounts/blobServices/containers@2026-09-01' = [
  for name in containers: {
    parent: blobs
    name: name
    properties: { publicAccess: 'None' }
  }
]

output accountName string = account.name
output blobEndpoint string = account.properties.primaryEndpoints.blob
