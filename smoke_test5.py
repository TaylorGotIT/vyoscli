"""Test static route set/delete."""
import os, sys, tempfile, subprocess, textwrap

lib = r"C:\Users\taylorg\Documents\OpenWrt\package\vyoscli\files\usr\lib"
etc = tempfile.mkdtemp(prefix="vyoscli-route-")
cmds = textwrap.dedent("""\
configure
set protocols static route 10.0.0.0/8 next-hop 192.168.1.1
set protocols static route 172.16.0.0/12 interface eth1
show configuration
commit
delete protocols static route 10.0.0.0/8 next-hop 192.168.1.1
show configuration commands
commit
exit
""")
env = os.environ.copy()
env["PYTHONPATH"] = lib
env["VYOSCLI_ETC"] = etc
p = subprocess.run([sys.executable, "-m", "vyoscli"],
                   input=cmds, capture_output=True, text=True, env=env, timeout=15)
print(p.stdout)
print("--- stderr ---")
print(p.stderr)
print("--- running.json ---")
with open(os.path.join(etc, "running.json"), encoding="utf-8") as f:
    print(f.read())
