    # LARS Robot Server Installation

    ## Quick Installation

    Install with one command (downloads and unpacks):
 
    curl -sSL https://raw.githubusercontent.com/LARS-robots/public-install/main/robot_server/unpack.py | sudo python3 - --user $(whoami)
                  ## Manual Installation

    Download and run unpacker:

    wget https://raw.githubusercontent.com/LARS-robots/public-install/main/robot_server/unpack.py
    sudo python3 unpack.py --user $(whoami)
                  ---

    **Version**: dev-20251219-075533  
    **Build Date**: $(date -u +"%Y-%m-%d %H:%M:%S UTC")  
    **Source**: https://github.com/LARS-robots/LARS-gstreamer 
