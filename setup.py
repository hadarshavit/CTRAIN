from pathlib import Path
from setuptools import setup, find_packages
from setuptools.command.install import install
import subprocess
import os

def run_command(command, cwd=None):
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=cwd, env=os.environ)
    print(f"Running command: {' '.join(command)}")
    print(f"Return code: {result.returncode}")
    print(f"stdout: {result.stdout}")
    print(f"stderr: {result.stderr}")
    result.check_returncode()

def install_abcrown(installation_path):
    run_command(["touch", "__init__.py"], cwd=installation_path)
    run_command(["touch", "__init__.py"], cwd=f"{installation_path}/complete_verifier/input_split")

class CustomInstallCommand(install):
    def run(self):
        run_command(["pip", "install", "--no-deps", "git+https://github.com/KaidiXu/onnx2pytorch@8447c42c3192dad383e5598edc74dddac5706ee2"])
        run_command(["pip", "install", "--no-deps", "git+https://github.com/Verified-Intelligence/auto_LiRPA.git@cf0169ce6bfb4fddd82cfff5c259c162a23ad03c"])
        install.run(self)
        install_abcrown("./CTRAIN/verification_systems/abCROWN")

setup(
    name="CTRAIN",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
    ],
    cmdclass={
        "install": CustomInstallCommand,
    },
    package_data={
        "CTRAIN": ["verification_systems/abCROWN/*"],
        "": ["onnx2pytorch/*", "auto_LiRPA/*"]
    },
    include_package_data=True,
)
