# DSL Lite — common development and deployment commands
#
# Usage:
#   make validate-presets          # validate all preset YAMLs
#   make validate-bundle b=cisco/ios -t dev  # validate one bundle
#   make validate-bundles          # validate all bundles
#   make deploy b=cisco/ios        # deploy one bundle (dev target)
#   make deploy-all                # deploy all bundles (dev target)
#   make run b=cisco/ios           # run SDP pipeline for a bundle (dev)
#   make destroy b=cisco/ios       # destroy one bundle (dev target)
#   make check-templates           # check OCSF template field coverage

.PHONY: help validate-presets validate-bundle validate-bundles \
        deploy deploy-all run destroy check-templates

# Default target — show usage
help:
	@echo ""
	@echo "DSL Lite — available targets:"
	@echo ""
	@echo "  Presets:"
	@echo "    validate-presets          Validate all preset.yaml files under pipelines/"
	@echo "    validate-preset p=<path>  Validate a single preset file"
	@echo ""
	@echo "  Bundles (set b=<source>/<source_type>, e.g. b=cisco/ios):"
	@echo "    validate-bundle           databricks bundle validate -t dev"
	@echo "    validate-bundles          validate-bundle for every bundle"
	@echo "    deploy                    databricks bundle deploy -t dev"
	@echo "    deploy-all                deploy every bundle to dev"
	@echo "    run                       databricks bundle run <source>_<source_type>_sdp -t dev"
	@echo "    destroy                   databricks bundle destroy -t dev"
	@echo ""
	@echo "  OCSF templates:"
	@echo "    check-templates           check OCSF template field coverage vs DDL"
	@echo ""

# ── Presets ──────────────────────────────────────────────────────────────────

validate-presets:
	python3 vault/validate_preset.py

validate-preset:
ifndef p
	$(error Set p=<path>, e.g. make validate-preset p=pipelines/cisco/ios/preset.yaml)
endif
	python3 vault/validate_preset.py $(p)

# ── Bundles ──────────────────────────────────────────────────────────────────

# Helper: derive the resource key from the bundle path (cisco/ios → cisco_ios)
_resource_key = $(subst /,_,$(b))

validate-bundle:
ifndef b
	$(error Set b=<source>/<source_type>, e.g. make validate-bundle b=cisco/ios)
endif
	cd bundles/$(b) && databricks bundle validate -t dev

validate-bundles:
	@for bundle in bundles/*/*; do \
		echo "── $$bundle ──"; \
		(cd $$bundle && databricks bundle validate -t dev) || exit 1; \
	done

deploy:
ifndef b
	$(error Set b=<source>/<source_type>, e.g. make deploy b=cisco/ios)
endif
	cd bundles/$(b) && databricks bundle deploy -t dev

deploy-all:
	@for bundle in bundles/*/*; do \
		echo "── deploying $$bundle ──"; \
		(cd $$bundle && databricks bundle deploy -t dev) || exit 1; \
	done

run:
ifndef b
	$(error Set b=<source>/<source_type>, e.g. make run b=cisco/ios)
endif
	cd bundles/$(b) && databricks bundle run $(_resource_key)_sdp -t dev

destroy:
ifndef b
	$(error Set b=<source>/<source_type>, e.g. make destroy b=cisco/ios)
endif
	cd bundles/$(b) && databricks bundle destroy -t dev

# ── OCSF templates ───────────────────────────────────────────────────────────

check-templates:
	python3 vault/check_template_fields.py
