"""Test container set/delete."""
import os, sys, tempfile, subprocess, textwrap

lib = r"C:\Users\taylorg\Documents\OpenWrt\package\vyoscli\files\usr\lib"
etc = tempfile.mkdtemp(prefix="vyoscli-ctr-")
cmds = textwrap.dedent("""\
configure
set container nginx image nginx:alpine
set container nginx network podman
set container nginx port 8080:80
set container nginx volume /etc/vyoscli/lists:/usr/share/nginx/html
set container nginx restart always
set container nginx environment TZ value Asia/Shanghai
set container nginx environment ENV value production
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
