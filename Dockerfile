# Use the official image as a parent image.
FROM python:2.7

# Set the working directory.
WORKDIR /usr/src/app

RUN python -m pip install --upgrade pip
RUN python -m pip install pathlib
RUN python -m pip install pyusb
RUN python -m pip install pyserial

# Copy the file from your host to your current location.
COPY . .

# Run the command inside your image filesystem.
# RUN npm install

# Add metadata to the image to describe which port the container is listening on at runtime.
# EXPOSE 8080

# Run the specified command within the container.
# CMD [ "python", "antifier.py", "-l", "-c", "power_calc_factors_fortius.txt", "-s" ]

# Copy the rest of your app's source code from your host to your image filesystem.
# COPY . .
