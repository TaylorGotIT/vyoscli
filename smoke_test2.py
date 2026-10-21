"""Second smoke: delete, discard, edit/next, up."""
import os, sys, tempfile, subprocess, textwrap

lib = r"C:\Users\taylorg\Documents\OpenWrt\package\vyoscli\files\usr\lib"
etc = tempfile.mkdtemp(prefix="vyoscli-test2-")

cmds = textwrap.dedent("""\
configure
set interfaces ethernet eth0 address 198.51.100.5/24
set interfaces ethernet eth0 address 198.51.100.6/24
show configuration
delete interfaces ethernet eth0 address 198.51.100.6/24
show configuration
discard
show configuration
commit
exit
""")

env = os.environ.copy()
env["PYTHONPATH"] = lib
env["VYOSCLI_ETC"] = etc

p = subprocess.run([sys.executable, "-m", "vyoscli"],
                   input=cmds, capture_output=True, text=True, env=env, timeout=30)
print(p.stdout)
print("--- stderr ---")
print(p.stderr)
