"""Python setup file."""
import os
from pathlib import Path

from setuptools import setup

this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text()

# allow setup.py to be run from any path
os.chdir(os.path.normpath(os.path.join(os.path.abspath(__file__), os.pardir)))

version = "0.1.0"

setup(
    name="sap",
    version=version,
    packages=["sap"],
    include_package_data=True,
    license="COPYRIGHT @ Trellix",
    description="Library of re-usable utilities for python web apps.",
    long_description=long_description,
    url="https://github.com/trellixio/sap",
    author="Trellix Dev",
    author_email="contact@trellix.io",
    python_requires=">=3.9",
    install_requires=[
        "aioamqp~=0.15",
        "httpx~=0.23",
        "redis~=4.5",
        "celery~=5.2",
        "pydantic~=1.10",
        "fastAPI~=0.89",
        "itsdangerous~=2.1",
    ],
    classifiers=[
        "Environment :: Web Environment",
        "Framework :: FastAPI",
        "Intended Audience :: Developers",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.9",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Internet :: WWW/HTTP :: Dynamic Content",
    ],
)
