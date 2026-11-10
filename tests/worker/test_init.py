"""
Test Worker.

Test that the worker package exports the helpers that do not depend on a runner.
"""

import sap.worker
from sap.worker import crons, lambdas, packet, topics


def test_worker_exports() -> None:
    """Export the helpers of the modules of the package."""
    assert sap.worker.CronTask is crons.CronTask
    assert sap.worker.LambdaResponse is lambdas.LambdaResponse
    assert sap.worker.SignalPacket is packet.SignalPacket
    assert sap.worker.EventPublisher is packet.EventPublisher
    assert sap.worker.match_amqp_topics is topics.match_amqp_topics
    assert all(hasattr(sap.worker, name) for name in sap.worker.__all__)
