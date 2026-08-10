param(
    [string]$ProjectId = "agentic-fleet-2026",
    [string]$Location = "us-central1"
)

$ErrorActionPreference = "Stop"
$GatewayId = "day-three-ingress"

# Google documents regional endpoints as mandatory for Model Armor template operations.
gcloud config set api_endpoint_overrides/modelarmor "https://modelarmor.$Location.rep.googleapis.com/"
gcloud services enable modelarmor.googleapis.com networkservices.googleapis.com networksecurity.googleapis.com iap.googleapis.com --project $ProjectId --quiet

if (-not (gcloud model-armor templates describe day-three-agent-input --project $ProjectId --location $Location 2>$null)) {
    gcloud model-armor templates create day-three-agent-input --project=$ProjectId --location=$Location --pi-and-jailbreak-filter-settings-enforcement=enabled --pi-and-jailbreak-filter-settings-confidence-level=medium-and-above --malicious-uri-filter-settings-enforcement=enabled --basic-config-filter-enforcement=disabled --template-metadata-log-sanitize-operations --quiet
}

if (-not (gcloud model-armor templates describe day-three-agent-output --project $ProjectId --location $Location 2>$null)) {
    gcloud model-armor templates create day-three-agent-output --project=$ProjectId --location=$Location --pi-and-jailbreak-filter-settings-enforcement=enabled --pi-and-jailbreak-filter-settings-confidence-level=medium-and-above --malicious-uri-filter-settings-enforcement=enabled --basic-config-filter-enforcement=enabled --template-metadata-log-sanitize-operations --quiet
}

$AccessToken = gcloud auth print-access-token
$Headers = @{ Authorization = "Bearer $AccessToken"; "Content-Type" = "application/json" }
$GatewayUrl = "https://networkservices.googleapis.com/v1/projects/$ProjectId/locations/$Location/agentGateways/$GatewayId"
try {
    Invoke-RestMethod -Method Get -Uri $GatewayUrl -Headers $Headers | Out-Null
    Write-Output "exists: Agent Gateway $GatewayId"
} catch {
    if ($_.Exception.Response.StatusCode.value__ -ne 404) { throw }
    $Payload = @{ name = $GatewayId; protocols = @("MCP"); googleManaged = @{ governedAccessPath = "CLIENT_TO_AGENT" } } | ConvertTo-Json -Depth 5
    $CreateUrl = "https://networkservices.googleapis.com/v1/projects/$ProjectId/locations/$Location/agentGateways?agentGatewayId=$GatewayId"
    Invoke-RestMethod -Method Post -Uri $CreateUrl -Headers $Headers -Body $Payload | Out-Null
    Write-Output "submitted: Agent Gateway $GatewayId"
}

Write-Output "Next: python infra/deploy_runtimes.py"

