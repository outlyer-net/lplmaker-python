
PROGNAME=lplmaker
ENTRYPOINT=$(PROGNAME).py
SPECFILE=$(PROGNAME).spec
# To cross-compile, this script runs pyinstaller in a Wine bottle.
# NOTE the Python installation in Wine must have the toml installed for the resulting exe to work
WINE_PYINSTALLER=./wine-pyinstaller

all:

pkg: dist/$(PROGNAME) dist/$(PROGNAME).exe

dist/$(PROGNAME):
	pyinstaller --onefile $(ENTRYPOINT)

dist/$(PROGNAME).exe:
	"$(WINE_PYINSTALLER)" --onefile $(ENTRYPOINT)

clean:
	$(RM) $(SPECFILE) *.pyc
	$(RM) -r build/ dist/

distclean: clean

.PHONY: all pkg clean distclean
