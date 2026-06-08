smoke-test:
	DOCUMINT_PROFILE=full pytest tests/integration/ -v --integration -k "colpali or qdrant or renderer or verifier" 2>&1 | tee smoke_test_output.txt

integration-test:
	docker compose -f infra/docker-compose.yml up -d postgres redis minio qdrant
	sleep 5
	QDRANT_URL=http://localhost:6333 DOCUMINT_PROFILE=full pytest tests/integration/ --integration -v 2>&1 | tee integration_output.txt

regression:
	pytest tests/regression/ -v --regression 2>&1 | tee regression_output.txt
	@echo "Regression complete. Results in regression_output.txt"

golden-set-check:
	@python -c "from pathlib import Path; import sys; names=['sec_10k','invoice','bank_statement','scanned_contract','academic_paper','phone_photo','handwritten']; missing=[str(Path('golden_set') / f'{name}.expected.json') for name in names if not (Path('golden_set') / f'{name}.expected.json').exists()]; print('All golden set expected.json files present.') if not missing else (print('MISSING expected.json files:'), [print(f'  {m}') for m in missing], sys.exit(1))"

download-models:
	python scripts/download_models.py

check-models:
	@python scripts/check_models.py
