FROM python:3.11-slim

# Set up a new user named "user" with user ID 1000
# Hugging Face Spaces requires apps to run as a non-root user
RUN useradd -m -u 1000 user

# Switch to the "user" user
USER user

# Set home to the user's home directory
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH

# Set the working directory to the user's home directory
WORKDIR $HOME/app

# Copy the requirements file and install dependencies
COPY --chown=user ./requirements.txt $HOME/app/requirements.txt
RUN pip install --no-cache-dir --upgrade -r $HOME/app/requirements.txt

# Copy the current directory contents into the container at $HOME/app setting the owner to the user
COPY --chown=user . $HOME/app

# Hugging Face Spaces requires the app to run on port 7860
CMD ["uvicorn", "run:app", "--host", "0.0.0.0", "--port", "7860"]
