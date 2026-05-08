from enum import StrEnum


class QueueName(StrEnum):
    """
    All arq job queues in this application.

    Each queue is consumed by a dedicated WorkerSettings in registry.py.
    Add new names here only when a feature is ready to enqueue to them.
    """

    notifications = "boreas:notifications"
    media = "boreas:media"
    compute = "boreas:compute"
    analytics = "boreas:analytics"
