LICENSE_CONFIG?="license-config.json"

node_modules/license-check-and-add:
	npm ci

LICENSE:
	@echo "you must have a LICENSE file" 1>&2
	exit 1

LICENSE_HEADER:
	@echo "you must have a LICENSE_HEADER file" 1>&2
	exit 1

.PHONY: license
license: LICENSE_HEADER
	npm run license:fix

.PHONY: license-deploy
license-deploy: node_modules/license-check-and-add LICENSE LICENSE_HEADER
	LICENSE_CONFIG=${LICENSE_CONFIG} npm run license:deployPHONY: test

.PHONY: test-unit
test-unit:
# envvars required:
	S3_STATIC_ARN=arn:aws:s3:::bucket-name JWT_SECRET=secret REGION=us-east-1 \
	 python -m py.test -vv test/unit

.PHONY: test-integration
test-integration:
# envvars injected by the cicd pipeline
	python -m py.test -vv test/integration
