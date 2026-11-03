"""Behaviour tests for the CLI core: candidate store, rendering, commit."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from harness import cfg, cfg_errors, completions, load_json, new_cli, op  # noqa: E402


class DefaultsTest(unittest.TestCase):
    def test_fresh_store_has_ethernet_defaults(self):
        cli = new_cli()
        eth = cli.store.get(["interfaces", "ethernet"])
        self.assertIsNotNone(eth, "DEFAULT_RUNNING lost the ethernet subtree")
        self.assertIn("eth0", eth)
        self.assertTrue(os.path.exists(cli.store.running_path))
        self.assertTrue(os.path.exists(cli.store.candidate_path))


class SetDeleteTest(unittest.TestCase):
    def setUp(self):
        self.cli = new_cli()

    def test_set_scalar(self):
        self.assertEqual(cfg_errors(self.cli, "set system host-name edge"), [])
        self.assertEqual(self.cli.store.get(["system", "host-name"]), "edge")

    def test_abbreviated_path(self):
        self.assertEqual(cfg_errors(self.cli, "set syst host-name edge2"), [])
        self.assertEqual(self.cli.store.get(["system", "host-name"]), "edge2")

    def test_list_append_is_deduplicated(self):
        cfg(self.cli, "set system name-server 9.9.9.9",
            "set system name-server 9.9.9.9")
        self.assertEqual(self.cli.store.get(["system", "name-server"]).count("9.9.9.9"), 1)

    def test_delete_list_member(self):
        cfg(self.cli, "set system name-server 9.9.9.9")
        cfg(self.cli, "delete system name-server 9.9.9.9")
        self.assertNotIn("9.9.9.9", self.cli.store.get(["system", "name-server"]))

    def test_invalid_ipv4_rejected(self):
        out = cfg(self.cli, "set interfaces ethernet eth0 address 300.1.1.1/24")[0]
        self.assertTrue(out.startswith("set: invalid value"), out)
        self.assertEqual(self.cli.store.get(["interfaces", "ethernet", "eth0", "address"]), [])

    def test_extra_token_rejected(self):
        out = cfg(self.cli, "set system name-server 1.1.1.1 extra")[0]
        self.assertTrue(out.startswith("set: invalid value"), out)

    def test_bool_is_coerced_and_rendered_lowercase(self):
        self.assertEqual(cfg_errors(self.cli, "set service adguard enabled true"), [])
        self.assertIs(self.cli.store.get(["service", "adguard", "enabled"]), True)
        self.assertIn("set service adguard enabled true",
                      "\n".join(self.cli.store.render_set_commands()))

    def test_port_out_of_range_rejected(self):
        out = cfg(self.cli, "set service ssh port 70000")[0]
        self.assertTrue(out.startswith("set: invalid value"), out)

    def test_repeatable_leaf_stays_a_list(self):
        # DEFAULT_RUNNING declares system.ntp as a list; a config file that
        # predates the key must not turn "223.5.5.5" into 9 characters.
        cfg(self.cli, "set system ntp 223.5.5.5")
        cfg(self.cli, "set system ntp 1.1.1.1")
        value = self.cli.store.get(["system", "ntp"])
        self.assertIsInstance(value, list)
        self.assertIn("223.5.5.5", value)
        self.assertIn("1.1.1.1", value)
        self.assertNotIn("2", value)

    def test_candidate_survives_restart(self):
        cfg(self.cli, "set system host-name persisted")
        # A brand-new CLI on the same directory must see the edit.
        again = new_cli(self.cli.store.base_dir)
        self.assertEqual(again.store.get(["system", "host-name"]), "persisted")
        self.assertTrue(again.store.modified())


class RenderTest(unittest.TestCase):
    def setUp(self):
        self.cli = new_cli()

    def test_unset_defaults_are_not_rendered(self):
        text = "\n".join(self.cli.store.render_set_commands())
        self.assertNotIn("None", text)
        self.assertNotIn("hardware vendor \n", text)
        tree = self.cli.store.render_tree()
        self.assertNotIn("None", tree)

    def test_value_with_spaces_is_quoted(self):
        cfg(self.cli, "set interfaces ethernet eth0 description core uplink")
        line = [x for x in self.cli.store.render_set_commands()
                if "description" in x][0]
        self.assertIn("'core uplink'", line)

    def test_export_import_round_trip(self):
        cfg(self.cli,
            "set system host-name r1",
            "set system name-server 223.5.5.5",
            "set interfaces ethernet eth0 address 203.0.113.10/24",
            "set interfaces ethernet eth0 description 'core uplink'",
            "set service adguard enabled false",
            "set service ssh port 2222",
            "set service crontab daily schedule '0 3 * * *'",
            "set protocols static route 10.0.0.0/8 next-hop 192.168.1.1")
        exported = self.cli.store.render_set_commands()

        fresh = new_cli()
        bad = cfg_errors(fresh, *exported)
        self.assertEqual(bad, [], f"exported commands rejected: {bad}")
        self.assertEqual(fresh.store.candidate, self.cli.store.candidate)


class CommitTest(unittest.TestCase):
    def setUp(self):
        self.cli = new_cli()

    def test_commit_moves_candidate_to_running(self):
        cfg(self.cli, "set system host-name committed")
        out = self.cli.store.commit()
        self.assertIn("Commit complete", out)
        self.assertFalse(self.cli.store.modified())
        self.assertEqual(load_json(self.cli.store.running_path)["system"]["host-name"],
                         "committed")
        self.assertEqual(len(self.cli.store.list_history()), 1)

    def test_commit_without_changes(self):
        self.assertEqual(self.cli.store.commit(), "No changes to commit.")

    def test_commit_conflict_leaves_state_untouched(self):
        # dnsmasq listens on 53 by default; enabling adguard on 53 conflicts.
        cfg(self.cli,
            "set service adguard enabled true",
            "set service adguard port 53",
            "set system host-name should-not-apply")
        before = dict(self.cli.store.running)
        out = self.cli.store.commit()
        self.assertIn("Commit aborted", out)
        self.assertEqual(self.cli.store.running, before)
        self.assertTrue(self.cli.store.modified())
        self.assertEqual(load_json(self.cli.store.running_path), before)

    def test_compare_and_discard(self):
        cfg(self.cli, "set system host-name temp")
        self.assertIn("+ set system host-name temp", self.cli.store.compare())
        cfg(self.cli, "discard")
        self.assertFalse(self.cli.store.modified())
        self.assertEqual(self.cli.store.compare(), "No changes.")

    def test_rollback_restores_previous_snapshot(self):
        cfg(self.cli, "set system host-name first")
        self.cli.store.commit()
        cfg(self.cli, "set system host-name second")
        self.cli.store.commit()
        out = self.cli.store.rollback_to()
        self.assertIn("Rolled back", out)
        self.assertEqual(self.cli.store.running["system"]["host-name"], "first")

    def test_confirm_without_armed_timer(self):
        self.assertIn("No pending", self.cli.store.confirm())

    def test_stale_rollback_file_is_not_reported_as_pending(self):
        self.cli.store._dump(self.cli.store.rollback_conf,
                             {"pid": 999999, "deadline": 1, "snapshot": "/tmp/x"})
        self.assertIsNone(self.cli.store.pending_rollback())
        self.assertIn("No pending", self.cli.store.confirm())

    @unittest.skipIf(os.name == "nt", "POSIX permission bits only")
    def test_config_files_are_private(self):
        cfg(self.cli, "set system host-name perms")
        self.cli.store.commit()
        for path in (self.cli.store.running_path, self.cli.store.candidate_path):
            self.assertEqual(os.stat(path).st_mode & 0o777, 0o600, path)


class CompletionTest(unittest.TestCase):
    def setUp(self):
        self.cli = new_cli()

    def test_root_lists_verbs(self):
        names = [name for name, _ in completions(self.cli)]
        for verb in ("set", "delete", "edit", "commit", "discard", "show"):
            self.assertIn(verb, names)

    def test_path_completion(self):
        names = [name for name, _ in completions(self.cli, "set system ")]
        self.assertIn("host-name", names)
        self.assertIn("name-server", names)

    def test_leaf_completion_has_value_hint(self):
        self.cli.ctx.cfg_path = []
        pairs = dict(completions(self.cli, "set interfaces ethernet eth0 address "))
        self.assertEqual(pairs.get("a.b.c.d/prefix"), "value")


class OpModeTest(unittest.TestCase):
    def setUp(self):
        self.cli = new_cli()

    def test_show_configuration_uses_running(self):
        cfg(self.cli, "set system host-name running-only")
        self.cli.store.commit()
        self.assertIn("running-only", op(self.cli, "show configuration"))
        cfg(self.cli, "set system host-name candidate-only")
        self.assertNotIn("candidate-only", op(self.cli, "show configuration"))

    def test_invalid_command_is_reported(self):
        out = op(self.cli, "definitely-not-a-command --nope")
        self.assertIn("Invalid command", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
