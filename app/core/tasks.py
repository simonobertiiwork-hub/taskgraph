from app.core.celery_app import celery_app


@celery_app.task
def process_task(task_id: int):
    print(f"Processing task {task_id}")

    return {
        "task_id": task_id,
        "status": "completed",
    }