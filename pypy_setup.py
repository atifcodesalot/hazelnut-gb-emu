

import pathlib
import urllib.request
import urllib.parse
import subprocess
import shutil
import os
import hashlib
import platform
import logging

logging.basicConfig(level=logging.INFO)
setup_logger = logging.getLogger("PyPy-setup")

PLATFORM = platform.system().upper()

if PLATFORM not in {"WINDOWS", "LINUX", "DARWIN"}:
    raise RuntimeError(f"Unsupported platform: {PLATFORM}")

ARCHITECTURE = platform.machine().lower()

PYPY_DOWNLOADS = {
    "WINDOWS": {
        "amd64": [
            "https://downloads.python.org/pypy/pypy3.11-v7.3.23-win64.zip",
            "948b8ea58dea5b9917210fe4afd242c788fbfaba1c3f1a25e696a404f703389a",
        ],
        "x86_64": [
            "https://downloads.python.org/pypy/pypy3.11-v7.3.23-win64.zip",
            "948b8ea58dea5b9917210fe4afd242c788fbfaba1c3f1a25e696a404f703389a",
        ],
    },

    "LINUX": {
        "amd64": [
            "https://downloads.python.org/pypy/pypy3.11-v7.3.23-linux64.tar.bz2",
            "16f9f56e82d1f4ec95a324c1a8cacfd78afc7f0656c0a809a18725ef4391453a",
        ],
        "x86_64": [
            "https://downloads.python.org/pypy/pypy3.11-v7.3.23-linux64.tar.bz2",
            "16f9f56e82d1f4ec95a324c1a8cacfd78afc7f0656c0a809a18725ef4391453a",
        ],
        "arm64": [
            "https://downloads.python.org/pypy/pypy3.11-v7.3.23-aarch64.tar.bz2",
            "5433ac0ad526aeb35025ef8509bed65cd62ea35cb9e21ac649c69a5eff4eecb6",
        ],
        "aarch64": [
            "https://downloads.python.org/pypy/pypy3.11-v7.3.23-aarch64.tar.bz2",
            "5433ac0ad526aeb35025ef8509bed65cd62ea35cb9e21ac649c69a5eff4eecb6",
        ],
        "x86": [
            "https://downloads.python.org/pypy/pypy3.11-v7.3.23-linux32.tar.bz2",
            "c7e2ffb173dcadbe4708a2e606e0b705474c1c33f25a09a4084f265d538172e4",
        ],
        "i386": [
            "https://downloads.python.org/pypy/pypy3.11-v7.3.23-linux32.tar.bz2",
            "c7e2ffb173dcadbe4708a2e606e0b705474c1c33f25a09a4084f265d538172e4",
        ],
        "i486": [
            "https://downloads.python.org/pypy/pypy3.11-v7.3.23-linux32.tar.bz2",
            "c7e2ffb173dcadbe4708a2e606e0b705474c1c33f25a09a4084f265d538172e4",
        ],
        "i586": [
            "https://downloads.python.org/pypy/pypy3.11-v7.3.23-linux32.tar.bz2",
            "c7e2ffb173dcadbe4708a2e606e0b705474c1c33f25a09a4084f265d538172e4",
        ],
        "i686": [
            "https://downloads.python.org/pypy/pypy3.11-v7.3.23-linux32.tar.bz2",
            "c7e2ffb173dcadbe4708a2e606e0b705474c1c33f25a09a4084f265d538172e4",
        ],
    },

    "DARWIN": {
        "amd64": [
            "https://downloads.python.org/pypy/pypy3.11-v7.3.23-macos_x86_64.tar.bz2",
            "c95363c4e87235d11a6cec8128239c291b1eb67a752778fbcfe029a71da82b5e",
        ],
        "x86_64": [
            "https://downloads.python.org/pypy/pypy3.11-v7.3.23-macos_x86_64.tar.bz2",
            "c95363c4e87235d11a6cec8128239c291b1eb67a752778fbcfe029a71da82b5e",
        ],
        "arm64": [
            "https://downloads.python.org/pypy/pypy3.11-v7.3.23-macos_arm64.tar.bz2",
            "4747b3aceba4c1c6104cddc0fe5ea302101d32955f0957347b9ecc4fbd7aed05",
        ],
        "aarch64": [
            "https://downloads.python.org/pypy/pypy3.11-v7.3.23-macos_arm64.tar.bz2",
            "4747b3aceba4c1c6104cddc0fe5ea302101d32955f0957347b9ecc4fbd7aed05",
        ],
    },
}

INPUT = "Would you like to install the PyPy runtime? [y/n]"

DOWNLOAD_URL, CHECKSUM = PYPY_DOWNLOADS[PLATFORM][ARCHITECTURE]

ZIP_NAME = pathlib.PurePosixPath(
    urllib.parse.urlsplit(DOWNLOAD_URL).path
).name


def checksum_arc(zip_bytes):
    hash = hashlib.sha256(zip_bytes).hexdigest()
    return hash == CHECKSUM


def install_pypy():
    if not os.path.exists(".runtime"):
        os.mkdir(".runtime")
    else:
        setup_logger.info(".runtime directory already exists.")
    os.chdir(".runtime")
    setup_logger.info(
        f"Now installing pypy for {PLATFORM + ' ' + ARCHITECTURE}... This may take a couple of seconds.")

    fn = ZIP_NAME
    if os.path.exists(fn):
        setup_logger.info(f"{fn} already exists!")
    else:
        urllib.request.urlretrieve(
            url=DOWNLOAD_URL, filename=fn)
        setup_logger.info(f"{fn} installed, now checking file signature...")
    arc = open(fn, "rb")

    if not checksum_arc(zip_bytes=arc.read()):
        raise RuntimeError("Checksum mismatch")
    setup_logger.info(f"{fn} checksum correct.")
    setup_logger.info(f"Now unpacking {fn}...")
    shutil.unpack_archive(fn, extract_dir=".")
    arc.close()
    os.chdir("..")
    return True


def find_pypy3():
    fex = "pypy3.exe" if PLATFORM == "WINDOWS" else "pypy"
    extract_dir = pathlib.Path(ZIP_NAME)\
        .stem.split('.tar')[0]
    pypy_dir = os.path.join(".runtime", extract_dir)
    if PLATFORM == "LINUX":
        pypy = os.path.join(pypy_dir, "bin", fex)
    elif PLATFORM == "WINDOWS":
        pypy = os.path.join(pypy_dir, fex)

    return pypy


def install_packages(pypy):
    result = subprocess.run(
        [pypy, "-c", "import pygame"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    if result.returncode != 0:
        subprocess.run([pypy, "-m", "ensurepip"], check=True)
        subprocess.run([
            pypy, "-m", "pip", "install",
            "--only-binary=:all:",
            "pygame-ce==2.5.8",
        ], check=True)


def rerun(pypy):
    subprocess.run([
        pypy, "-m", "hazelnut_gb_emu"
    ], check=True)


def try_pypy():
    installed = False
    if os.path.exists(".runtime"):
        # runtime path exists
        pypy = find_pypy3()
        installed = os.path.exists(pypy)

    if not installed:
        logging.info("Using the PYPY runtime is highly recommended.")
        logging.info(INPUT)
        inp = input()
        if inp.strip().lower() in ["y", "yes", "ya", "yeah", "yy", "yyy"]:
            if install_pypy():
                pypy = find_pypy3()
                install_packages(pypy)
                rerun(pypy)
                exit()
        else:
            return

    logging.info("You have PyPy installed, using it.")
    install_packages(pypy)
    rerun(pypy)
    exit()
