    # LARS Robot Server Installation

    ## Quick Installation

    Install with one command (downloads and unpacks):
    ```bash
    curl -sSL https://raw.githubusercontent.com/LARS-robots/public-install/main/robot_server/unpack.py | python3 - --user $(whoami)
    ```

    ## Manual Installation

    Download and run unpacker:
    ```bash
    wget https://raw.githubusercontent.com/LARS-robots/public-install/main/robot_server/unpack.py
    python3 unpack.py --user $(whoami)
    ```
    ---

    **Version**: dev-20251114-141147  
    **Build Date**: $(date -u +"%Y-%m-%d %H:%M:%S UTC")  
    **Source**: https://github.com/LARS-robots/LARS-gstreamer 
