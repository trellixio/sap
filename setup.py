"""Python setup file."""
import os
from pathlib import Path

from setuptools import find_packages, setup

this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text()

# allow setup.py to be run from any path
os.chdir(os.path.normpath(os.path.join(os.path.abspath(__file__), os.pardir)))

VERSION = "0.1.5"

setup(
    name="sapx",
    version=VERSION,
    packages=find_packages(include=("sap.*", "sap")),
    package_data={"sap": ["py.typed"]},
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
        "PyJWT~=2.6",
        "fastAPI~=0.89",
        "itsdangerous~=2.1",
        "beanie~=1.15",
        "motor~=3.1",
        "sqlmodel~=0.0",
        "typing-extensions~=4.5",
        "PyYAML~=6.0",
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
