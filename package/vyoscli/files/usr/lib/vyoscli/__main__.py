import sys
import os
import time
import json

from .cli import main
from .config import ConfigStore


def _rollback_wait(seconds: int, snapshot: str) -> None:
    """Background timer: sleep ``seconds``, then auto-rollback unless
    someone ran ``commit confirm`` (which deletes rollback.conf)."""
    time.sleep(seconds)
    etc = os.environ.get("VYOSCLI_ETC", "/etc/vyoscli")
    conf_path = os.path.join(etc, "rollback.conf")
    if not os.path.exists(conf_path):
        return  # already confirmed
    try:
        with open(conf_path, encoding="utf-8") as f:
            conf = json.load(f)
    except Exception:
        return
    if conf.get("pid") != os.getpid():
        return  # a newer timer took over
    ts = os.path.basename(snapshot)[:-5]
    store = ConfigStore(etc)
    msg = store.rollback_to(ts)
    with open("/tmp/vyoscli-rollback.log", "a", encoding="utf-8") as f:
        f.write(f"{time.ctime()} AUTO-ROLLBACK: {msg}\n")


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--rollback-wait" in args:
        i = args.index("--rollback-wait")
        _rollback_wait(int(args[i + 1]), args[i + 2])
    else:
        main()
