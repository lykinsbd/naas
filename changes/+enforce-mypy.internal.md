Move mypy into the enforced lint job so type errors block CI. Previously mypy ran with continue-on-error=true in a separate job and failures were silently ignored.
