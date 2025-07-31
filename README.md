# Clinic AI Receptionist System - Docker Setup

A containerized clinic AI receptionist system that provides voice-based appointment management using LiveKit and FastAPI.

## 🏗️ Architecture

The system consists of two main services:

- **MCP Server**: FastAPI backend providing appointment management, database operations, and external service integrations
- **LiveKit Worker**: Voice AI agent handling real-time voice interactions and appointment booking

## 🚀 Quick Start

### Prerequisites

- Docker and Docker Compose installed
- `.env` file with required environment variables (see [Environment Variables](#environment-variables))

### Development Setup

1. **Clone and setup environment**:
   ```bash
   git clone <repository-url>
   cd clinic-ai-receptionist
   cp .env.example .env
   # Edit .env with your actual values
   ```

2. **Start services in development mode**:
   ```bash
   # Using development configuration
   docker-compose -f docker-compose.dev.yml up --build
   
   # Or using base configuration with override
   docker-compose up --build
   ```

3. **View logs**:
   ```bash
   docker-compose logs -f
   ```

### Production Deployment

1. **Setup environment**:
   ```bash
   cp .env.example .env
   # Configure production values in .env
   ```

2. **Deploy services**:
   ```bash
   docker-compose -f docker-compose.prod.yml up -d --build
   ```

3. **Monitor services**:
   ```bash
   docker-compose -f docker-compose.prod.yml ps
   docker-compose -f docker-compose.prod.yml logs --tail=100 -f
   ```

## 📋 Environment Variables

### Required Variables

Create a `.env` file with the following variables:

#### Database & Core Services
```bash
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_supabase_anon_key
GOOGLE_API_KEY=your_google_api_key
```

#### LiveKit Configuration
```bash
LIVEKIT_URL=wss://your-livekit-instance.livekit.cloud
LIVEKIT_API_KEY=your_livekit_api_key
LIVEKIT_API_SECRET=your_livekit_api_secret
```

#### Google Services
```bash
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
GOOGLE_REDIRECT_URI=your_google_redirect_uri
GEMINI_MODEL=gemini-2.0-flash
GEMINI_TEMPERATURE=0.7
```

#### Telephony (Plivo)
```bash
PLIVO_AUTH_ID=your_plivo_auth_id
PLIVO_AUTH_TOKEN=your_plivo_auth_token
PLIVO_PHONE_NUMBER=your_plivo_phone_number
```

#### Additional AI Services
```bash
DEEPGRAM_API_KEY=your_deepgram_api_key
ELEVEN_API_KEY=your_eleven_labs_api_key
OPENAI_API_KEY=your_openai_api_key
```

### Optional Variables (with defaults)
```bash
CLINIC_NAME=Your Clinic Name
CLINIC_ADDRESS=Your Clinic Address
CLINIC_TIMINGS=Monday to Saturday, 9:00 AM to 7:00 PM; Sunday closed
CLINIC_PHONE=+91-your-clinic-phone
CLINIC_SERVICES=General Medicine, Pediatrics, Endocrinology, Cardiology
```

## 🐳 Docker Commands

### Development Commands

```bash
# Start services with live code reloading
docker-compose -f docker-compose.dev.yml up --build

# Start in background
docker-compose -f docker-compose.dev.yml up -d --build

# View logs
docker-compose -f docker-compose.dev.yml logs -f

# Stop services
docker-compose -f docker-compose.dev.yml down

# Rebuild specific service
docker-compose -f docker-compose.dev.yml build mcp-server
```

### Production Commands

```bash
# Deploy production services
docker-compose -f docker-compose.prod.yml up -d --build

# Check service status
docker-compose -f docker-compose.prod.yml ps

# View logs
docker-compose -f docker-compose.prod.yml logs --tail=100 -f

# Update services
docker-compose -f docker-compose.prod.yml pull
docker-compose -f docker-compose.prod.yml up -d --build

# Stop services
docker-compose -f docker-compose.prod.yml down
```

### Maintenance Commands

```bash
# Clean up unused containers and images
docker system prune -a

# View container resource usage
docker stats

# Execute commands in running containers
docker-compose exec mcp-server bash
docker-compose exec livekit-worker bash

# Check health status
docker-compose exec mcp-server curl http://localhost:8000/health
docker-compose exec livekit-worker python health_check_livekit.py
```

## 🔍 Service Details

### MCP Server
- **Port**: 8000
- **Health Check**: `GET /health`
- **Purpose**: Appointment management, database operations, external API integrations
- **Dependencies**: Supabase, Google APIs, Plivo

### LiveKit Worker
- **Purpose**: Voice AI interactions, real-time appointment booking
- **Dependencies**: LiveKit Cloud, MCP Server
- **Health Check**: Process and connectivity validation

## 📊 Monitoring & Logging

### Health Checks

Both services include comprehensive health checks:

```bash
# Check MCP server health
curl http://localhost:8000/health

# Check LiveKit worker health (inside container)
docker-compose exec livekit-worker python health_check_livekit.py
```

### Log Management

Logs are stored in the `./logs` directory and mounted into containers:

```bash
# View real-time logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f mcp-server
docker-compose logs -f livekit-worker

# View log files directly
tail -f logs/*.log
```

### Resource Monitoring

```bash
# Monitor container resource usage
docker stats

# View detailed container information
docker-compose ps
docker inspect <container-name>
```

## 🔧 Troubleshooting

### Common Issues

#### 1. Environment Variable Errors
```bash
# Validate environment variables
docker-compose exec mcp-server python validate_env.py mcp-server
docker-compose exec livekit-worker python validate_env.py livekit-worker
```

#### 2. Service Connectivity Issues
```bash
# Check network connectivity
docker network ls
docker network inspect clinic-network

# Test internal service communication
docker-compose exec livekit-worker curl http://mcp-server:8000/health
```

#### 3. Database Connection Issues
```bash
# Check Supabase connectivity
docker-compose exec mcp-server python -c "
from supabase import create_client
import os
client = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_KEY'))
print('Database connection successful')
"
```

#### 4. LiveKit Connection Issues
```bash
# Verify LiveKit configuration
docker-compose exec livekit-worker python -c "
import os
print(f'LiveKit URL: {os.getenv(\"LIVEKIT_URL\")}')
print(f'API Key: {os.getenv(\"LIVEKIT_API_KEY\")[:10]}...')
"
```

### Debug Mode

Enable debug mode for detailed logging:

```bash
# Development with debug logging
DEBUG=true LOG_LEVEL=DEBUG docker-compose -f docker-compose.dev.yml up
```

### Container Shell Access

```bash
# Access MCP server container
docker-compose exec mcp-server bash

# Access LiveKit worker container
docker-compose exec livekit-worker bash
```

## 🔒 Security Considerations

### Production Security

1. **Environment Variables**: Never commit `.env` files to version control
2. **Network Isolation**: Services communicate via internal Docker network
3. **Resource Limits**: Production configuration includes CPU and memory limits
4. **Security Options**: Containers run with security hardening options
5. **Read-only Filesystem**: Where possible, containers use read-only filesystems

### Secrets Management

For production deployments, consider using Docker secrets or external secret management:

```bash
# Example using Docker secrets
echo "your_secret_value" | docker secret create supabase_key -
```

## 📈 Scaling

### Horizontal Scaling

Scale LiveKit workers for increased capacity:

```bash
# Scale LiveKit workers
docker-compose -f docker-compose.prod.yml up -d --scale livekit-worker=3
```

### Load Balancing

For production deployments, consider adding a load balancer:

```yaml
# Example nginx load balancer configuration
services:
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
    depends_on:
      - mcp-server
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes and test with Docker
4. Submit a pull request

## 📄 License

[Your License Here]

## 🆘 Support

For issues and questions:
1. Check the [Troubleshooting](#troubleshooting) section
2. Review container logs: `docker-compose logs -f`
3. Validate environment: `python validate_env.py <service-type>`
4. Open an issue with detailed error information