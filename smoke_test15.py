import os, sys, tempfile, subprocess, textwrap
lib = r"C:\Users\taylorg\Documents\OpenWrt\package\vyoscli\files\usr\lib"
etc = tempfile.mkdtemp(prefix="vyoscli-conf-")
cmds = textwrap.dedent("""\
configure
set service smartdns enabled true
set service smartdns port 53
commit
exit
""")
env = os.environ.copy()
env["PYTHONPATH"] = lib
env["VYOSCLI_ETC"] = etc
p = subprocess.run([sys.executable, "-m", "vyoscli"],
                   input=cmds, capture_output=True, text=True, env=env, timeout=15)
print(p.stdout)
