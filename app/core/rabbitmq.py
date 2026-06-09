import pika


def publish_message(message: str) -> None:

    connection = pika.BlockingConnection(
        pika.ConnectionParameters("rabbitmq")
    )

    channel = connection.channel()

    channel.queue_declare(
        queue="task_events",
        durable=True
    )

    channel.basic_publish(
        exchange="",
        routing_key="task_events",
        body=message
    )

    connection.close()