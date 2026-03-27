#!/usr/bin/env python3
"""Interactive smoke test for Switchboard.

Run with:
    python examples/smoke_test.py

Or from the project root (before pip install):
    PYTHONPATH=. python examples/smoke_test.py

This script demonstrates the core Switchboard functionality with
visible output for manual verification.
"""

from __future__ import annotations

import sys


def main() -> int:
    """Run the smoke test."""
    print("=" * 60)
    print("Switchboard Smoke Test")
    print("=" * 60)
    print()

    passed = 0
    failed = 0

    def check(name: str, condition: bool, detail: str = "") -> None:
        nonlocal passed, failed
        if condition:
            print(f"  [PASS] {name}")
            passed += 1
        else:
            print(f"  [FAIL] {name}")
            if detail:
                print(f"         {detail}")
            failed += 1

    # Step 1: Import
    print("Step 1: Import Switchboard")
    try:
        from switchboard import (
            HookDefinition,
            HookKind,
            PatchPanel,
            SlotDefinition,
            SlotPolicy,
            parse_manifest,
        )
        from switchboard.adapters.hook_router_memory import MemoryHookRouter
        from switchboard.adapters.loader import ImportLoader

        check("Import successful", True)
    except ImportError as e:
        check("Import successful", False, str(e))
        return 1
    print()

    # Step 2: Create PatchPanel
    print("Step 2: Create PatchPanel")
    try:
        panel = PatchPanel(
            slots=[
                SlotDefinition("ui.sidebar", policy=SlotPolicy.MULTI),
                SlotDefinition("ui.main", policy=SlotPolicy.SINGLE),
            ],
            hooks=[
                HookDefinition("app.started", kind=HookKind.LIFECYCLE),
                HookDefinition("command.run", kind=HookKind.COMMAND),
            ],
            hook_router=MemoryHookRouter(),
            loader=ImportLoader(),
        )
        check("PatchPanel created", True)
        check("Slots defined", len(panel.list_slots()) == 2)
        check("Hooks defined", len(panel.list_hooks()) == 2)
    except Exception as e:
        check("PatchPanel created", False, str(e))
        return 1
    print()

    # Step 3: Parse manifest
    print("Step 3: Parse Plugin Manifest")
    manifest_yaml = """
manifest_version: "1"
plugin_id: com.example.smoke
plugin_version: "1.0.0"
requires_switchboard: ">=0.1.0,<1.0.0"
entrypoint: tests.fixtures.sample_plugin:SamplePlugin
contributions:
  slots:
    - contribution_id: sidebar.widget
      slot_key: ui.sidebar
      priority: 75
  hooks:
    - contribution_id: on.started
      hook_key: app.started
      handler: tests.fixtures.sample_plugin:on_app_started
      priority: 100
"""
    try:
        manifest = parse_manifest(manifest_yaml)
        check("Manifest parsed", True)
        check("Plugin ID correct", manifest.plugin_id == "com.example.smoke")
        check("Has slot contribution", len(manifest.contributions.slots) == 1)
        check("Has hook contribution", len(manifest.contributions.hooks) == 1)
    except Exception as e:
        check("Manifest parsed", False, str(e))
        return 1
    print()

    # Step 4: Register plugin
    print("Step 4: Register Plugin")
    try:
        panel.register_manifest(manifest)
        check("Plugin registered", "com.example.smoke" in panel.list_plugins())
        state = panel.get_plugin_state("com.example.smoke")
        check("Plugin in ready state", state.value == "ready")
    except Exception as e:
        check("Plugin registered", False, str(e))
        return 1
    print()

    # Step 5: Activate plugin
    print("Step 5: Activate Plugin")
    try:
        panel.activate("com.example.smoke")
        state = panel.get_plugin_state("com.example.smoke")
        check("Plugin activated", state.value == "active")
    except Exception as e:
        check("Plugin activated", False, str(e))
        return 1
    print()

    # Step 6: Resolve slot
    print("Step 6: Resolve Slot")
    try:
        contributions = panel.resolve_slot("ui.sidebar")
        check("Slot resolved", len(contributions) == 1)
        check(
            "Contribution correct",
            contributions[0].contribution_id == "sidebar.widget",
        )
        check("Priority correct", contributions[0].priority == 75)
    except Exception as e:
        check("Slot resolved", False, str(e))
        return 1
    print()

    # Step 7: Emit hook
    print("Step 7: Emit Hook")
    try:
        results = panel.emit("app.started", {"timestamp": 12345})
        check("Hook emitted", len(results) == 1)
        check("Handler returned result", "started:12345" in str(results[0]))
    except Exception as e:
        check("Hook emitted", False, str(e))
        return 1
    print()

    # Step 8: Introspection
    print("Step 8: Introspection")
    try:
        info = panel.runtime_info()
        check("runtime_info() works", info.plugin_count == 1)
        check("Active count correct", info.active_plugin_count == 1)

        snap = panel.snapshot()
        check("snapshot() works", len(snap.plugins) == 1)
        check("Snapshot plugin state", snap.plugins[0].state == "active")

        text = panel.dump_state()
        check("dump_state() text works", "com.example.smoke" in text)

        json_str = panel.dump_state(format="json")
        import json

        data = json.loads(json_str)
        check("dump_state() json works", "plugins" in data)
    except Exception as e:
        check("Introspection", False, str(e))
        return 1
    print()

    # Step 9: Priority ordering
    print("Step 9: Priority Ordering Verification")
    try:
        # Add another plugin with different priority
        manifest2_yaml = """
manifest_version: "1"
plugin_id: com.example.smoke2
plugin_version: "1.0.0"
requires_switchboard: ">=0.1.0,<1.0.0"
entrypoint: tests.fixtures.sample_plugin:AnotherPlugin
contributions:
  slots:
    - contribution_id: sidebar.widget2
      slot_key: ui.sidebar
      priority: 50
"""
        manifest2 = parse_manifest(manifest2_yaml)
        panel.register_manifest(manifest2)
        panel.activate("com.example.smoke2")

        contributions = panel.resolve_slot("ui.sidebar")
        check("Two contributions", len(contributions) == 2)
        check(
            "Higher priority first",
            contributions[0].priority > contributions[1].priority,
        )
        check(
            "Order correct",
            contributions[0].contribution_id == "sidebar.widget",
        )
    except Exception as e:
        check("Priority ordering", False, str(e))
        return 1
    print()

    # Summary
    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    if failed > 0:
        print("\nSMOKE TEST FAILED")
        return 1
    else:
        print("\nSMOKE TEST PASSED")
        return 0


if __name__ == "__main__":
    sys.exit(main())
