FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

WORKDIR /app

COPY launch_desk/requirements.txt /app/launch_desk/requirements.txt
RUN python -m pip install --upgrade pip \
    && python -m pip install --no-cache-dir -r /app/launch_desk/requirements.txt

COPY launch_desk /app/launch_desk
COPY scripts/run_launch_desk_backend.py /app/scripts/run_launch_desk_backend.py

EXPOSE 8080

CMD python scripts/run_launch_desk_backend.py --host 0.0.0.0 --port ${PORT}
