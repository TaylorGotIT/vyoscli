"""Test smartdns set/delete."""
import os, sys, tempfile, subprocess, textwrap

lib = r"C:\Users\taylorg\Documents\OpenWrt\package\vyoscli\files\usr\lib"
etc = tempfile.mkdtemp(prefix="vyoscli-sd-")
cmds = textwrap.dedent("""\
configure
set service smartdns enabled true
set service smartdns port 5333
set service smartdns forbid-aaaa true
set service smartdns server ali ip 223.5.5.5
set service smartdns server ali port 53
set service smartdns server ali type udp
set service smartdns server cf ip 1.1.1.1
set service smartdns server cf port 443
set service smartdns server cf type https
set service smartdns domain-set gfw domain google.com
set service smartdns domain-set gfw domain youtube.com
set service smartdns domain-rule use-cf domain-set gfw
set service smartdns domain-rule use-cf forward cf
set service smartdns address nas.lan ip 192.168.1.10
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
