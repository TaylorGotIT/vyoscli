import os, sys, tempfile, subprocess, textwrap
lib = r"C:\Users\taylorg\Documents\OpenWrt\package\vyoscli\files\usr\lib"
etc = tempfile.mkdtemp(prefix="vyoscli-fw-")
cmds = textwrap.dedent("""\
configure
set firewall zone lan network lan
set firewall zone lan input ACCEPT
set firewall zone lan output ACCEPT
set firewall zone lan forward ACCEPT
set firewall zone wan network wan
set firewall zone wan input DROP
set firewall zone wan output ACCEPT
set firewall zone wan forward DROP
set firewall forwarding default src lan dest wan
set firewall rule 100 name Allow-SSH
set firewall rule 100 src wan
set firewall rule 100 dest-port 22
set firewall rule 100 target ACCEPT
set interfaces wireguard wg0 address 10.0.0.1/24
set interfaces wireguard wg0 listen-port 51820
set interfaces wireguard wg0 private-key ABCDEFG
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
