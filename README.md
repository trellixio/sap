[![Python 3.12](https://img.shields.io/badge/python-3.12-yellow.svg)](https://www.python.org/downloads/release/python-312/)

# SAP
Library of re-usable utilities for python web apps.
Published as `sapx`; import it as `sap`.

## 🔨 Installing

### Python 3.12
Before getting started, ensure that [Python 3.12](https://www.python.org/) is installed on your computer.

### MongoDB
MongoDB is a document-oriented database that use JSON-like documents to store data.
You will need to install MongoDB 8.0 [locally](https://www.mongodb.com/docs/manual/installation/)
or sign up for a free hosted one with [MongoDB Atlas](https://www.mongodb.com/pricing).
Once you install MongoDB, make sure to create a database.

### Redis
Redis is used for cache and as the Celery result backend.
You will need to install Redis 8 [locally](https://redis.io/docs/latest/operate/oss_and_stack/install/install-redis/).

### RabbitMQ
RabbitMQ is the message broker used by Celery workers.
You will need to install RabbitMQ 4.1 [locally](https://www.rabbitmq.com/docs/download).

### Steps
Clone the repo and open a terminal at the root of the cloned repo.

1. Setup a virtual env. Only do this on your first run.
```shell
python3.12 -m venv .venv
```

2. Activate the virtualenv
```shell
source .venv/bin/activate
```

3. Install all dependencies:
```shell
pip install -r requirements-dev.txt
```

4. Set up pre-commit
```shell
pre-commit install
```

5. Init environment variables. Duplicate the env template file:
```shell
cp ./.env.tpl ./.env
```
Open `.env` file with a text editor and update the env vars as needed.
Set `APP_SETTINGS_CRYPTO_SECRET`. MongoDB, Redis, and RabbitMQ hosts
must match the services above. `APP_SETTINGS_TOKENIFY__APP_DOMAIN` is required.


## 🖌 Formatting

Keep in mind that those are automated formatting assistant tools.
They will not always give the best result, as they just apply
rules blindly. As a developer you still have the responsibility to
ensure that the code is formatted with perfection.

- Use black to format the code
From the project root run:
```shell
black .
```

- Use isort to sort the import
From the project root run:
```shell
isort .
```


## 🧽 Linting

Linters are useful to ensure that your code quality matches with standards.

- Running pre-commit on the project to run all linters.
```shell
pre-commit run --all-files
```

- Use pylint to check for common mistakes.
From the project root, run:
```shell
pylint AppMain sap tests
```

- Use mypy to check for typing issues.
From the project root, run:
```shell
mypy .
```

- Use pydocstyle to check for documentation issues.
From the project root, run:
```shell
pydocstyle .
```


## 🧪 Testing

Tests are run using the pytest library.
From the project root, run:
```shell
pytest
```
