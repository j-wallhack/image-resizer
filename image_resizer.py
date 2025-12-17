"""
Compatibility wrapper to launch the GUI entrypoint.
The application logic now lives in separate modules:
- config.py for shared configuration
- image_api.py for processing logic
- ui.py for the tkinter interface
"""

from main import main

if __name__ == "__main__":
    main()
