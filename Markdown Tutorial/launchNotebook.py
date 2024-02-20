"""
A script for launching a Jupyter Notebook server so that .ipynb files
can be opened via the browser.

If it can't find the `notebook` module, it will first attempt to use pip to
upgrade `pip` and `wheel` and then install `notebook`, which should
install everything necessary to run a Jupyter Notebook server.

Please reach out to an instructor if you have any issues during the
installation process.

This script lists currently-running servers first, and if there are too
many, offers to shut down the old ones first. You can adjust the
threshold for how many servers is "too many" by editing the
`SHUTDOWN_PROMPT_THRESHOLD` variable.

The server it launches will shut itself down after a total of 120
minutes of idle time; The kernels will shut down after 75 minutes idle.
This should help prevent inactive servers from building up endlessly on
your computer :)

AUTHOR: Peter Mawhorter, Lyn Turbak

CHANGELOG:

## Version 1.0
* Minor reformatting from Lyn's 0.10.2
* Changes to debugging output.
* Removed quote-escaping which was causing problems after the move to
  list-of-strings based command-line construction.
* An optimistic version bump in preparation for sending to students.

# Version 0.10.2 (made by Lyn to Peter's 0.10.1)
* Update server/kernel timeouts in documentation at top of file
* Print version number
* targetNames needs to include .exe extension for Windows,
  no extension for Macs. e.g., target "jupyter-notebook" on Mac is
  "jupyter-notebook.exe" in Windows.
* print path using os.environ["PATH"], not subprocess.run("echo $PATH", ...),
  which doesn't work in Windows
* change jupyter_exec and opt to be *lists of strings* rather than *strings".
  + subprocess.run excepts either format, but for single strings, Windows is
    confused by executables with spaces like
      C:\\Program Files (x86)\\Thonny\\python.exe
    (because it thinks the exectuable is "C:\\Program" and that "Files" and
    "(x86)\\Thonny\\python.exe" are the first two arguments).
    No such confusion occurs when the format is lists of strings.
  + IMPORTANT: when commands are a *list of strings*, shell keyword arg
    *must* be False! (the default)
"""

import os
import sys
import subprocess
import urllib.parse
import sysconfig

__version__ = "1.0"
"""
Current version number.
"""

SHUTDOWN_PROMPT_THRESHOLD = 10
"""
If there are already more than this many Jupyter Notebook servers running
when attempting to launch a new one, prompt the user to as if they'd like
to shut them down. You can edit this value to set it higher or lower if
you want, but it must be an integer.
"""

print(f"Running launchNotebook version {__version__}")

try:
    import notebook # noqa F401
except Exception:
    # Jupyter isn't installed, so we'll try to install it
    print(
        "We couldn't find Jupyter Notebook on your system, so we'll try"
        " to install it first."
    )
    subprocess.check_call(
        [
            sys.executable, '-m', 'pip',
            'install', '--user', '--upgrade', 'pip', 'wheel'
        ]
    )
    subprocess.check_call(
        [
            sys.executable, '-m', 'pip',
            'install', '--user', 'notebook'
        ]
    )

# Find ALL scripts directories with 'jupyter' OR 'jupyter-notebook' in
# them, and add them to our PATH, since even running via python module
# import bounces to the shell PATH at some point T_T.
hits = set()
# Looking for one of these targets in packages
targetNames = set(
    [
        name + ext
        for name in ['jupyter', 'jupyter-notebook']
        for ext in [
            '', # Mac has no extension
            '.exe' # Windows has .exe extension
        ]
    ]
)


# Look for jupyter scripts in every possible script install dir
print("Looking for Jupyter script...")
look_in = set()
schemes_found = set()
for scheme in sysconfig.get_scheme_names():
    bindir = sysconfig.get_path('scripts', scheme)
    if bindir is not None and os.path.exists(bindir):
        look_in.add(bindir)
        schemes_found.add(scheme)

print(
    f"Found {len(look_in)} directories to search, from schemes:"
    f" {schemes_found}"
)

for bindir in look_in:
    print(f"Looking for Jupyter in '{bindir}':")
    matches = set(os.listdir(bindir)).intersection(targetNames)
    if len(matches) > 0:
        hits.add(bindir)
        print("  Found: " + ', '.join(matches))
    else:
        print("  No Jupyter scripts here.")

if len(hits) == 0:
    # If we can't find jupyter, try anyways because maybe it's elsewhere
    # on their PATH? But print a warning message...
    print(
        "Even after installing Jupyter Notebook, we can't figure out"
        " how to launch it. We're going to try anyways, but it will"
        " probably crash."
    )
else:
    # Add entries at the end of the PATH for all the Python script dirs
    # we found with 'jupyter' in them.
    path = os.environ["PATH"]
    print("Adding entries to PATH:")
    for bindir in hits:
        print('  ' + bindir)
        path += ":" + bindir
    os.environ["PATH"] = path

# Don't use subprocess.run with "echo $PATH" because in Windows 10
# this returns the string "$PATH" and not a string with path directories.
finalPath = os.environ["PATH"]

