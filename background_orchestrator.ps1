# This script waits for the lock to be free, starts the backend, and triggers downloads
Write-Host "Waiting for PyTorch installation to finish..."
while ($true) {
    # If the lock directory exists, uv is still installing
    if (-not (Test-Path "C:\Users\91797\Documents\Dev\JS\Monorepo\Backend Monorepo\Backend\.venv\.lock")) {
        # Check if python is running the uv pip install command
        $proc = Get-Process -Name "uv" -ErrorAction SilentlyContinue
        if (-not $proc) {
            break
        }
    }
    Start-Sleep -Seconds 5
}

Write-Host "Starting backend API..."
Start-Process -FilePath "C:\Users\91797\Documents\Dev\JS\Monorepo\Backend Monorepo\Backend\.venv\Scripts\uv.exe" -ArgumentList "run dev" -WorkingDirectory "C:\Users\91797\Documents\Dev\JS\Monorepo\Backend Monorepo\Backend" -NoNewWindow

Write-Host "Starting download trigger script..."
& "C:\Users\91797\Documents\Dev\JS\Monorepo\Backend Monorepo\Backend\.venv\Scripts\python.exe" trigger_downloads.py
