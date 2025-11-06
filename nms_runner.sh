#/bin/bash

if [ "$(docker ps -q -f name=my-redis)" ]; then
    echo "Redis container 'my-redis' is already running."
else
    # Check if the container exists but is stopped
    if [ "$(docker ps -aq -f status=exited -f name=my-redis)" ]; then
        echo "Starting existing Redis container 'my-redis'."
        docker start my-redis
    else
        echo "Running new Redis container 'my-redis'."
        docker run -d --name my-redis -p 6379:6379 redis
    fi
fi

celery -A app.celery_app worker --loglevel=INFO