ARG BUILD_FROM
FROM $BUILD_FROM

# Install Python, Pip, and JQ (for parsing config)
RUN apk add --no-cache python3 py3-pip jq

# Set working directory
WORKDIR /app

# Copy requirement file first to leverage cache
COPY requirements.txt .

# Install Python dependencies
RUN pip3 install --no-cache-dir -r requirements.txt --break-system-packages

# Copy the rest of the application
COPY . .

# Make run script executable
COPY run.sh /
RUN chmod a+x /run.sh

CMD [ "/run.sh" ]
