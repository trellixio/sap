"""
Samples.

Populate the database with dummy data for testing purposes.
"""
import beanie

from sap.beanie import DocMeta


class DummyDoc(beanie.Document, DocMeta):
    """Dummy document models used to populate the db for testing."""

    num: int

    class Settings:
        """Settings for the database collection."""

        name = "xlib_dummy"
