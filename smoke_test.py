"""Smoke test: drive the CLI with piped commands against a temp ETC dir."""
import os, sys, tempfile, subprocess, textwrap

lib = r"C:\Users\taylorg\Documents\OpenWrt\package\vyoscli\files\usr\lib"
etc = tempfile.mkdtemp(prefix="vyoscli-test-")

cmds = textwrap.dedent("""\
show version
show interface
configure
set system host-name test-router
set interfaces ethernet eth0 address 203.0.113.10/24
set interfaces ethernet eth0 description Uplink
show configuration
commit
exit
show system
exit
""")

env = os.environ.copy()
env["PYTHONPATH"] = lib
env["VYOSCLI_ETC"] = etc

p = subprocess.run(
    [sys.executable, "-m", "vyoscli"],
    input=cmds, capture_output=True, text=True, env=env, timeout=30,
)
print("=== STDOUT ===")
print(p.stdout)
print("=== STDERR ===")
print(p.stderr)
print("=== running.json on disk ===")
with open(os.path.join(etc, "running.json"), encoding="utf-8") as f:
    print(f.read())
