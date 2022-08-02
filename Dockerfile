# Instructions from https://fastapi.tiangolo.com/deployment/docker/
FROM python:3.9
WORKDIR /code
COPY ./requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt
COPY ./app /code/app
CMD ["uvicorn", "app.api:app", "--proxy-headers", "--host", "0.0.0.0", "--port", "8000"]
