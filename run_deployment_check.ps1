$ErrorActionPreference = "Stop"

Write-Host "Running AfriSync Deployment Readiness Check..."
python check_deployment_readiness.py
Write-Host "Deployment readiness check completed."
