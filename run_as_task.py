# Ported from AutoHotKey script run_as_task
# https://www.autohotkey.com/boards/viewtopic.php?f=83&t=119710

import sys
import os
import platform
import zlib
import ctypes

def is_windows():
    """Check if the operating system is Windows."""
    return platform.system() == 'Windows'

def is_bundled():
    """Check if the script is running from a bundled executable."""
    return getattr(sys, 'frozen', False)

def compute_crc32(data):
    """Compute the CRC32 checksum of the given data.

    Args:
        data (str): The input data to compute the checksum for.

    Returns:
        int: The CRC32 checksum of the input data.
    """
    return zlib.crc32(data.encode('utf-16-le')) & 0xFFFFFFFF

def is_admin():
    """Check if the script is running with administrative privileges.

    Returns:
        bool: True if the script is running as an administrator, False otherwise.
    """
    if not is_windows():
        return os.getuid() == 0
    return ctypes.windll.shell32.IsUserAnAdmin() == 1

def get_script_path():
    """Get the absolute path of the script.

    Returns:
        str: The path of the script.
    """
    return sys.executable if is_bundled() else os.path.abspath(sys.argv[0])

def run_as_admin_nix():
    """Re-run the script with elevated privileges on Unix-like systems."""
    if is_admin():
        return

    try:
        import subprocess
        subprocess.check_call(['sudo', sys.executable] + sys.argv)
    except subprocess.CalledProcessError as e:
        print(f"Failed to run as root: {e}")
        sys.exit(1)

def run_as_admin_win():
    """Re-run the script with elevated privileges on Windows."""
    if is_admin():
        return

    ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)

def run_as_admin():
    """Re-run the script with elevated privileges based on the operating system."""
    return run_as_admin_win() if is_windows() else run_as_admin_nix()

class Task:
    """Represents a scheduled task in the Windows Task Scheduler."""

    def __init__(self, task):
        """Initialize a Task instance.

        Args:
            task (object): The Task object from the Task Scheduler.
        """
        self.task = task

    def run(self):
        """Run the scheduled task."""
        self.task.Run(0)

    # https://learn.microsoft.com/en-us/windows/win32/taskschd/taskfolder-registertask
    # https://stackoverflow.com/questions/62407093/adding-principal-runlevel-to-task-scheduler-on-python-using-win32com
    # https://holypython.com/how-to-schedule-tasks-with-py-files-python-manual-automated/
    # https://learn.microsoft.com/en-us/windows/win32/taskschd/logon-trigger-example--scripting-
    @staticmethod
    def build_task_def(task_def):
        """Build the task definition for the scheduled task.

        Args:
            task_def (object): The task definition object.

        Returns:
            object: The modified task definition object.
        """
        Principal = task_def.Principal
        # TASK_LOGON_INTERACTIVE_TOKEN
        Principal.LogonType = 3
        # TASK_RUNLEVEL_HIGHEST
        Principal.RunLevel = 1

        Settings = task_def.Settings
        Settings.Enabled = True
        # TASK_INSTANCES_PARALLEL
        Settings.MultipleInstances = 0
        Settings.StopIfGoingOnBatteries = False
        Settings.DisallowStartIfOnBatteries = False
        Settings.AllowHardTerminate = True
        Settings.AllowDemandStart = True
        Settings.ExecutionTimeLimit = 'PT0S'

        # TASK_ACTION_EXEC
        action = task_def.Actions.Create(0)
        action.Path = sys.executable
        action.Arguments = "" if is_bundled() else ' '.join(sys.argv)
        action.WorkingDirectory = os.path.dirname(get_script_path())

        return task_def

class Scheduler:
    """Represents the Task Scheduler service."""

    def __init__(self, sched):
        """Initialize a Scheduler instance.

        Args:
            sched (object): The Schedule.Service object from the Task Scheduler.
        """
        self.sched = sched
        sched.Connect()
        self.root = sched.GetFolder('\\')

    def get_task(self, task_name):
        """Get a task by name from the Task Scheduler.

        Args:
            task_name (str): The name of the task.

        Returns:
            Task: The Task object if found, None otherwise.
        """
        try:
            return Task(self.root.GetTask(task_name))
        except:
            return None

    def register(self, task_name):
        """Register a new task with the Task Scheduler.

        Args:
            task_name (str): The name of the task.
        """
        try:
            task = self.root.RegisterTaskDefinition(
                task_name,
                Task.build_task_def(self.sched.NewTask(0)),
                6,  # TASK_CREATE_OR_UPDATE
                None,
                None,
                3,  # TASK_LOGON_INTERACTIVE_TOKEN
            )
            self.add_read_and_exe_perm_to_local_service(task)
        except Exception as e:
            print('RegisterTaskDefinition', e)

    # https://www.reddit.com/r/PowerShell/comments/8wpua5/privilege_elevation_the_microsoft_way_admin/
    @staticmethod
    def add_read_and_exe_perm_to_local_service(task):
        """Add read and execute permissions to the Local Service account.

        Args:
            task (object): The Task object.
        """
        Sddl = task.GetSecurityDescriptor(0xF)
        Local_Service_x_perm = '(A;;0x1200a9;;;LS)'
        if Local_Service_x_perm not in Sddl:
            Sddl += Local_Service_x_perm
            task.SetSecurityDescriptor(Sddl, 0)

class TaskRunner:
    """Handles running and scheduling tasks."""

    def __init__(self):
        """Initialize a TaskRunner instance."""
        if not is_windows():
            raise Exception('Sorry. Windows only')

        from win32com.client import Dispatch
        self._task_name = ''
        self.sched = Scheduler(Dispatch('Schedule.Service.1'))

    def run(self):
        """Run or register the scheduled task."""
        task = self.sched.get_task(self.task_name)
        if not is_admin():
            if not task:
                run_as_admin()
            else:
                task.run()
            sys.exit(0)

        if not task:
            self.sched.register(self.task_name)

    @property
    def task_name(self):
        """Generate the task name based on script and system information.

        Returns:
            str: The generated task name.
        """
        if not self._task_name:
            cmd_line = self._cmd_line()
            path_crc = compute_crc32(cmd_line)
            script_name = os.path.basename(get_script_path()).split('.')[0]
            ptr_size = 64 if sys.maxsize > 2**32 else 32
            self._task_name = f"RunAsTask\\{script_name}_{ptr_size}@{path_crc:08X}"
        return self._task_name

    @staticmethod
    def _cmd_line():
        """Generate the command line for the script.

        Returns:
            str: The command line for the script.
        """
        rv = [sys.executable]
        if not is_bundled():
            rv.append(os.path.abspath(sys.argv[0]))
        return ' '.join(rv)

def run_as_task():
    """Run the script as a scheduled task."""
    TaskRunner().run()

if __name__ == '__main__':
    run_as_task()
    # Launch regedit without console window.
    # PS> pythonw run_as_task.py
    import subprocess
    subprocess.Popen(['regedit'], creationflags=subprocess.CREATE_NO_WINDOW)
