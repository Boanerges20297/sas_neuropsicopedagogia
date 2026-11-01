# Release requests
The canonical source branch is main. Ordinary pushes never deploy.
The watcher only responds when the latest main commit CHANGES .release/request.json.
The requestId must be unique, and version fields must match release.json.
Do NOT create request.json until the production bootstrap is explicitly approved.
Example request:
    {"schemaVersion":1,"action":"release","requestId":"neuro-0.1.0-1-r1","versionName":"0.1.0","versionCode":1}
Releases are disabled until a separate, restricted runner and host gateway are installed.
Do not use GitHub Actions. Never place private data or credentials in the repo.
