FROM nvcr.io/nvidia/tensorflow:20.12-tf2-py3
COPY requirements.txt /tmp
RUN apt update && apt install -y libgl1-mesa-glx
RUN python -m pip install --upgrade pip && \
    python -m pip install -r /tmp/requirements.txt
