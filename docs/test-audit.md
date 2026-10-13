# Test audit

This audit removes 24 of 58 test methods, or 41.4%. The remaining 34 methods protect file installation, config merging, user edits, unsafe inputs, CLI behavior, and platform contracts. Three parallel, read-only auditors reviewed every test and its production owner. The parent reviewed their results and made all edits.

## Scope and authorization

The user's test-audit request authorizes test deletion, removal of test-only production code, and the five testing rules in `AGENTS.md`. Acceptance requires observable contracts, credible regressions, distinct protection beyond existing integration tests, and resilience to behavior-preserving refactors. The numerical target is at least 20% removal with coverage within two percentage points, or an explanation of incompatibility. No failing test may be deleted to obtain a passing result.

The baseline is revision `c0d40ef35a4d9765d9d4fa0b3c811b5a6af7b3a6`. Both measured runs used macOS ARM64, Python 3.14.4, and coverage.py 7.16.2. [summary.json](test-audit/summary.json) contains exact totals, removed names, environment details, and SHA-256 hashes of the final test, production, and instruction files. The [baseline log](test-audit/before-tests.log) and [final log](test-audit/after-tests.log) record individual results. No baseline test failed. Four Windows-only methods were skipped in both runs.

## Verification and coverage

Before PR creation, `main` advanced to `cd6337bb9b6724aeebde753c1ecfb4c29a2c21c8`, adding nine sync tests and expanding the configuration-pin test selected for removal. The expanded candidate and its updated owner were read before resolving the rebase conflict. The same removal criteria still apply. All nine new sync tests and their production behavior remain unchanged.

Fresh measurements against this PR base run 67 baseline methods and 43 final methods, with four Windows-only skips in both runs. Both suites pass. The real `python3 manage.py check-sync --repo-only` command also passes. The removal is 24/67, or 35.8%, of the latest repository suite. Line coverage is 811/1052, or 77.09%, before and 681/1050, or 64.86%, after. Branch coverage is 404/592, or 68.24%, before and 329/592, or 55.57%, after. The two-point target remains unmet for the same reasons described below.

[pr-validation.json](test-audit/pr-validation.json), the [PR baseline log](test-audit/pr-before-tests.log), and the [PR final log](test-audit/pr-after-tests.log) record this newer base and final artifact hashes. The figures in the following paragraphs describe the original audit pair at `c0d40ef`, rather than the newer PR base.

The baseline ran 58 methods and passed with four skips. The final measured run ran 34 methods and passed with four skips. The production statement denominator changed from 952 to 950 because the test-only `portable.config.parse` wrapper was deleted. That removes two nonblank production lines, plus surrounding blank lines. All other production behavior remains in place.

Line coverage changed from 723/952, or 75.95%, to 593/950, or 62.42%. Branch coverage changed from 352/530, or 66.42%, to 277/530, or 52.26%. Coverage.py's combined line/branch score changed from 72.54% to 58.78%.

The two-point coverage target was not met. The strict mock and refactor rules require removing tests that uniquely execute native restore, Sentry registration, inventory, and reconciliation code. Existing CLI integration tests exercise `refresh` and `link`, not native `bootstrap` or `inventory`. Removing those required candidates loses 86 previously executed lines in `portable/apps.py` and 24 in `manage.py`. Crash and race probes lose another 14 executed lines in `portable/install.py`. These losses alone exceed the coverage allowance. Preserving the old score would require retaining rejected tests or adding substantial new behavioral coverage. No coverage exclusions or coverage-only replacements were added.

The repository had no coverage configuration or baseline report. Both measurements use the whole checkout as the production source, omit tests, enable branch measurement, and capture Python subprocesses. Copies of the checkout created inside temporary test fixtures are outside that source directory and excluded in both measurements. Results therefore cover the original production paths, including the original-checkout CLI subprocess, rather than every executed copy. These figures are local measurements, not fresh cross-platform CI results.

