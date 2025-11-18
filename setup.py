"""Python setup file."""

import os

from setuptools import find_packages, setup

# this_directory = Path(__file__).parent
# long_description = (this_directory / "README.md").read_text()
LONG_DESCRIPTION = "Library of re-usable utilities for python web apps."

# allow setup.py to be run from any path
os.chdir(os.path.normpath(os.path.join(os.path.abspath(__file__), os.pardir)))

VERSION = "0.4.4"

setup(
    name="sapx",
    version=VERSION,
    packages=find_packages(include=("sap.*", "sap")),
    package_data={"sap": ["py.typed"]},
    include_package_data=True,
    license="COPYRIGHT @ Trellix",
    description="Library of re-usable utilities for python web apps.",
    long_description=LONG_DESCRIPTION,
    url="https://github.com/trellixio/sap",
    author="Trellix Dev",
    author_email="contact@trellix.io",
    python_requires=">=3.12",
    install_requires=[
        "aioamqp~=0.15",
        "httpx~=0.28",
        "PyJWT~=2.10",
        "typing-extensions~=4.15",
        "itsdangerous~=2.2",
        "passlib~=1.7",
        "PyYAML~=6.0",
        "pymongo~=4.9",
        "motor~=3.6",
        "pydantic~=2.9.2",
        "beanie~=1.27.0",
        "fastapi~=0.120",
        "redis~=5.1",
        "celery~=5.4",
    ],
    classifiers=[
        "Environment :: Web Environment",
        "Framework :: FastAPI",
        "Intended Audience :: Developers",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.12",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Internet :: WWW/HTTP :: Dynamic Content",
    ],
)
