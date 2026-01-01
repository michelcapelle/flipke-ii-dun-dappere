import pika
import sys

print("Testing RabbitMQ connection...")
try:
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(
            host='localhost',
            port=5672,
            credentials=pika.PlainCredentials('admin', 'admin'),
            heartbeat=600,
            blocked_connection_timeout=300
        )
    )
    print("✓ Connected to RabbitMQ")
    channel = connection.channel()
    print("✓ Channel created")
    result = channel.queue_declare(queue='tasks', durable=True)
    print(f"✓ Queue 'tasks' declared")
    print(f"  - Messages ready: {result.method.message_count}")
    print(f"  - Consumers: {result.method.consumer_count}")
    channel.basic_qos(prefetch_count=1)
    print("✓ QoS set")

    def test_callback(ch, method, properties, body):
        print(f"\n✓ Received message: {body.decode()}")
        ch.basic_ack(delivery_tag=method.delivery_tag)
    
    channel.basic_consume(
        queue='tasks',
        on_message_callback=test_callback
    )
    print("✓ Consumer registered")
    print("\n👂 Now consuming messages from 'tasks' queue...")
    print("   Press CTRL+C to stop\n")    
    channel.start_consuming()
except pika.exceptions.AMQPConnectionError as e:
    print(f"❌ Connection failed: {str(e)}")
    print("   Make sure RabbitMQ is running: docker-compose up -d")
    sys.exit(1)
except KeyboardInterrupt:
    print("\n\n👋 Test stopped")
    try:
        connection.close()
    except:
        pass
    sys.exit(0)
except Exception as e:
    print(f"❌ Error: {str(e)}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
