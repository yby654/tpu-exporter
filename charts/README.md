# 🧠 TPU Exporter Helm Chart

Helm chart for deploying **TPU Exporter** along with optional **Prometheus**, **Grafana**, and **Alertmanager** components.

이 차트는 **GKE 환경에서 TPU 노드/메모리/CPU 등 TPU 관련 메트릭을 수집**하고,  
**Prometheus 및 Grafana를 통해 시각화 및 모니터링**할 수 있도록 구성되어 있습니다.

---

## 📦 Chart Information

| 항목 | 설명 |
|------|------|
| **Chart Name** | `tpu-exporter` |
| **App Version** | `0.4` |
| **Chart Version** | `0.2.0` |
| **Namespace** | `monitoring` |
| **Dependencies** | [`kube-prometheus-stack`](https://artifacthub.io/packages/helm/prometheus-community/kube-prometheus-stack) (optional) |

---

## 🧩 Components

| 구성요소 | 설명 |
|-----------|------|
| **TPU Exporter** | GKE TPU 리소스 및 Cloud Monitoring 메트릭 수집기 |
| **Prometheus** | Exporter로부터 메트릭 수집 |
| **Grafana** | TPU 관련 대시보드 시각화 |
| **Alertmanager** | TPU 상태 기반 알람 발송 |
| **ServiceMonitor** | Prometheus Operator를 위한 CRD |

---

## ⚙️ Installation

### 1. Repository 추가

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update
```

### 2. Chart 설치

```bash
helm install tpu-exporter ./tpu-exporter -n monitoring --create-namespace
```

### 3. 확인

```bash
kubectl get pods -n monitoring
kubectl get svc -n monitoring
```

---

## 🧾 Values Reference

| Key | Type | Default | 설명 |
|-----|------|----------|------|
| `image.repository` | string | `"yby654/tpu-exporter"` | TPU Exporter 이미지 리포지토리 |
| `image.tag` | string | `"0.4"` | 이미지 태그 |
| `replicaCount` | int | `1` | Exporter 복제 개수 |
| `serviceAccount.create` | bool | `true` | ServiceAccount 생성 여부 |
| `serviceAccount.name` | string | `""` | 기존 ServiceAccount 사용 시 이름 |
| `service.type` | string | `"ClusterIP"` | Kubernetes 서비스 타입 |
| `service.port` | int | `8080` | Exporter 포트 |
| `env.GCP_PROJECT_ID` | string | `"leafy-environs-445206-d2"` | GCP 프로젝트 ID |
| `env.GKE_CLUSTER_NAME` | string | `"cluster-1"` | GKE 클러스터 이름 |
| `env.GKE_CLUSTER_LOCATION` | string | `"us-central1"` | GKE 클러스터 리전 |
| `prometheus.enabled` | bool | `true` | Prometheus 스택 활성화 여부 |
| `prometheus.grafana.enabled` | bool | `true` | Grafana 활성화 여부 |
| `prometheus.grafana.adminUser` | string | `"admin"` | Grafana 기본 사용자 |
| `prometheus.grafana.adminPassword` | string | `"prom-1234"` | Grafana 기본 비밀번호 |
| `prometheus.grafana.dashboards.enabled` | bool | `true` | TPU Exporter 대시보드 자동 등록 |
| `prometheus.alertmanager.enabled` | bool | `true` | Alertmanager 활성화 여부 |

---

## 📊 Grafana Dashboard

TPU Exporter 차트는 Grafana 대시보드를 자동으로 로드합니다.

**기본 접속 정보:**

| 항목 | 값 |
|------|----|
| **URL** | `http://<grafana-service>.<namespace>.svc.cluster.local:80` |
| **사용자** | `admin` |
| **비밀번호** | `prom-1234` |

**기본 포함 패널:**
- TPU Node Utilization  
- TPU Memory Usage  
- TPU CPU Utilization  
- TPU Duty Cycle  
- TPU Network Usage  

---

## 🚨 Alertmanager Integration (Optional)

Prometheus Alert Rule을 통해 TPU 자원 상태 이상을 감지할 수 있습니다.

예시 (`templates/alert-rules.yaml`):

```yaml
groups:
- name: tpu.rules
  rules:
  - alert: TPUHighUsage
    expr: gke_tpu_node_usage > 0.9
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "TPU usage high on {{ $labels.node }}"
      description: "TPU usage exceeded 90% for more than 5 minutes"
```

---

## 🔄 Upgrade & Uninstall

### 업그레이드
```bash
helm upgrade tpu-exporter ./tpu-exporter -n monitoring
```

### 삭제
```bash
helm uninstall tpu-exporter -n monitoring
```

---

## 🧠 Notes

- `prometheus.enabled=false` → Prometheus 및 Grafana는 배포되지 않고, 기존 모니터링 스택에 연동만 수행합니다.  
- `serviceAccount.create=false` + `serviceAccount.name=my-sa` → 기존 GSA 또는 수동 생성된 SA를 그대로 사용합니다.  
- TPU Exporter는 기본적으로 `/metrics` (포트 8080)에서 Prometheus 포맷 데이터를 노출합니다.

---

## 🏗️ Architecture

```
+-------------------+        +--------------------+
| TPU Exporter Pod  | --->   | Prometheus         |
| /metrics endpoint |        | (scrape metrics)   |
+-------------------+        +--------------------+
                                    |
                                    v
                             +--------------+
                             | Grafana UI   |
                             | Dashboards   |
                             +--------------+
                                    |
                                    v
                             +----------------+
                             | Alertmanager   |
                             | (Optional)     |
                             +----------------+
```

---

## 🔐 ServiceAccount Notes

**GCP 연동(GSA) 사용 시:**
```yaml
serviceAccount:
  create: true
  annotations:
    iam.gke.io/gcp-service-account: "your-gsa@project.iam.gserviceaccount.com"
```

**Key 기반 인증(JSON 파일) 사용 시:**
```yaml
env:
  GOOGLE_APPLICATION_CREDENTIALS: "/var/secrets/google/key.json"
volumeMounts:
  - name: gcp-key
    mountPath: /var/secrets/google
volumes:
  - name: gcp-key
    secret:
      secretName: gcp-service-key
```

---

## 🧪 Local Test

```bash
helm template tpu-exporter ./tpu-exporter --values values.yaml
kubectl port-forward svc/tpu-exporter 8080:8080 -n monitoring
curl http://localhost:8080/metrics
```

---

## 📚 License

MIT License © 2025 **yby654**  
Maintainer: **bbi7**
