# Use the official Python 3.10.9 image
FROM python:3.10.9

# Copy the current directory contents into the container at .
COPY . .

# Set the working directory to /
WORKDIR /

# Install requirements.txt
RUN pip install uv


# Start the FastAPI app on port 7860, the default port expected by Spaces
CMD ["uv" "run" "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]