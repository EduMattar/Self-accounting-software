-- Update `projectFolder` to point at your clone of Self-accounting-software.
-- Save your virtual environment inside the project root (default: .venv).

set projectFolder to "/path/to/Self-accounting-software"
set venvDir to ".venv"
set activateScript to projectFolder & "/" & venvDir & "/bin/activate"
set launchCommand to "cd " & quoted form of projectFolder & " && " & \
    "source " & quoted form of activateScript & " && python -m app"

tell application "Terminal"
    activate
    do script launchCommand
end tell

return input
