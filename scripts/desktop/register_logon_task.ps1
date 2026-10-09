# Windows タスクスケジューラに「ログオン時(2分待ってから)に出品ファイル作成を実行」するタスクを登録する。
# 使い方: PowerShell で  powershell -ExecutionPolicy Bypass -File scripts\desktop\register_logon_task.ps1
# 解除:   Unregister-ScheduledTask -TaskName "ShopeeDailyListing" -Confirm:$false
# ※ 作成者の環境では未テストです。登録後は「タスクスケジューラ」から「実行」で一度試してください。

$repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$taskName = "ShopeeDailyListing"

$cmd = "Set-Location '$repo'; " +
       "python scripts\desktop\should_run_today.py; " +
       "if (`$LASTEXITCODE -eq 0) { Get-Content scripts\desktop\daily_prompt.md -Raw | claude -p }"

$action  = New-ScheduledTaskAction -Execute "powershell.exe" `
           -Argument "-NoProfile -WindowStyle Minimized -Command `"$cmd`""
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$trigger.Delay = "PT2M"
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 2)

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Force
Write-Host "登録しました: $taskName (ログオン2分後に実行。本日分が作成済みならスキップ)"
