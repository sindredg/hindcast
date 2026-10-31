// The image an existing container app runs, read in a deployment of its own.
// Read from app.bicep directly, the reference is circular: the template would
// read the resource it is about to update. A module boundary breaks the cycle;
// azd's own templates do the same.
param name string
param exists bool

resource app 'Microsoft.App/containerApps@2026-01-01' existing = if (exists) {
  name: name
}

// "!" because Bicep cannot see that the reference is set exactly when exists is true.
output image string = exists ? app!.properties.template.containers[0].image : ''
