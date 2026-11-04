import copy
import unittest

from adapt_plan import POLICY_PATH, SETTINGS, VERSION, adapt


def item(name, state="Uncompleted", **fields):
    return {"action": {"action_name": name, **fields}, "state": state}


def fixture():
    return {
        "version": VERSION,
        "planner": {"planner": "linux", "settings": copy.deepcopy(SETTINGS),
                    "init": {"init": "None", "start_daemon": False}},
        "actions": [
            item("create_directory", "Completed", path="/nix", is_mountpoint=True),
            item("provision_nix"), item("create_users_and_group"),
            item("configure_nix", place_nix_configuration=None,
                 configure_shell_profile=None, setup_channels=None),
            item("provision_selinux", policy_path="/usr/share/selinux/packages/nix.pp",
                 policy_content=[1, 2, 3]),
            item("create_directory", path="/etc/tmpfiles.d"),
            item("create_upstream_init_service", configure_init_service=item(
                "configure_init_service", init="None", start_daemon=False)),
            item("remove_directory", path="/nix/temp-install-dir"),
        ],
    }


class PlanTests(unittest.TestCase):
    def test_owners_and_policy(self):
        original = fixture()
        result = adapt(original)
        self.assertEqual(len(result["actions"]), 5)
        self.assertEqual(result["actions"][3]["action"]["policy_path"], POLICY_PATH)
        self.assertEqual(original, fixture())

    def test_reject_settings_drift(self):
        for field in ("modify_profile", "force", "add_channel"):
            plan = fixture()
            plan["planner"]["settings"][field] = True
            with self.subTest(field=field), self.assertRaises(ValueError):
                adapt(plan)

    def test_reject_configuration_actions(self):
        for field in ("place_nix_configuration", "configure_shell_profile", "setup_channels"):
            plan = fixture()
            plan["actions"][3]["action"][field] = {}
            with self.subTest(field=field), self.assertRaises(ValueError):
                adapt(plan)

    def test_reject_unmounted_store(self):
        plan = fixture()
        plan["actions"][0]["action"]["is_mountpoint"] = False
        with self.assertRaises(ValueError):
            adapt(plan)

    def test_reject_unknown_or_missing_actions(self):
        for index in range(8):
            plan = fixture()
            del plan["actions"][index]
            with self.subTest(index=index), self.assertRaises(ValueError):
                adapt(plan)

    def test_reject_changed_version(self):
        plan = fixture()
        plan["version"] = "unreviewed"
        with self.assertRaises(ValueError):
            adapt(plan)

    def test_reject_changed_cleanup(self):
        plan = fixture()
        plan["actions"][7]["action"]["path"] = "/nix"
        with self.assertRaises(ValueError):
            adapt(plan)


if __name__ == "__main__":
    unittest.main()
