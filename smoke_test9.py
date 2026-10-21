import os, sys, tempfile, subprocess, textwrap
lib = r"C:\Users\taylorg\Documents\OpenWrt\package\vyoscli\files\usr\lib"
etc = tempfile.mkdtemp(prefix="vyoscli-wl-")
cmds = textwrap.dedent("""\
configure
set interfaces wireless wlan0 ssid MyHome
set interfaces wireless wlan0 channel 6
set interfaces wireless wlan0 hw-mode 11g
set interfaces wireless wlan0 security wpa2
set interfaces wireless wlan0 passphrase abcdefgh
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
