// The Foundry resource, its project, the four model deployments, and the
// custom role the screens need (decisions 0012, 0014, 0018, 0021, 0028).
// Settings mirror the resource built by hand for milestones 1 to 5, read with
// `az cognitiveservices account show` on 2026-11-05.

param location string
param tags object

@description('Distinguishes the custom role\'s name, which is unique in the tenant.')
param environmentName string

var accountName = 'ais-hindcast-${take(uniqueString(resourceGroup().id), 6)}'

// Pinned versions with automatic upgrade off: a model that changes under a
// run changes the result (decision 0012). Capacity in thousands of tokens per
// minute; quota read with `az cognitiveservices usage list` on 2026-11-05.
var deployments = [
  { name: 'gpt-6-luna', format: 'OpenAI', version: '2026-09-22' }
  { name: 'gpt-6.1-sol', format: 'OpenAI', version: '2026-09-29' }
  { name: 'gpt-5.4-mini', format: 'OpenAI', version: '2026-03-17' }
  { name: 'text-embedding-3-large', format: 'OpenAI', version: '1' }
]

// 2026-09-01: the newest stable version Bicep 0.48.1 has types for (2026-11-01
// is listed by `az provider show` on 2026-11-05, BCP081 without types).
resource account 'Microsoft.CognitiveServices/accounts@2026-09-01' = {
  name: accountName
  location: location
  tags: tags
  kind: 'AIServices'
  sku: { name: 'S0' }
  identity: { type: 'SystemAssigned' }
  properties: {
    // The subdomain is the endpoint's host; Entra tokens need one.
    customSubDomainName: accountName
    // Entra tokens only: every key is refused.
    disableLocalAuth: true
    allowProjectManagement: true
    publicNetworkAccess: 'Enabled'
  }
}

resource project 'Microsoft.CognitiveServices/accounts/projects@2026-09-01' = {
  parent: account
  name: 'hindcast'
  location: location
  tags: tags
  identity: { type: 'SystemAssigned' }
  properties: {}
}

// One at a time: the service refuses concurrent deployment changes on one account.
@batchSize(1)
resource model 'Microsoft.CognitiveServices/accounts/deployments@2026-09-01' = [
  for d in deployments: {
    parent: account
    name: d.name
    sku: { name: 'GlobalStandard', capacity: 50 }
    properties: {
      model: { format: d.format, name: d.name, version: d.version }
      versionUpgradeOption: 'NoAutoUpgrade'
      raiPolicyName: 'Microsoft.DefaultV2'
    }
  }
]

// Prompt Shields and PII detection, and nothing else: no built-in role holds
// only these two data actions (docs/findings/safety.md).
resource safetyCaller 'Microsoft.Authorization/roleDefinitions@2022-04-01' = {
  name: guid(resourceGroup().id, 'hindcast-safety-caller')
  properties: {
    roleName: 'Hindcast Safety Caller (${environmentName})'
    description: 'Prompt Shields and PII detection on the Hindcast Foundry resource'
    type: 'CustomRole'
    assignableScopes: [resourceGroup().id]
    permissions: [
      {
        actions: []
        dataActions: [
          'Microsoft.CognitiveServices/accounts/ContentSafety/text:shieldprompt/action'
          'Microsoft.CognitiveServices/accounts/Language/analyze-text/action'
        ]
      }
    ]
  }
}

output accountName string = account.name
output projectName string = project.name
output safetyCallerRoleId string = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', safetyCaller.name)
// The resource endpoint serves embeddings, Prompt Shields, and PII detection;
// the project endpoint serves the agents and responses.
output resourceEndpoint string = 'https://${account.properties.customSubDomainName}.services.ai.azure.com/'
output projectEndpoint string = 'https://${account.properties.customSubDomainName}.services.ai.azure.com/api/projects/${project.name}'
