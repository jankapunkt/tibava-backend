# For more information, please refer to https://aka.ms/vscode-docker-python
FROM ubuntu:20.04

RUN DEBIAN_FRONTEND=noninteractive apt update --fix-missing -y
RUN DEBIAN_FRONTEND=noninteractive apt upgrade -y 
RUN DEBIAN_FRONTEND=noninteractive apt install python3-pip npm git -y
RUN DEBIAN_FRONTEND=noninteractive apt install libmariadbclient-dev-compat imagemagick -y


EXPOSE 5000

# Keeps Python from generating .pyc files in the container
ENV PYTHONDONTWRITEBYTECODE=1

# Turns off buffering for easier container logging
ENV PYTHONUNBUFFERED=1

# Install pip requirements
COPY requirements.txt .
RUN python3 -m pip install -r requirements.txt

WORKDIR /app
COPY . /app

# Switching to a non-root user, please refer to https://aka.ms/vscode-docker-python-user-rights
RUN useradd appuser && chown -R appuser /app
USER appuser

# During debugging, this entry point will be overridden. For more information, please refer to https://aka.ms/vscode-docker-python-debug
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "backend:app", "--log-level debug"]
# CMD ["python", "backend.py"]
