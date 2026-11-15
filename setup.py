# This runs before the Streamlit app starts on Streamlit Cloud.
# It installs Deno so yt-dlp can solve YouTube's JS signature challenges.

import subprocess
import os
import sys

DENO_BIN = os.path.expanduser("~/.deno/bin/deno")

if not os.path.exists(DENO_BIN):
    try:
        subprocess.run(
            "curl -fsSL https://deno.land/install.sh | sh",
            shell=True, check=True
        )
    except Exception as e:
        print(f"[setup] Deno install failed (non-fatal): {e}", file=sys.stderr)

# Add deno to PATH for this process
deno_dir = os.path.expanduser("~/.deno/bin")
if deno_dir not in os.environ.get("PATH", ""):
    os.environ["PATH"] = deno_dir + ":" + os.environ.get("PATH", "")
