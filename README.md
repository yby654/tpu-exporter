cat > README.md << 'EOF'
# TPU Exporter for GKE

Prometheus exporter for Google Kubernetes Engine (GKE) TPU metrics.

## Features

- Real-time TPU node metrics collection
- Prometheus integration
- Grafana dashboard support
- Multi-cluster support

## Quick Start

### Prerequisites

- Kubernetes cluster with TPU nodes
- Helm 3.x
- GCP credentials (Service Account or Workload Identity)

### Installation
```bash
# Add your values
cat > my-values.yaml << 'EOV'
env:
  GCP_PROJECT_ID: "your-project-id"
  GKE_CLUSTER_NAME: "your-cluster"
  GKE_CLUSTER_LOCATION: "us-central1"

image:
  repository: yby654/tpu-exporter
  tag: "0.4"

prometheus:
  enabled: true
  grafana:
    enabled: true
    adminPassword: "your-secure-password"
EOV

# Install
helm install tpu-exporter ./charts \
  --namespace monitoring \
  --create-namespace \
  --values my-values.yaml
```

### Using from GitHub
```bash
git clone https://github.com/YOUR_USERNAME/tpu-exporter.git
cd tpu-exporter
helm install tpu-exporter ./charts -n monitoring --create-namespace
```

## Configuration

See [charts/README.md](charts/README.md) for detailed configuration options.

## Development

### Build Docker Image
```bash
docker build -t yby654/tpu-exporter:dev .
docker push yby654/tpu-exporter:dev
```

### Run Locally
```bash
export GCP_PROJECT_ID="your-project"
export GKE_CLUSTER_NAME="your-cluster"
export GKE_CLUSTER_LOCATION="us-central1"

python exporter.py
```

### Test Helm Chart
```bash
# Dry run
helm install tpu-exporter ./charts --dry-run --debug

# Template rendering
helm template tpu-exporter ./charts > rendered.yaml
```

## Monitoring

Access Grafana dashboard:
```bash
kubectl port-forward -n monitoring svc/prometheus-grafana 3000:80
# Open http://localhost:3000
# Default credentials: admin / (from values.yaml)
```

## License

MIT

## Contributing

Pull requests are welcome!
EOF
```

### 5. GitHub Secrets 설정

Repository Settings → Secrets and variables → Actions에서 추가:
```
DOCKER_USERNAME: yby654
DOCKER_PASSWORD: <your-docker-hub-token>
