"""vyoscli: a VyOS-style CLI for OpenWrt.

Modes:
  operational  -> prompt  user@host:~$
  configure    -> prompt  user@host#  (followed by current node path)

Commands:
  op:      configure | show version|system|interface | ping <host> | exit
  cfg:     set <path> <value> | delete <path> | edit <path> |
           commit | discard | save | show | up | next | exit
"""

from __future__ import annotations

import os
import sys
import json
import shlex
from typing import List, Optional

try:
    import readline  # type: ignore
    _HAVE_READLINE = True
except ImportError:  # Windows / minimal python3 without readline
    readline = None  # type: ignore
    _HAVE_READLINE = False

from .config import ConfigStore
from .tree import CommandTree, Node, VALUE_TYPES, coerce_value, validate_value
from . import commands as builtin


class Context:
    """Per-session state passed to command actions."""

    def __init__(self, store: ConfigStore, tree: CommandTree) -> None:
        self.store = store
        self.tree = tree
        self.mode: str = "op"           # "op" | "cfg"
        self.cfg_path: List[str] = []   # current sub-config node (VyOS "edit" stack)
        self._cli: Optional["Cli"] = None

    def bind(self, cli: "Cli") -> None:
        self._cli = cli

    def enter_configure(self) -> str:
        self.mode = "cfg"
        self.cfg_path = []
        return ""

    def quit(self) -> str:
        if self.mode == "cfg" and self.store.modified():
            ans = input("Uncommitted changes exist. Quit anyway? [y/N] ").strip().lower()
            if ans != "y":
                return ""
        if self._cli:
            self._cli.running = False
        return ""


