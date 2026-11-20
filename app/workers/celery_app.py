import os, time
from celery import Celery

# Initializing celery with Redis as broker and result backend
app = Celery(
    'banana_chain',
    broker=os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/1")
)

app.conf.update(
    task_acks_late=True, 
    worker_prefetch_multiplier=1, 
    task_soft_time_limit=int(os.getenv("CELERY_SOFT_TIME_LIMIT", 300)), 
    task_time_limit=int(os.getenv("CELERY_HARD_TIME_LIMIT", 360))
    )

@app.task
def ping_task(delay=0):
    time.sleep(delay)
    return "banana ping"