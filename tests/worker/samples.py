"""
Samples.

Populate the database with dummy data for testing purposes.
"""
from sap.beanie import Document


class DummyDoc(Document):
    """Dummy document models used to populate the db for testing."""

    num: int

    class Settings:
        """Settings for the database collection."""

        name = "xlib_dummy"
