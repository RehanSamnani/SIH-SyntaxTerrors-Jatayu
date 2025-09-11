## Production Deployment with TLS and Nginx

### TLS Setup with Nginx Reverse Proxy

1. Install Nginx:
```bash
sudo apt update
sudo apt install nginx certbot python3-certbot-nginx
```

2. Configure Nginx as reverse proxy (`/etc/nginx/sites-available/drone-api`):
```nginx
server {
    listen 80;
    server_name api.your-domain.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

3. Enable the site and get SSL certificate:
```bash
sudo ln -s /etc/nginx/sites-available/drone-api /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
sudo certbot --nginx -d api.your-domain.com
```

4. Security headers (add to Nginx config):
```nginx
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
add_header X-Frame-Options "SAMEORIGIN" always;
add_header X-XSS-Protection "1; mode=block" always;
add_header X-Content-Type-Options "nosniff" always;
add_header Content-Security-Policy "default-src 'self'; img-src 'self' data: https:; style-src 'self' 'unsafe-inline';" always;
```

5. Optional: Rate limiting in Nginx:
```nginx
http {
    limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;
    
    server {
        location / {
            limit_req zone=api_limit burst=20 nodelay;
            proxy_pass http://localhost:8000;
            # ... other proxy settings ...
        }
    }
}
```

6. Update your environment variables:
```bash
FRONTEND_URL=https://your-frontend-domain.com
```

### Production Deployment Steps

1. Set up Python environment:
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

2. Set up PostgreSQL:
```bash
sudo apt install postgresql postgresql-contrib
sudo -u postgres createuser --interactive
sudo -u postgres createdb drone_system
```

3. Create systemd service (`/etc/systemd/system/drone-api.service`):
```ini
[Unit]
Description=Drone Relief API
After=network.target

[Service]
User=ubuntu
Group=ubuntu
WorkingDirectory=/path/to/app
Environment="PATH=/path/to/app/venv/bin"
Environment="DATABASE_URL=postgresql://user:password@localhost/drone_system"
Environment="JWT_SECRET_KEY=your-secret-key"
ExecStart=/path/to/app/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
Restart=always

[Install]
WantedBy=multi-user.target
```

4. Start and enable the service:
```bash
sudo systemctl start drone-api
sudo systemctl enable drone-api
```

### Security Best Practices

1. Firewall configuration:
```bash
sudo ufw allow ssh
sudo ufw allow 'Nginx Full'
sudo ufw enable
```

2. Secure PostgreSQL:
```bash
# Edit pg_hba.conf to use scram-sha-256
sudo nano /etc/postgresql/13/main/pg_hba.conf
```

3. Regular updates:
```bash
sudo apt update
sudo apt upgrade
sudo apt autoremove
```

4. Monitoring setup:
```bash
# Install monitoring tools
sudo apt install prometheus node-exporter
```

### Backup Strategy

1. Database backups:
```bash
# Create backup script
sudo nano /usr/local/bin/backup-db.sh

#!/bin/bash
pg_dump -U username drone_system | gzip > /path/to/backups/drone_$(date +%Y%m%d).sql.gz

# Make executable
sudo chmod +x /usr/local/bin/backup-db.sh

# Add to crontab
0 0 * * * /usr/local/bin/backup-db.sh
```

2. Log rotation (`/etc/logrotate.d/drone-api`):
```
/path/to/app/logs/*.log {
    daily
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 ubuntu ubuntu
    sharedscripts
    postrotate
        systemctl reload drone-api
    endscript
}
```

### Monitoring and Alerts

1. Basic health check:
```bash
# Monitor API health
curl -f https://api.your-domain.com/health || notify-admin.sh

# Add to crontab
*/5 * * * * /path/to/health-check.sh
```

2. Resource monitoring:
```bash
# Install monitoring stack
sudo apt install prometheus grafana
```

### Scaling Considerations

1. Use connection pooling with SQLAlchemy
2. Configure proper worker count based on CPU cores
3. Set up caching if needed (Redis)
4. Consider load balancing for high availability