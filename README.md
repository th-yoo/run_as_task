# run\_as\_task
**run_as_task** is a Python package that allows scripts to escalate their privileges to Administrator (Local Service) on Windows, without requiring UAC approval. This project is a port of AHK [RunAsTask](https://www.autohotkey.com/boards/viewtopic.php?f=83&t=119710).

## Installation
```powershell
PS > pip install run_as_task
```

## Usage
Here is a basic example of how to use `run_as_task` to run the Windows Registry Editor (`regedit`) with escalated privileges:

```python
# regedit.py
from run_as_task import run_as_task
import subprocess

run_as_task()
subprocess.Popen(['regedit'], creationflags=subprocess.CREATE_NO_WINDOW)
```

### Important Notes
1. **First Run Setup**: When you run the script for the first time, `run_as_task` will register the script as a Windows Scheduled Task to allow for escalated execution. This initial setup will prompt you for UAC (User Account Control) permissions.

2. **Subsequent Runs**: After the initial setup, running the script again will not prompt for UAC. Instead, it will trigger the scheduled task to run with escalated privileges.

To execute the script, use the following command in PowerShell:
```powershell
PS > pythonw regedit.py
```

## License
This project is licensed under the MIT License. See the LICENSE file for details.

## Contact
For any questions or support, please reach out to me via [GitHub Issues](https://github.com/th-yoo/run_as_task/issues).
