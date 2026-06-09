from celery import Celery

celery_app = Celery(
    "taskgraph",
    broker="amqp://guest:guest@rabbitmq:5672//",
    backend="rpc://",
)

celery_app.autodiscover_tasks(
    ["app.core"]
)