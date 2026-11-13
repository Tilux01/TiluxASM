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

!macro customInstall
  ; Automatically allow Tilux, Python, and cloudflared in Windows Defender Firewall so it never prompts
  nsExec::Exec 'netsh advfirewall firewall add rule name="Tilux AI" dir=in action=allow program="$INSTDIR\Tilux.exe" enable=yes'
  nsExec::Exec 'netsh advfirewall firewall add rule name="Tilux Python" dir=in action=allow program="$INSTDIR\resources\backend\runtime\python.exe" enable=yes'
  nsExec::Exec 'netsh advfirewall firewall add rule name="Tilux Cloudflared" dir=in action=allow program="$INSTDIR\resources\backend\cloudflared.exe" enable=yes'
  nsExec::Exec 'netsh advfirewall firewall add rule name="Tilux Cloudflared Out" dir=out action=allow program="$INSTDIR\resources\backend\cloudflared.exe" enable=yes'
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

!macro customUnInstall
  ; Clean up firewall rules on uninstall
  nsExec::Exec 'netsh advfirewall firewall delete rule name="Tilux AI"'
  nsExec::Exec 'netsh advfirewall firewall delete rule name="Tilux Python"'
  nsExec::Exec 'netsh advfirewall firewall delete rule name="Tilux Cloudflared"'
  nsExec::Exec 'netsh advfirewall firewall delete rule name="Tilux Cloudflared Out"'
  ClearErrors
!macroend
