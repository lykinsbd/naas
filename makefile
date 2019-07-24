# The version of the container will be the name of the most recent git tag. Before building a new container,
# please tag the repo with the new version number.
version = $(shell git for-each-ref --sort=-taggerdate --format '%(refname:short)' refs/tags | head -n 1)

.PHONY: all
all: help

.PHONY: clean
clean:  ## delete temporary files
	# Distribution directory
	-rm -rf dist build
	# Cached modules downloaded by setuptools
	-rm -rf .eggs
	# Package metadata
	-rm -rf naas.egg-info
	# Compiled python
	-find naas -name '*.pyc' -o -name '__pycache__' -delete
	# Extra stuff installed by pip
	-rm -rf share

.PHONY: distclean
distclean: clean  ## delete anything that's not part of the repo
	git reset HEAD --hard
	git clean -fxd

.PHONY: build_container
build_container:  ## build the NAAS docker container
	@echo Checking for untagged changes...
	test -z "$(shell git status --porcelain)"
	git diff-index --quiet $(version)
	@echo Repo is clean.
	@echo Building container...
	docker build --pull --build-arg version="$(version)" \
	--tag lykinsbd/naas:$(version) \
	--tag lykinsbd/naas:latest .

.PHONY: push_container
push_container: ## push the NAAS docker container to artifactory
	docker push lykinsbd/naas:$(version)
	docker push lykinsbd/naas:latest

release: build_container push_container ## build and push the NAAS docker container to docker hub

.PHONY: banner
banner:
	@echo ""
	@echo " ███▄▄▄▄      ▄████████    ▄████████    ▄████████ "
	@echo " ███▀▀▀██▄   ███    ███   ███    ███   ███    ███ "
	@echo " ███   ███   ███    ███   ███    ███   ███    █▀  "
	@echo " ███   ███   ███    ███   ███    ███   ███        "
	@echo " ███   ███ ▀███████████ ▀███████████ ▀███████████ "
	@echo " ███   ███   ███    ███   ███    ███          ███ "
	@echo " ███   ███   ███    ███   ███    ███    ▄█    ███ "
	@echo "  ▀█   █▀    ███    █▀    ███    █▀   ▄████████▀  "
	@echo "                                                  "
	@echo ""

.PHONY: help
help: banner
# Help function shamelessly stolen from the Rackspace Engineering Handbook
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'
