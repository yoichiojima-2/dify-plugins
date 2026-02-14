PLUGIN_NAME := karaage-tencho-kun
PLUGIN_DIR := $(PLUGIN_NAME)
BUILD_DIR := build
PACKAGE_FILE := $(BUILD_DIR)/$(PLUGIN_NAME).difypkg
PYTHON := $(shell if [ -x "$(CURDIR)/.venv/bin/python" ]; then echo "$(CURDIR)/.venv/bin/python"; else echo "python"; fi)

.PHONY: all help build package run test clean

all: package

help:
	@echo "Targets:"
	@echo "  make package   Build plugin package ($(PACKAGE_FILE))"
	@echo "  make build     Alias of package"
	@echo "  make run       Run plugin in debug mode (python -m main)"
	@echo "  make test      Run plugin test suite"
	@echo "  make clean     Remove build artifacts"

build: package

package:
	mkdir -p $(BUILD_DIR)
	dify plugin package $(PLUGIN_DIR) -o $(PACKAGE_FILE)

run:
	cd $(PLUGIN_DIR) && python -m main

test:
	cd $(PLUGIN_DIR) && $(PYTHON) -m unittest discover -s tests -p 'test_*.py' -v

clean:
	rm -f $(PACKAGE_FILE)
