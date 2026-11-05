// Log Analytics and Application Insights. The workspace takes Entra tokens
// only; Application Insights keeps its connection string, which can write
// telemetry and read nothing, the one stored setting (decision 0011).

param location string
param tags object

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2026-03-01' = {
  name: 'log-hindcast'
  location: location
  tags: tags
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
    features: { disableLocalAuth: true }
  }
}

// 2020-02-02 is the newest stable version the provider lists for components.
resource applicationInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: 'appi-hindcast'
  location: location
  tags: tags
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalytics.id
    IngestionMode: 'LogAnalytics'
  }
}

output logAnalyticsName string = logAnalytics.name
output applicationInsightsName string = applicationInsights.name
