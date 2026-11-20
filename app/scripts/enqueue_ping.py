import sys
from app.workers.celery_app import ping_task

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sleep_seconds=0
    else: 
        sleep_seconds = int(sys.argv[1])

    result = ping_task.delay(sleep_seconds)

    print(result.id)

    print(result.get(timeout=sleep_seconds+2))

