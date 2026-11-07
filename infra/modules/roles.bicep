// Every role assignment the environment needs except the registry's two,
// which app.bicep makes next to the registry, each next to the call it
// serves (decision 0028). Built-in role definition IDs read with
// `az role definition list --name <role>` on 2026-11-05.

param foundryAccountName string
param foundryProjectName string
param storageAccountName string
param searchName string
param safetyCallerRoleId string

@description('The app\'s managed identity.')
param appPrincipalId string

@description('The search service\'s identity, for the Foundry IQ comparison only.')
param searchPrincipalId string

@description('The operator who loads the data and runs the commands; empty skips their roles.')
param operatorPrincipalId string

var foundryUser = '53ca6127-db72-4b80-b1b0-d745d6d5456d'
var openAiUser = '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'
var cognitiveServicesUser = 'a97b65f3-24c7-4388-baec-2e87135dc908'
var searchIndexDataReader = '1407120a-92aa-4202-b7e9-c0e197c71c8f'
var searchIndexDataContributor = '8ebe5a00-799e-43f5-93ac-243d3dce84a7'
var searchServiceContributor = '7ca78c08-252a-4471-8644-bb5ff32d4ba0'
var blobDataReader = '2a2b9908-6ea1-4ae2-8e65-a410df84e7d1'
var blobDataContributor = 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'

resource account 'Microsoft.CognitiveServices/accounts@2026-09-01' existing = {
  name: foundryAccountName
}

resource project 'Microsoft.CognitiveServices/accounts/projects@2026-09-01' existing = {
  parent: account
  name: foundryProjectName
}

resource storage 'Microsoft.Storage/storageAccounts@2026-09-01' existing = {
  name: storageAccountName
}

resource runtimeContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2026-09-01' existing = {
  name: '${storageAccountName}/default/runtime'
}

resource runsContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2026-09-01' existing = {
  name: '${storageAccountName}/default/runs'
}

resource search 'Microsoft.Search/searchServices@2025-05-01' existing = {
  name: searchName
}

var hasOperator = !empty(operatorPrincipalId)

// The app: the agent and its responses, through the project.
resource appFoundryUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(project.id, appPrincipalId, foundryUser)
  scope: project
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', foundryUser)
    principalId: appPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// The app: Prompt Shields on every tool item and PII detection on every answer.
resource appSafety 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(account.id, appPrincipalId, safetyCallerRoleId)
  scope: account
  properties: {
    roleDefinitionId: safetyCallerRoleId
    principalId: appPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// The app: the embedding of each library search query, on the resource
// endpoint. Reaches every deployment on the resource (decision 0019).
resource appOpenAi 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(account.id, appPrincipalId, openAiUser)
  scope: account
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', openAiUser)
    principalId: appPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// The app: library searches and the chunk listing each run records.
resource appSearch 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(search.id, appPrincipalId, searchIndexDataReader)
  scope: search
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', searchIndexDataReader)
    principalId: appPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// The app: reads its runtime files, and nothing else in the account.
resource appRuntime 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(runtimeContainer.id, appPrincipalId, blobDataReader)
  scope: runtimeContainer
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', blobDataReader)
    principalId: appPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// The app: writes and reads back its runs and challenges.
resource appRuns 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(runsContainer.id, appPrincipalId, blobDataContributor)
  scope: runsContainer
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', blobDataContributor)
    principalId: appPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// The search service, for the Foundry IQ comparison only (decision 0028).
// Hindcast's own search embeds its queries in code and needs neither role.
// The knowledge base index's vectorizer embeds queries: the vectorizer page
// asks for Cognitive Services OpenAI User.
resource searchOpenAi 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(account.id, searchPrincipalId, openAiUser)
  scope: account
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', openAiUser)
    principalId: searchPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// The planning arm's knowledge base calls gpt-5.4-mini: the agentic retrieval
// overview asks for Cognitive Services User on the Foundry resource.
resource searchCognitiveUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(account.id, searchPrincipalId, cognitiveServicesUser)
  scope: account
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', cognitiveServicesUser)
    principalId: searchPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// The operator: the commands (investigate, challenge, index, load) as the
// developer's sign-in, the same set milestones 1 to 5 used.
var operatorRoles = [
  { scope: 'project', role: foundryUser }
  { scope: 'account', role: openAiUser }
  { scope: 'storage', role: blobDataContributor }
  { scope: 'search', role: searchServiceContributor }
  { scope: 'search', role: searchIndexDataContributor }
]

resource operatorProject 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for r in filter(operatorRoles, r => r.scope == 'project'): if (hasOperator) {
    name: guid(project.id, operatorPrincipalId, r.role)
    scope: project
    properties: {
      roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', r.role)
      principalId: operatorPrincipalId
      principalType: 'User'
    }
  }
]

resource operatorAccount 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for r in filter(operatorRoles, r => r.scope == 'account'): if (hasOperator) {
    name: guid(account.id, operatorPrincipalId, r.role)
    scope: account
    properties: {
      roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', r.role)
      principalId: operatorPrincipalId
      principalType: 'User'
    }
  }
]

resource operatorSafety 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (hasOperator) {
  name: guid(account.id, operatorPrincipalId, safetyCallerRoleId)
  scope: account
  properties: {
    roleDefinitionId: safetyCallerRoleId
    principalId: operatorPrincipalId
    principalType: 'User'
  }
}

resource operatorStorage 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for r in filter(operatorRoles, r => r.scope == 'storage'): if (hasOperator) {
    name: guid(storage.id, operatorPrincipalId, r.role)
    scope: storage
    properties: {
      roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', r.role)
      principalId: operatorPrincipalId
      principalType: 'User'
    }
  }
]

resource operatorSearch 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for r in filter(operatorRoles, r => r.scope == 'search'): if (hasOperator) {
    name: guid(search.id, operatorPrincipalId, r.role)
    scope: search
    properties: {
      roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', r.role)
      principalId: operatorPrincipalId
      principalType: 'User'
    }
  }
]