To repeat the measurement from a checkout, use an isolated environment and this configuration:

```ini
[run]
branch = True
parallel = True
source = .
omit = */tests/*
patch = subprocess
[report]
precision = 2
```

Run these commands from that checkout, with the configuration saved as `/tmp/test-audit-coverage.ini`:

```sh
python3 -m venv /tmp/test-audit-venv
/tmp/test-audit-venv/bin/python -m pip install coverage==7.16.2
COVERAGE_RCFILE=/tmp/test-audit-coverage.ini COVERAGE_FILE=/tmp/test-audit-result /tmp/test-audit-venv/bin/python -m coverage run -m unittest discover -s tests -v
COVERAGE_RCFILE=/tmp/test-audit-coverage.ini COVERAGE_FILE=/tmp/test-audit-result /tmp/test-audit-venv/bin/python -m coverage combine
COVERAGE_RCFILE=/tmp/test-audit-coverage.ini COVERAGE_FILE=/tmp/test-audit-result /tmp/test-audit-venv/bin/python -m coverage json -o /tmp/test-audit-result.json
```

Use separate result paths for baseline and final runs. Run the baseline from a separate checkout of the recorded revision. Different Python versions or operating systems can change executable line and branch counts.

## Removed methods

Each candidate was read with its production owner before deletion. The following reasons distinguish redundancy from lost but brittle protection:

- `test_config_link_recovers_after_target_was_written`: Patches internal `install.atomic`. Renaming or replacing the writer breaks crash injection. Linked-config interruption coverage is lost.
- `test_config_link_failure_preserves_existing_files`: Requires an intercepted `Path.symlink_to` call. An equivalent `os.symlink` implementation breaks it. Permission-denial protection is not replaced by the happy-path CLI test.
- `test_config_link_interruption_preserves_config_and_can_retry`: Pins internal writer, marker, and replacement boundaries. Unique linking-interruption cases are lost.
- `test_directory_link_second_app_failure_leaves_first_link`: Duplicates malformed-second-app preflight refusal. Retained malformed-config and malformed-journal tests cover refusal before first-app publication.
- `test_directory_link_recovery_boundaries_and_app_edits`: Pins writer and directory-operation calls. Unique partial-conversion recovery and edit-conflict cases are lost.
- `test_existing_bytes_and_local_instruction_preserved`: Captures expected config bytes after the first refresh, so initial formatting corruption passes. Rerun stability and managed-file edit preservation have stronger retained filesystem tests.
- `test_removed_unchanged_owned_file_deleted`: Same removal branch as the retained removed-skill migration test, which also protects edited and external files across both apps.
- `test_crash_recovery_all_durable_boundaries`: Requires internal `atomic` calls and journal/baseline write order. Distinct crash-recovery cases are lost.
- `test_crash_then_app_edit_refuses_overwrite`: Requires internal writer interception. Interrupted-file conflict refusal is a remaining gap.
- `test_app_edit_between_plan_and_publish_refuses`: Pins the internal `plan`/`publish` decomposition and payload. A combined transaction can preserve behavior and break it. The race scenario remains uncovered.
- `test_repository_only_manages_authored_skills_and_install_guide`: Pins source inventory and directory names. CLI installation and retained ownership scenarios cover installer behavior without freezing the selected skill list.
- `test_inventory_routes_third_party_skills_to_upstream_guide`: Greps prose and patches CLI internals. It asserts no installed state or non-installation effect.
- `test_repository_manifest_and_sentry_environment`: Combines an assertion-free manifest load with restated allowlist strings. It never establishes actual child environment forwarding.
- `test_native_install_retains_local_disabled_flag`: Meaningful opposite-state stimulus, but patches internal `restore`/`installed` and asserts an internal plugin payload. Unique native reconciliation protection is lost.
- `test_journal_escape_and_reparse_parent_rejected`: Direct helper call with a canned link classifier. Manifest escapes and real unsafe ancestors remain covered. Hostile recovery-journal paths remain a gap.
- `test_native_install_retains_deleted_plugin_table`: Patches internal restoration and parsing seams. Unique reconciliation after native mutation is lost.
- `test_serializer_complete_types`: Repeats `render`'s own parser/equality self-check using its production comparator. A shared comparator defect can pass both checks. Its sole consumer of the test-only `parse` wrapper disappears with it.
- `test_real_repository_app_specific_pstack_models`: Greps literal model roles and pins source values. The retained old/new manifest upgrade scenario protects routing and local edits.
- `test_failed_plugin_does_not_skip_later_restores`: Fake internal command implements installed state and dispatches on current argument shapes. Later-plugin progress after a failure remains a distinct gap.
- `test_shapes_disabled_installs_and_idempotency`: Mock implements install/disable state. Final assertions count internal calls rather than inspect observed native state.
- `test_sentry_existing_definition_never_replaced`: Only counts calls and checks a keyword argument. A destructive sole command could pass.
- `test_sentry_missing_created_then_observed`: Canned responses and call-shape checks can pass with the wrong MCP spec or executable.
- `test_codex_object_shape_and_missing_capability`: Mocks the internal command seam for shallow membership/error assertions. Actual native object-response compatibility remains a gap.
- `test_runtime_plugins_not_restored_as_native`: Greps a warning without proving installation was skipped. A warning plus unwanted installation could pass.

