import os, sys, tempfile, subprocess, textwrap
lib = r"C:\Users\taylorg\Documents\OpenWrt\package\vyoscli\files\usr\lib"
etc = tempfile.mkdtemp(prefix="vyoscli-ovpn-")
cmds = textwrap.dedent("""\
configure
set interfaces openvpn vtun0 mode server
set interfaces openvpn vtun0 proto udp
set interfaces openvpn vtun0 port 1194
set interfaces openvpn vtun0 dev tun
set interfaces openvpn vtun0 ca /etc/openvpn/ca.crt
set interfaces openvpn vtun0 cert /etc/openvpn/server.crt
set interfaces openvpn vtun0 key /etc/openvpn/server.key
set interfaces openvpn vtun0 dh /etc/openvpn/dh.pem
set interfaces openvpn vtun0 server 10.8.0.0 255.255.255.0
set interfaces openvpn vtun0 push "redirect-gateway def1"
set interfaces openvpn vtun0 push "dhcp-option DNS 192.168.1.1"
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
