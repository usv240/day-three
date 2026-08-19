param(
    [string]$ProjectId = "agentic-fleet-2026",
    [string]$Location = "us-central1",
    [string]$RuntimeServiceAccount = "sa-reason@agentic-fleet-2026.iam.gserviceaccount.com"
)

$ErrorActionPreference = "Stop"
$Gcloud = "gcloud.cmd"
$RoleId = "dayThreeMemoryBankOperator"
$RoleName = "projects/$ProjectId/roles/$RoleId"

$ErrorActionPreference = "Continue"
& $Gcloud iam roles describe $RoleId --project $ProjectId --format "value(name)" 2>$null | Out-Null
$RoleExists = $LASTEXITCODE -eq 0
$ErrorActionPreference = "Stop"

if (-not $RoleExists) {
    & $Gcloud iam roles create $RoleId `
        --project $ProjectId `
        --title "Day Three Memory Bank Operator" `
        --description "Create and exactly retrieve deidentified Day Three handoff memories." `
        --permissions "aiplatform.memories.create,aiplatform.memories.get,aiplatform.memories.list,aiplatform.memories.retrieve" `
        --stage GA `
        --quiet
}

& $Gcloud projects add-iam-policy-binding $ProjectId `
    --member "serviceAccount:$RuntimeServiceAccount" `
    --role $RoleName `
    --condition None `
    --quiet | Out-Null

$env:GOOGLE_CLOUD_PROJECT = $ProjectId
$env:REGION = $Location
python infra/seed_memory_bank.py
if ($LASTEXITCODE -ne 0) {
    throw "Memory Bank proof seeding failed with exit code $LASTEXITCODE."
}

Write-Output "Memory Bank IAM and deidentified proof memory are ready."
