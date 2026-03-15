.PHONY: build package install clean

build: node_modules
	npm run build

package: build
	npm run package

install: package
	code --install-extension *.vsix

node_modules: package.json
	npm install
	@touch $@

clean:
	rm -rf out node_modules *.vsix
