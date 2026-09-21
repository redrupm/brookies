@description('Base name used to derive all resource names, e.g. "brookies".')
param appName string = 'brookies'

@description('Azure region for all resources.')
param location string = resourceGroup().location

@description('Static Web Apps SKU. Free covers everything the frontend needs.')
@allowed(['Free', 'Standard'])
param staticWebAppSku string = 'Free'

@description('GitHub repo URL to link the Static Web App for CI/CD (leave empty to configure the deployment source later).')
param repositoryUrl string = ''

@description('Branch to deploy from when repositoryUrl is set.')
param repositoryBranch string = 'main'

@description('Full backend container image, e.g. ghcr.io/<owner>/brookies-backend:latest. The GHCR package must be public (Package settings -> Change visibility) so Container Apps can pull it without registry credentials.')
param backendImage string

@description('Backend container CPU cores. Must be a combo Container Apps Consumption allows alongside backendMemory (2.0 cpu / 4Gi memory is a valid pairing).')
param backendCpu string = '2.0'

@description('Backend container memory.')
param backendMemory string = '4Gi'

@description('Max concurrent HTTP requests routed to one backend replica before scaling out an additional one.')
param backendConcurrentRequests int = 10

@description('Max backend replicas. Kept small since this is a personal-scale app and each replica loads the ML models into memory.')
param backendMaxReplicas int = 2

var staticWebAppName = '${appName}-web'
var logAnalyticsName = '${appName}-logs'
var containerAppEnvName = '${appName}-env'
var containerAppName = '${appName}-backend'

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: logAnalyticsName
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    // Keep the free daily ingestion cap tight; this app's logs are tiny.
    workspaceCapping: {
      dailyQuotaGb: 1
    }
    retentionInDays: 30
  }
}

resource containerAppEnv 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: containerAppEnvName
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalytics.listKeys().primarySharedKey
      }
    }
    // No workloadProfiles set -> the environment defaults to the Consumption
    // plan, which bills only for actual CPU/memory-seconds used and supports
    // scaling to zero. That's what keeps this backend near-free when idle.
  }
}

resource containerApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: containerAppName
  location: location
  properties: {
    managedEnvironmentId: containerAppEnv.id
    configuration: {
      ingress: {
        external: true
        targetPort: 8000
        transport: 'auto'
        allowInsecure: false
      }
    }
    template: {
      containers: [
        {
          name: 'backend'
          image: backendImage
          resources: {
            cpu: json(backendCpu)
            memory: backendMemory
          }
          env: [
            {
              name: 'PORT'
              value: '8000'
            }
          ]
          probes: [
            {
              type: 'Readiness'
              httpGet: {
                path: '/api/health'
                port: 8000
              }
              // Generous startup allowance: cold start has to load torch,
              // transformers, and the baked-in FinBERT weights into memory.
              initialDelaySeconds: 15
              periodSeconds: 10
              failureThreshold: 12
            }
          ]
        }
      ]
      scale: {
        minReplicas: 0
        maxReplicas: backendMaxReplicas
        rules: [
          {
            name: 'http-scale'
            http: {
              metadata: {
                concurrentRequests: string(backendConcurrentRequests)
              }
            }
          }
        ]
      }
    }
  }
}

resource staticWebApp 'Microsoft.Web/staticSites@2024-04-01' = {
  name: staticWebAppName
  location: location
  sku: {
    name: staticWebAppSku
    tier: staticWebAppSku
  }
  properties: {
    repositoryUrl: empty(repositoryUrl) ? null : repositoryUrl
    branch: empty(repositoryUrl) ? null : repositoryBranch
    buildProperties: {
      appLocation: 'frontend'
      outputLocation: 'dist'
    }
  }
}

output staticWebAppDefaultHostname string = staticWebApp.properties.defaultHostname
output staticWebAppName string = staticWebApp.name
output backendUrl string = 'https://${containerApp.properties.configuration.ingress.fqdn}'
output containerAppName string = containerApp.name
output containerAppEnvName string = containerAppEnv.name
