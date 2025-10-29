"""
Application Performance Monitoring.

Used for testing if database queries are resource efficient.
"""

import pymongo.monitoring


class CommandLogger(pymongo.monitoring.CommandListener):
    """Subclass CommandListener to be notified whenever a command is executed.

    https://motor.readthedocs.io/en/stable/examples/monitoring.html
    https://pymongo.readthedocs.io/en/stable/api/pymongo/monitoring.html
    """

    events: list[pymongo.monitoring.CommandStartedEvent] = []

    def started(self, event: pymongo.monitoring.CommandStartedEvent) -> None:
        """Log all queries to DB when it starts."""
        self.events.append(event)
        # logger.debug(
        #     "Command %s with request id %s started on server %s",
        #     str(event.command),
        #     str(event.request_id),
        #     str(event.connection_id),
        # )

    def succeeded(self, event: pymongo.monitoring.CommandSucceededEvent) -> None:
        """Log successful queries to DB."""

    def failed(self, event: pymongo.monitoring.CommandFailedEvent) -> None:
        """Log failed queries to DB."""

    def clear(self) -> None:
        """Erase the events buffer."""
        self.events = []

    def get_events_count(self) -> int:
        """Return the numbers of events in buffer."""
        return len(self.events)


apm = CommandLogger()
pymongo.monitoring.register(apm)
