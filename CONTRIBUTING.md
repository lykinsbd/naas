# Contributing to NAAS

PRs are welcome!

## Dev Environment

The dev environment of NAAS can be instantiated by doing the following:

1. Clone down the NAAS repo to your device:
    ```git clone git@github.com:lykinsbd/naas.git```
2. Create a Python virtual environment in that folder:
    ```python3 -m venv naas```
3. Change to that directory and activate the virtual environment:
    ```source bin/activate```
4. Install the requirements:
    ```pip install -r requirements.txt```
5. Make any changes you desire.
6. Launch a local Redis container:
    ```docker run -p 6379:6379 redis:5-alpine```
7. Launch a local worker process:
    ```python worker.py 2 -l DEBUG -s 1```
8. Launch the Gunicorn server:
    ```gunicorn -c gunicorn.py naas.app:app```
9. Test your changes...
