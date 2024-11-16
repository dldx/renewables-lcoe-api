# Use the official Python 3.10.9 image
FROM python:3.12-slim-bookworm
# The installer requires curl (and certificates) to download the release archive
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates

# Download the latest installer
ADD https://astral.sh/uv/install.sh /uv-installer.sh

# Run the installer then remove it
RUN sh /uv-installer.sh && rm /uv-installer.sh

# Ensure the installed binary is on the `PATH`
ENV PATH="/root/.local/bin/:$PATH"

# Copy the current directory contents into the container at .
COPY . .

# Set the working directory to /
WORKDIR /

RUN uv sync --frozen

# Start the FastAPI app on port 7860, the default port expected by Spaces
CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]