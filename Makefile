PLUGIN_DIR := karaage-tencho-kun
PLUGIN_NAME := karaage-tencho-kun
BUILD_DIR := build
PACKAGE_FILE := $(BUILD_DIR)/$(PLUGIN_NAME).difypkg

.PHONY: all help build package run clean

all: package

help:
	@echo "Targets:"
	@echo "  make package   Build plugin package ($(PACKAGE_FILE))"
	@echo "  make build     Alias of package"
	@echo "  make run       Run plugin in debug mode (python -m main)"
	@echo "  make clean     Remove build artifacts"

build: package

package:
	mkdir -p $(BUILD_DIR)
	dify plugin package $(PLUGIN_DIR) -o $(PACKAGE_FILE)

run:
	cd $(PLUGIN_DIR) && python -m main

clean:
	rm -f $(PACKAGE_FILE)
