import os, sys, tempfile, subprocess
lib = r"C:\Users\taylorg\Documents\OpenWrt\package\vyoscli\files\usr\lib"
etc = tempfile.mkdtemp(prefix="vyoscli-img-")
cmds = "show container image\nadd container image nginx:alpine\ndelete container image nginx:alpine\nexit\n"
env = os.environ.copy()
env["PYTHONPATH"] = lib
env["VYOSCLI_ETC"] = etc
p = subprocess.run([sys.executable, "-m", "vyoscli"],
                   input=cmds, capture_output=True, text=True, env=env, timeout=20)
print(p.stdout)
print("--- stderr ---")
print(p.stderr)