class Cli:
    def __init__(self, store_dir: str = "/etc/vyoscli") -> None:
        self.store = ConfigStore(store_dir)
        self.tree = builtin.build_tree(self.store)
        self.ctx = Context(self.store, self.tree)
        self.ctx.bind(self)
        self.running = True
        self._setup_readline()

    # ------------ readline / completion ------------
    def _setup_readline(self) -> None:
        if not _HAVE_READLINE:
            return
        self._hist_path = os.path.expanduser("~/.vyoscli_history")
        try:
            readline.read_history_file(self._hist_path)
        except Exception:
            pass
        readline.set_history_length(1000)
        readline.set_completer(self._completer)
        readline.parse_and_bind("tab: complete")
        readline.parse_and_bind("set show-all-if-ambiguous on")
        readline.set_completer_delims(" \t\n")
        readline.set_completion_display_matches_hook(self._display_matches)

    def _save_history(self) -> None:
        if not _HAVE_READLINE:
            return
        try:
            readline.write_history_file(self._hist_path)
        except Exception:
            pass

    def postloop(self) -> None:
        self._save_history()

    def _completer(self, text: str, state: int) -> Optional[str]:
        if not _HAVE_READLINE:
            return None
        buf = readline.get_line_buffer()
        tokens = buf.split()
        if buf.endswith(" "):
            tokens.append("")
        matches = self._matches_with_help(tokens)
        names = [n for n, _ in matches]
        filtered = [n for n in names if n.startswith(text)]
        if state >= len(filtered):
            return None
        # if unique match and it's a leaf, append space
        if len(filtered) == 1:
            name = filtered[0]
            # check if this node has children (not a leaf)
            help_map = dict(matches)
            # if help is a value hint or <Enter>, it's a leaf -> add space
            if help_map.get(name) in ("value", "") or name.startswith("<") or name == "<Enter>":
                return name + " "
        return filtered[state]

    def _matches_with_help(self, tokens: List[str]) -> List[tuple]:
        """Return [(name, help), ...] for the next token in current context."""
        if not tokens:
            return []
        if self.ctx.mode == "op":
            root = self.tree.op_root
            head = tokens[:-1]
        else:
            root = self.tree.cfg_root
            head = tokens[:-1]
            # Inside `edit`, the buffer has no node path: "set host-name x"
            # must be resolved as "set <cfg_path> host-name x".
            if (self.ctx.cfg_path and head
                    and head[0] in ("set", "delete", "edit", "next")):
                head = [head[0]] + self.ctx.cfg_path + head[1:]

        node, _rem, _matched, _canon = root.walk(head)
        out: List[tuple] = []
        for child_name, child in node.children.items():
            out.append((child_name, child.help or ""))
        if node.dynamic is not None and callable(node.dynamic):
            tpl = getattr(node, "_dyn_template", None)
            tpl_help = (tpl.help if tpl is not None else "") or "(dynamic)"
            for dyn in node.dynamic():
                out.append((dyn, tpl_help))
        if node.value_type and not node.children:
            hint = VALUE_TYPES.get(node.value_type, "<value>")
            out.append((hint, "value"))
        # If current node is already a runnable leaf, suggest <Enter>.
        if node.action is not None and not node.children:
            out.append(("<Enter>", "Execute the current command"))
        return out

    def _display_matches(self, _subst: str, matches: List[str],
                         _longest: int) -> None:
        """readline hook: render matches two-column (name + help), VyOS style."""
        if not matches:
            return
        buf = readline.get_line_buffer()
        tokens = buf.split()
        if buf.endswith(" "):
            tokens.append("")
        help_map = dict(self._matches_with_help(tokens))
        print()
        width = max(len(m) for m in matches)
        for m in matches:
            print(f"  {m.ljust(width + 2)}{help_map.get(m, '')}")
        sys.stdout.write(self._prompt() + buf)
        sys.stdout.flush()

    # ------------ prompt ------------
    def _prompt(self) -> str:
        host = self.store.get(["system", "host-name"], candidate=False) or "OpenWrt"
        if self.ctx.mode == "op":
            return f"root@{host}:~$ "
        path = " ".join(self.ctx.cfg_path)
        suffix = f" [{path}]" if path else ""
        return f"root@{host}# {suffix}"

    def _suggest(self, word: str, candidates: list) -> str:
        """Simple typo suggestion: find closest match by edit distance."""
        if not word or not candidates:
            return ""
        best = None
        best_dist = 999
        for c in candidates:
            # simple: common prefix length
            prefix_len = 0
            for a, b in zip(word, c):
                if a == b:
                    prefix_len += 1
                else:
                    break
            dist = len(word) + len(c) - 2 * prefix_len
            if dist < best_dist:
                best_dist = dist
                best = c
        if best and best_dist <= max(3, len(word) // 2):
            return f"  (did you mean: {best}?)"
        return ""

    # ------------ command dispatch ------------
    def _run_op(self, tokens: List[str]) -> str:
        node, remaining, _matched, _canon = self.tree.op_root.walk(tokens)
        # fully matched node with action?
        if node.action is not None and not remaining:
            return node.action(self.ctx, None)
        # value-bearing leaf
        if node.action is not None and node.value_type and remaining:
            return node.action(self.ctx, " ".join(remaining))
        # maybe the action lives one level deeper but user gave extra tokens
        if node.action is not None:
            return node.action(self.ctx, " ".join(remaining) or None)
        # pass-through to system shell (ping/nslookup/ls/...)
        import subprocess
        try:
            r = subprocess.run(tokens, capture_output=True, text=True, timeout=30)
            out = r.stdout
            if r.stderr:
                out += r.stderr
            return out or f"Command exited {r.returncode}"
        except FileNotFoundError:
            # suggest closest match
            top = list(self.tree.op_root.children.keys())
            sug = self._suggest(tokens[0], top)
            return f"Invalid command: {' '.join(tokens)} (try '?'){sug}"
        except Exception as e:
            return f"Command error: {e}"

    def _run_cfg(self, tokens: List[str]) -> str:
        if not tokens:
            return ""
        head, *rest = tokens

        # run <op-command>: execute op-mode command from config mode
        if head == "run":
            return self._run_op(rest)

        # top-level verbs
        if head == "sync":
            return self.store.sync()
        if head == "commit":
            # variants: commit | commit confirm | commit confirmed [minutes]
            if rest and rest[0] == "confirm":
                return self.store.confirm()
            minutes = 0
            if rest and rest[0] == "confirmed":
                try:
                    minutes = int(rest[1]) if len(rest) > 1 else 5
                except ValueError:
                    return "commit confirmed: expected minutes, e.g. 'commit confirmed 5'"
            return self.store.commit(confirmed_minutes=minutes)
        if head == "rollback":
            ts = rest[0] if rest else None
            return self.store.rollback_to(ts)
        if head == "discard":
            return self.store.discard()
        if head == "compare":
            return self.store.compare()
        if head == "save":
            return self.store.save()
        if head == "up":
            if self.ctx.cfg_path:
                self.ctx.cfg_path.pop()
            return ""
        if head == "exit":
            if self.ctx.cfg_path:
                self.ctx.cfg_path.pop()
            else:
                self.ctx.mode = "op"
            return ""
        if head == "next" or head == "edit":
            # Resolve to canonical node names so "edit syst" really lands on
            # "system" and later "set" sub-commands compose with it.
            node, remaining, _matched, canon = self.tree.cfg_root.walk(
                ["set"] + self.ctx.cfg_path + rest)
            if remaining:
                return f"edit: no such node: {' '.join(remaining)}"
            self.ctx.cfg_path = canon[1:]
            return ""
        if head == "show":
            rest2 = rest
            sub = rest2[1] if len(rest2) > 1 else ""
            kind = rest2[0] if rest2 else ""
            if kind in ("", "configuration", "config", "cfg"):
                # show configuration [commands|json|all]
                if sub == "commands":
                    lines = self.store.render_set_commands(self.store.candidate)
                    return "\n".join(lines) if lines else "(empty)"
                if sub == "json":
                    return json.dumps(self.store.candidate, indent=2, sort_keys=True)
                # default: indented tree
                body = self.store.render_tree(self.store.candidate)
                if self.store.modified():
                    return "# candidate (uncommitted):\n" + body
                return body
            if kind == "system":
                return self.store.render_tree(self.store.running)
            if kind == "history":
                snaps = self.store.list_history()
                if not snaps:
                    return "(no snapshots yet)"
                return "\n".join(f"  {ts}" for ts, _ in snaps)
            return "show: expected [configuration|system|history]"

        # set / delete
        if head in ("set", "delete"):
            return self._apply_set_delete(head, rest)
        return f"cfg: unknown verb '{head}'"

    def _apply_set_delete(self, verb: str, path_tokens: List[str]) -> str:
        # Prepend current cfg_path so edit/next sessions compose.
        full = self.ctx.cfg_path + path_tokens
        # Walk the cfg tree; canonical names are what gets stored, so
        # abbreviated input ("set syst host-name x") lands in the right node.
        node, remaining, _matched, canon = self.tree.cfg_root.walk([verb] + full)
        structural = canon[1:]           # drop the verb itself
        value_tokens = remaining
        if not structural:
            return f"{verb}: path required"

        if verb == "set":
            if node.value_type:
                value = " ".join(value_tokens)
                if not value:
                    return f"set: missing value for {' '.join(structural)}"
                err = validate_value(node.value_type, value)
                if err:
                    return (f"set: invalid value '{value}' for "
                            f"{' '.join(structural)}: {err}")
                self.store.set_value(structural, coerce_value(node.value_type, value))
                return ""
            if node.children:
                return ("set: incomplete path. expected one of: "
                        + ", ".join(sorted(node.children.keys())))
            # Structural leaf with no value_type: create an empty node.
            self.store.create_node(structural)
            return ""

        # delete: if the landed node is a list, remove matching items;
        # otherwise (scalar leaf or dict) delete the whole structural node.
        target = self.store.get(structural, candidate=True)
        if isinstance(target, list) and value_tokens:
            for v in value_tokens:
                self.store.delete_path(structural + [v])
        else:
            self.store.delete_path(structural)
        return ""

    # ------------ inline help (`?`) ------------
    def _help_text(self, prefix: str) -> str:
        tokens = prefix.split()
        if self.ctx.mode == "cfg" and self.ctx.cfg_path and not tokens:
            # inside `edit`: list the current node's children
            tokens, partial = ["set", ""], ""
        elif prefix.endswith(" ") or not tokens:
            partial = ""
        else:
            partial = tokens.pop()
        pairs = self._matches_with_help(tokens + [""])
        names = [(name, help_text) for name, help_text in pairs
                 if name.startswith(partial)]
        if not names:
            return f"  (no completions for '{prefix.strip()}')"
        width = max(len(name) for name, _ in names)
        return "\n".join(f"  {name.ljust(width + 2)}{help_text}"
                         for name, help_text in names)

    # ------------ main loop ------------
    def cmdloop(self) -> None:
        # set terminal title
        print("\033]0;vyoscli - OpenWrt\007", end="")
        print("Welcome to vyoscli (a VyOS-style CLI for OpenWrt). Type 'exit' to return to shell.")
        while self.running:
            try:
                line = input(self._prompt()).strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not line:
                continue
            if line.endswith("?"):
                # VyOS-style inline help: "show ?", "set system ?", "?"
                print(self._help_text(line[:-1]))
                continue
            try:
                tokens = shlex.split(line)
            except ValueError as e:
                print(f"parse error: {e}")
                continue
            try:
                if self.ctx.mode == "op":
                    out = self._run_op(tokens)
                else:
                    out = self._run_cfg(tokens)
            except Exception as e:  # noqa: BLE001
                out = f"error: {e}"
            if out:
                print(out)
        print("Bye.")
        self.postloop()


def main() -> None:
    store_dir = os.environ.get("VYOSCLI_ETC", "/etc/vyoscli")
    Cli(store_dir).cmdloop()


if __name__ == "__main__":
    main()
