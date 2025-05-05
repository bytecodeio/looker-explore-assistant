# Use the official Python image as the base image
FROM python:3.9

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install any needed packages specified in requirements.txt
# use cache-dir to cache the dependencies
# and avoid re-downloading them if they haven't changed
RUN pip install --cache-dir=./cache/pip -r requirements.txt

# Make port 8080 available to the world outside this container
EXPOSE 8080

# Define environment variable
ENV PORT=8080
ENV FUNCTION_TARGET=cloud_function_entrypoint

# Run the function using functions-framework
CMD exec functions-framework --target=${FUNCTION_TARGET} --port=${PORT}