The first five methods belong to `portable/links.py`, `portable/manage.py`, and `portable/install.py`. File/config ownership and validation methods belong to `portable/manage.py` and `portable/install.py`. Serializer behavior belongs to `portable/config.py`. Native restoration, registration, and reconciliation belong to `portable/apps.py`. Inventory output belongs to root `manage.py`. These runtime owners remain necessary and were not deleted to improve the denominator.

The synthetic reparse subcase and internal `portable.manage.linked` patch were also removed from `test_directory_link_unsafe_ancestors_and_broken_roots`. Real ancestor and broken-root fixtures remain. The actual Windows junction test protects reparse behavior. The unnecessary symlink-call interception was removed from the fresh-machine test; its file, mtime, and backup assertions remain.

## Retained methods and distinct regressions

These 34 methods remain because their stimuli and observations protect contracts absent from stronger existing tests:

- `test_opt_in_config_link_preserves_live_bytes_and_refreshes`: Stale checkout bytes must not replace live config. Later updates preserve local notes and the opted-in link.
- `test_new_config_link_does_not_import_an_unrelated_legacy_baseline`: A stale snapshot must not delete local marketplace settings from a new link.
- `test_config_link_rejects_retargeting_without_writing_foreign_file`: A retargeted link must refuse refresh and preserve both files.
- `test_config_link_can_be_restored_after_app_replaces_link`: Relinking adopts app-edited bytes rather than stale checkout bytes.
- `test_real_cli_config_link`: Exercises real argument parsing, home routing, link establishment, and refresh through a subprocess.
- `test_real_cli_legacy_directory_links`: Both apps convert real absolute/relative legacy links without modifying the source; repeated CLI refresh remains idle.
- `test_directory_link_remapped_nested_empty_and_foreign`: Remapped destinations preserve empty directories and refuse foreign roots.
- `test_remapped_child_file_link_uses_manifest_source`: Child-file migration must use the mapped source rather than assume matching paths.
- `test_invalid_second_app_journal_payload_no_first_app_write`: A malformed second-app recovery journal blocks all first-app mutation.
- `test_windows_junction_is_rejected_without_target_write`: Actual Windows reparse detection must prevent checkout writes.
- `test_directory_link_unsafe_ancestors_and_broken_roots`: Real unsafe ancestors and broken roots must refuse installation before state creation.
- `test_directory_link_empty_asset`: Zero file updates must not bypass an empty-directory conversion.
- `test_fresh_machine_and_identical_rerun`: Actual mtimes and backups detect needless writes that a zero-change CLI message can miss.
- `test_shared_defaults_update_remove_and_local_changes`: Shared updates adopt new keys while retaining local edits and deletions.
- `test_entire_table_deletion_and_array_override`: Deleted tables stay deleted; arrays remain whole local overrides.
- `test_removed_shared_table_keeps_unknown_local_keys`: Removing a shared table removes owned children without erasing local keys.
- `test_edited_removed_deleted_and_unmanaged_skills`: Local deletions, upstream-removed edits, and unmanaged files survive refresh.
- `test_foreign_symlinks_migrate_without_target_write`: Foreign file targets stay untouched while local regular files and backup records replace links.
- `test_malformed_inputs_no_mutation`: Invalid live TOML causes no filesystem mutation.
- `test_malformed_second_app_no_first_app_mutation`: Invalid second-app JSON blocks first-app config creation.
- `test_cross_home_state_separation_and_source_unchanged`: Editing one installation cannot alter another home or the checkout.
- `test_legacy_journal_refused`: Pending legacy recovery blocks migration before a new config appears.
- `test_claude_auth_local_changes_retained`: A secret in existing live settings and a local model survive refresh without source publication.
- `test_shared_secret_is_rejected_before_home_mutation`: A committed credential is rejected before any installation.
- `test_removed_owned_skill_migration_preserves_edits_and_external_files`: Removed assets relinquish ownership, delete unchanged children, and retain edited/external files across both apps.
- `test_local_profile_retains_secret_outside_repo`: A machine-local profile reaches live settings without entering shared source config.
- `test_path_collision_and_escape_rejected`: Traversal, drive paths, reserved names, and trailing dots are rejected through the manifest boundary. The method does not actually test collisions despite its name.
- `test_pstack_models_upgrade_preserves_local_edits`: An old shared source upgrades to app-specific sources while retaining local edits and remaining idle on rerun.
- `test_real_cli_fresh_home_and_canary_output`: Real all-app initialization succeeds without exposing an environment canary and reports an idle rerun.
- `test_npm_claude_native_entry_needs_no_node`: The external npm layout must select Claude's native Windows executable without requiring Node.
- `test_native_cmd_shim_and_scoped_longpaths`: A real child receives exact metacharacter-rich arguments and scoped Git settings without mutating the parent environment.
- `test_missing_launcher_and_child_exit_code`: Real PowerShell startup rejects missing Python and propagates child exit codes.
- `test_default_claude_home_retains_native_config_lookup`: The external subprocess environment preserves default credential lookup, custom-home routing, and explicit overrides.
- `test_failed_native_command_redacts_output`: A failed external subprocess containing secrets must not expose its output in the raised error.

## Judgment calls and gaps

The two retained native environment/error tests capture the standard subprocess boundary. Their fixtures supply external input or observe external payloads; they do not implement config routing or error redaction. That boundary is treated as a contract, unlike the deleted mocks of the repository's own restoration helpers. A switch to a different process transport would require reconsidering these fixtures. The Windows npm-layout fixture also controls executable discovery; it protects a documented external installation layout.

The deleted interruption and native-reconciliation tests had useful intent. Their failures under harmless internal changes violate the user's explicit criterion, but their scenarios are not redundant with E2E coverage. Native bootstrap, Sentry registration, inventory, crash recovery, publication races, recovery-journal hostile paths, and uncommon TOML types remain unverified at a robust higher boundary. This audit does not claim those product paths are correct.

No retained test failed. Four Windows-only tests require Windows verification; local macOS results do not establish their current behavior. The archived local runs do not substitute for the PR's fresh CI matrix.

The five requested rules appear verbatim in root `AGENTS.md` for this checkout and in `codex/AGENTS.md` for the portable global instructions. No refresh of the user's actual application homes was performed.
