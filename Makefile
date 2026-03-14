.PHONY : vscode/package

vscode/package :
	cd vscode && ${MAKE} package
