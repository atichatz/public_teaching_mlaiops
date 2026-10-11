# Lab 4 — Blocked bad commit evidence

- Pull request: https://github.com/atichatz/public_teaching_mlaiops/pull/2
- Workflow run: https://github.com/atichatz/public_teaching_mlaiops/actions/runs/37604360319
- Deliberate fault: removed the required `temp_c` column from the generated dataset.
- Blocking test: `test_schema_columns_present_and_typed`
- Error: `missing columns: ['temp_c']`
- Test job result: failure.
- Build and integration job result: skipped.
- Resolution: the pull request was closed without merging.
