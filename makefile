# The version of the container will be the name of the most recent git tag. Before building a new container,
# please tag the repo with the new version number.
version = $(shell git for-each-ref --sort=-taggerdate --format '%(refname:short)' refs/tags | head -n 1)

.phony: all container

all:
	@echo The current tagged version is $(version)
	@echo Run 'make container' to build a new container and tag it with this version.

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

container:
	@echo Checking for untagged changes...
	test -z "$(shell git status --porcelain)"
	git diff-index --quiet $(version)
	@echo Repo is clean.
	@echo Building container...
	docker build --pull --build-arg version="$(version)" \
	--tag lykinsbd/naas:$(version) \
	--tag lykinsbd/naas:latest .

container_push: ## push the docker container to artifactory
	docker push lykinsbd/naas:$(version)
	docker push lykinsbd/naas:latest

release: container_build container_push ## build and push a release to docker hub
