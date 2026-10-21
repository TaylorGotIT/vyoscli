import os, sys, tempfile, subprocess, textwrap
lib = r"C:\Users\taylorg\Documents\OpenWrt\package\vyoscli\files\usr\lib"
etc = tempfile.mkdtemp(prefix="vyoscli-tun-")
cmds = textwrap.dedent("""\
configure
set interfaces tunnel tun0 encapsulation gre
set interfaces tunnel tun0 local-ip 5.6.7.8
set interfaces tunnel tun0 remote-ip 1.2.3.4
set interfaces tunnel tun0 address 10.0.0.1/30
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
