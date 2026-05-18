import sys
import os

if __name__ == "__main__":
    if "--gui" in sys.argv:
        from ui.gui_pet import run_gui
        run_gui()
    else:
        from ui.tui_term import NativeTerminalTUI
        tui = NativeTerminalTUI()
        tui.run_loop()