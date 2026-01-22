import subprocess
import re

def get_chrome_version():
    try:
        output = subprocess.check_output(
            r'reg query "HKEY_CURRENT_USER\Software\Google\Chrome\BLBeacon" /v version',
            shell=True, encoding='utf-8'
        )
        match = re.search(r"version\s+REG_SZ\s+([\d.]+)", output)
        if match:
            return match.group(1)
    except Exception:
        pass
    return None

def get_chrome_major_version():
    version = get_chrome_version()
    if version:
        return int(version.split('.')[0])
    return None