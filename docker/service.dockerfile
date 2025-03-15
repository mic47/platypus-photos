FROM node:22.6.0 AS typescript

RUN mkdir /app
WORKDIR /app

COPY package.json tsconfig.json yarn.lock ./
RUN yarn
COPY typescript/ typescript/
COPY css/ css/
COPY schema/ schema/
RUN yarn prod-build

FROM python:3.12

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
  cmake && \
  apt-get clean && rm -rf /var/lib/apt/lists/*

# Install face recognition module, this is expensive
RUN pip install face_recognition==1.3.0

RUN mkdir /app
WORKDIR /app

# Install ML libraries first and download models
RUN pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
RUN pip install \
  transformers==4.49.0 \
  ultralytics==8.3.91
RUN pip install opencv-python-headless==4.10.0.84
COPY download_models.py ./
RUN python download_models.py

# Install rest system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
  libimage-exiftool-perl \
  && \
  apt-get clean && rm -rf /var/lib/apt/lists/*

# Install rest of python dependencies
COPY requirements.txt ./
RUN pip install -r requirements.txt

## Environment is setup, PUT thing that changes often after this line

# Add built webpage
COPY --from=typescript /app/static /app/static
COPY pphoto/ pphoto/
COPY css/ css/
COPY schema/ schema/

# TODO: node dependencies
