!macro preInit
  ; Forcefully and silently terminate any lingering instances of Tilux or background Python processes before installation begins
  nsExec::Exec 'taskkill /F /IM "Tilux.exe" /T'
  nsExec::Exec 'taskkill /F /IM "python.exe" /T'
  nsExec::Exec 'taskkill /F /IM "cloudflared.exe" /T'
  nsExec::Exec 'taskkill /F /IM "electron.exe" /T'
  ClearErrors
!macroend

!macro customInit
  ; Also terminate in customInit before file extraction begins to prevent locked file errors
  nsExec::Exec 'taskkill /F /IM "Tilux.exe" /T'
  nsExec::Exec 'taskkill /F /IM "python.exe" /T'
  nsExec::Exec 'taskkill /F /IM "cloudflared.exe" /T'
  nsExec::Exec 'taskkill /F /IM "electron.exe" /T'
  ClearErrors
!macroend

!macro customUnInit
  ; Cleanly kill during uninstall
  nsExec::Exec 'taskkill /F /IM "Tilux.exe" /T'
  nsExec::Exec 'taskkill /F /IM "python.exe" /T'
  nsExec::Exec 'taskkill /F /IM "cloudflared.exe" /T'
  nsExec::Exec 'taskkill /F /IM "electron.exe" /T'
  ClearErrors
!macroend