print("Your current PATH entries are:")
for entry in finalPath.split(':'):
    print('  ' + entry)

# This is how we'll launch jupyter...
# Put command, args, opts etc in a *list of strings*
# rather than *single string*
# so that spaces in program names like
#   C:\\Program Files (x86)\\Thonny\\python.exe
# don't cause an error in Windows in subprocess.run
jupyter_exec = [sys.executable, '-m', 'jupyter_core.command']

print(f"Running {jupyter_exec + ['notebook', 'list']}")

# Check for already-running servers:
result = subprocess.run(
    jupyter_exec + ['notebook', 'list'],
    # shell=True, # shell must be False (default) when command is a list
    capture_output=True,
    text=True
)

if result.stdout:
    print(result.stdout)

# Abort if jupyter is not installed
if result.returncode != 0:
    print(
        f"Jupyter Notebook server isn't working on your system (return"
        f" code {result.returncode}). You should ask an instructor for"
        f" help with this, or if you can, install Anaconda and use that"
        f" to open the notebook."
    )
    sys.exit(1)

if result.stdout and len(result.stdout.splitlines()) > 1:
    lines = result.stdout.splitlines()[1:]
    URLs = [line.split('::')[0].strip() for line in lines]
    print("One or more notebook servers are already active:")
    for url in URLs:
        print('  ' + url)

    # if there are TOO many servers running, prompt about whether to
    # close them all
    if len(URLs) > SHUTDOWN_PROMPT_THRESHOLD:
        print(
            "That's an awful lot of servers running. Did you know that"
            " you can use a single server to open multiple notebooks at"
            " once?"
        )
        choice = input(
            "Would you like to shut down ALL old servers before starting"
            " a new server? (y/n) "
        )
        if choice.lower() in ('y', "yes"):
            print(
                "Okay, we'll shut down ALL of the old servers for you"
                " now."
            )
            # Stop each previously-running notebook
            for url in URLs:
                port = url.split('//')[1].split('/')[0].split(':')[1]
                subprocess.run(
                    jupyter_exec + ['notebook', 'stop', port]
                    # shell=True,
                    # shell must be False (default) when command is a list
                )
        else:
            print(
                "Okay, we'll launch a new server without shutting down"
                " the old ones. You should eventually shut them down if"
                " you're not using them though."
            )
            # done with this if/else tree

# Find the "first" .ipynb file in the current directory, and use that as
# our default target
target = None
file_target = None
for f in sorted(os.listdir()):
    if f.endswith(".ipynb"):
        file_target = f
        target = os.path.abspath(f)
        break

if target:
    print(f"Opening '{os.path.split(target)[1]}' in a new notebook server.")
else:
    print("Launching a new notebook server.")

# Save current directory and go to home directory so that user will be
# able to find files in the notebook server
here = os.getcwd()
home = os.path.expanduser('~')

# Don't set home dir if target isn't inside it!
if (
    (target is None and here.startswith(home))
 or (target and target.startswith(home))
):
    root_dir = home
    if target is None and here.startswith(home):
        rel_target = here[len(home):].replace('\\', '/')
        if rel_target.startswith('/'):
            rel_target = rel_target[1:]
        default_url = "/tree/" + rel_target
    elif target is not None:
        rel_target = os.path.split(target)[0][len(home):].replace('\\', '/')
        if rel_target.startswith('/'):
            rel_target = rel_target[1:]
        default_url = "/tree/" + rel_target
    else:
        default_url = "/tree"
else:
    print(
        "Warning: your notebook file is outside your home directory, so"
        " this server will only be able to access files in the current"
        " folder or sub-folders."
    )
    root_dir = here
    default_url = "/tree"

# Note: escaping quotes would be bad since we're using the
# list-of-strings command-line approach

# For the default URL, we want to fully encode it as a URL
default_url = urllib.parse.quote(default_url)

opts = [
    # Make sure that we'll shut things down eventually since the notebook
    # process doesn't die with Thonny.
    "--NotebookApp.shutdown_no_activity_timeout=7200", # 120 minutes
    "--MappingKernelManager.cull_idle_timeout=4500", # 75 minutes
    # disable mathjax since it's potentially slow...
    "--no-mathjax",
    # prevent async io errors on Mac
    "--NotebookApp.kernel_manager_class="
    + "notebook.services.kernels.kernelmanager.AsyncMappingKernelManager"
]

# Only try fancy root directory stuff if there are no spaces in the
# folder name!
if (
    (not target or ' ' not in target)
and ' ' not in root_dir
and ' ' not in default_url
):
    opts += [
        # Set root directory
        f'--notebook-dir="{root_dir}"',
        # Set default URL to current folder
        f'--NotebookApp.default_url="{default_url}"'
    ]

# run with a target, or not if we couldn't find one
if target:
    args = jupyter_exec + ['notebook', target]
else:
    args = jupyter_exec + ['notebook']

print(f'Running:\n{args + opts}')
subprocess.run(
    args + opts
    # shell=True,
    # shell must be False (default) when command is a list
)
