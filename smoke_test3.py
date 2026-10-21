"""Direct unit-style test of ConfigStore commit/confirm/history/rollback."""
import os, sys, tempfile, shutil

etc = tempfile.mkdtemp(prefix="vyoscli-cfg-")
sys.path.insert(0, r"C:\Users\taylorg\Documents\OpenWrt\package\vyoscli\files\usr\lib")

from vyoscli.config import ConfigStore

s = ConfigStore(etc)
print("--- initial running ---")
print(s.render_set_commands())

# make a change
s.set_value(["system", "host-name"], "router-A")
s.set_value(["interfaces", "ethernet", "eth0", "address"], "203.0.113.1/24")
print("\n--- commit (no confirm) ---")
print(s.commit())

print("\n--- history after commit ---")
for ts, _ in s.list_history():
    print(" ", ts)

# change again, then rollback
s.set_value(["system", "host-name"], "router-B")
print("\n--- second change, host-name now:", s.get(["system","host-name"]))
print(s.commit())

print("\n--- rollback to previous snapshot ---")
snaps = s.list_history()
# snaps[0] is the latest (before second commit); snaps[1] is before first commit
print(s.rollback_to(snaps[1][0]))
print("\n--- host-name after rollback:", s.get(["system","host-name"]))
print("--- eth0 address after rollback:", s.get(["interfaces","ethernet","eth0","address"]))

shutil.rmtree(etc, ignore_errors=True)
