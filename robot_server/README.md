    # LARS Robot Server Installation

    ## Quick Installation
    Install with one command (downloads and unpacks):
 
    curl -sSL https://raw.githubusercontent.com/LARS-robots/public-install/main/robot_server/unpack.py | sudo python3 - --user runner
  
    ## Manual Installation
    Download and run unpacker:

    wget https://raw.githubusercontent.com/LARS-robots/public-install/main/robot_server/unpack.py
    sudo python3 unpack.py --user runner
    
    ## Code Update Only (No Installation)
    For updating code without reinstalling systemd service:
    
    wget https://raw.githubusercontent.com/LARS-robots/public-install/main/robot_server/update.py
    python3 update.py /path/to/install/dir
                  ---

    **Version**: dev-20260202-103148  
    **Build Date**: 2026-02-02 10:31:53 UTC  
    **Source**: https://github.com/LARS-robots/LARS-gstreamer 
