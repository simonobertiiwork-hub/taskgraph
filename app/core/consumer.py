import pika

connection = pika.BlockingConnection(
    pika.ConnectionParameters("rabbitmq")
)

channel = connection.channel()

channel.queue_declare(
    queue="task_events",
    durable=True,
)


def callback(ch, method, properties, body):
    print(f"Received: {body.decode()}")

    ch.basic_ack(
        delivery_tag=method.delivery_tag
    )


channel.basic_consume(
    queue="task_events",
    on_message_callback=callback,
)

print("Waiting messages...")
channel.start_consuming()