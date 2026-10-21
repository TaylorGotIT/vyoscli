import os, sys, tempfile, subprocess, textwrap
lib = r"C:\Users\taylorg\Documents\OpenWrt\package\vyoscli\files\usr\lib"
etc = tempfile.mkdtemp(prefix="vyoscli-dhcp-")
cmds = textwrap.dedent("""\
configure
set service dhcp lan start 192.168.1.100
set service dhcp lan end 192.168.1.200
set service dhcp lan lease 12h
set service dhcp lan dns 192.168.1.1
set service dhcp lan dns 223.5.5.5
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
