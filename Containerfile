# Using the official Fedora 39 Python 3.9 image
FROM registry.fedoraproject.org/f39/python3:3.9

# Set the working directory
WORKDIR /app

# Fedora images usually use the '1001' user for OpenShift compatibility
# We switch to root just to install system-level dependencies, then back to 1001
USER 0

# Install PostgreSQL development headers (needed for psycopg2)
RUN dnf install -y gcc libpq-devel && dnf clean all

# Switch back to the non-root user (Standard for OpenShift)
USER 1001

# Copy and install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application code
COPY . .

# Expose the common OpenShift port
EXPOSE 8080

# Start your app (assuming your entry file is app.py)
CMD ["python", "app.py"]