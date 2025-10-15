import os
import time
from prometheus_client import start_http_server, Gauge, Info
from kubernetes import client, config
from google.cloud import container_v1
from google.cloud import monitoring_v3
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PROJECT_ID = os.getenv('GCP_PROJECT_ID')
CLUSTER_NAME = os.getenv('GKE_CLUSTER_NAME')
CLUSTER_LOCATION = os.getenv('GKE_CLUSTER_LOCATION')

if not all([PROJECT_ID, CLUSTER_NAME, CLUSTER_LOCATION]):
    raise ValueError("환경변수 필요: GCP_PROJECT_ID, GKE_CLUSTER_NAME, GKE_CLUSTER_LOCATION")

# Prometheus 메트릭 정의
cluster_info = Info('gke_cluster', 'GKE Cluster information')

# 클러스터 레벨 집계 메트릭
cluster_tpu_total = Gauge('gke_cluster_tpu_total', 'Total TPU chips in cluster', ['tpu_type'])
cluster_tpu_allocated = Gauge('gke_cluster_tpu_allocated', 'Allocated TPU chips in cluster', ['tpu_type'])
cluster_tpu_available = Gauge('gke_cluster_tpu_available', 'Available TPU chips in cluster', ['tpu_type'])
cluster_tpu_pods_running = Gauge('gke_cluster_tpu_pods_running', 'Number of pods using TPU', ['namespace', 'tpu_type'])
cluster_tpu_pods_pending = Gauge('gke_cluster_tpu_pods_pending', 'Number of pods waiting for TPU', ['namespace', 'tpu_type'])

# 노드 레벨 메트릭
tpu_node_count = Gauge('gke_tpu_node_total', 'Total TPU nodes', ['tpu_type', 'topology', 'zone'])
tpu_chip_count = Gauge('gke_tpu_chip_total', 'Total TPU chips per node', ['node', 'tpu_type', 'zone'])
tpu_node_capacity = Gauge('gke_tpu_node_capacity', 'Node capacity', 
                          ['node', 'resource_type', 'tpu_type', 'zone'])
tpu_node_allocatable = Gauge('gke_tpu_node_allocatable', 'Allocatable resources', 
                              ['node', 'resource_type', 'tpu_type', 'zone'])
tpu_node_usage = Gauge('gke_tpu_node_usage', 'Current usage', 
                       ['node', 'resource_type', 'tpu_type', 'zone'])

# Cloud Monitoring 메트릭 (TPU VM)
tpu_memory_usage = Gauge('gke_tpu_memory_usage_bytes', 'TPU VM memory usage', 
                         ['node', 'tpu_type'])
tpu_cpu_utilization = Gauge('gke_tpu_cpu_utilization', 'TPU VM CPU utilization', 
                            ['node', 'tpu_type'])
tpu_network_received = Gauge('gke_tpu_network_received_bytes_total', 'Network bytes received', 
                             ['node', 'tpu_type'])
tpu_network_sent = Gauge('gke_tpu_network_sent_bytes_total', 'Network bytes sent', 
                         ['node', 'tpu_type'])
tpu_tensorcore_idle = Gauge('gke_tpu_tensorcore_idle_duration_seconds', 'TensorCore idle duration', 
                            ['node', 'tpu_type'])
tpu_tensorcore_utilization = Gauge('gke_tpu_tensorcore_utilization', 'TensorCore utilization', 
                                   ['node', 'tpu_type'])
tpu_memory_bandwidth_utilization = Gauge('gke_tpu_memory_bandwidth_utilization', 'Memory bandwidth utilization', 
                                         ['node', 'tpu_type'])
tpu_duty_cycle = Gauge('gke_tpu_duty_cycle', 'Accelerator duty cycle', 
                       ['node', 'tpu_type'])
tpu_memory_total = Gauge('gke_tpu_memory_total_bytes', 'Total accelerator memory', 
                         ['node', 'tpu_type'])
tpu_memory_used = Gauge('gke_tpu_memory_used_bytes', 'Used accelerator memory', 
                        ['node', 'tpu_type'])

# Pod 메트릭
tpu_pod_request = Gauge('gke_tpu_pod_requests', 'TPU pod resource requests',
                        ['pod', 'namespace', 'node', 'resource_type'])

# GCP 클라이언트 초기화
container_client = container_v1.ClusterManagerClient()
monitoring_client = monitoring_v3.MetricServiceClient()

# Cloud Monitoring 메트릭 맵핑
MONITORING_METRICS = {
    'memory/usage': ('gke_tpu_memory_usage_bytes', tpu_memory_usage),
    'cpu/utilization': ('gke_tpu_cpu_utilization', tpu_cpu_utilization),
    'network/received_bytes_count': ('gke_tpu_network_received_bytes_total', tpu_network_received),
    'network/sent_bytes_count': ('gke_tpu_network_sent_bytes_total', tpu_network_sent),
    'tpu/tensorcore/idle_duration': ('gke_tpu_tensorcore_idle_duration_seconds', tpu_tensorcore_idle),
    'accelerator/tensorcore_utilization': ('gke_tpu_tensorcore_utilization', tpu_tensorcore_utilization),
    'accelerator/memory_bandwidth_utilization': ('gke_tpu_memory_bandwidth_utilization', tpu_memory_bandwidth_utilization),
    'accelerator/duty_cycle': ('gke_tpu_duty_cycle', tpu_duty_cycle),
    'accelerator/memory_total': ('gke_tpu_memory_total_bytes', tpu_memory_total),
    'accelerator/memory_used': ('gke_tpu_memory_used_bytes', tpu_memory_used),
}

def get_cluster_info():
    try:
        cluster_path = f"projects/{PROJECT_ID}/locations/{CLUSTER_LOCATION}/clusters/{CLUSTER_NAME}"
        cluster = container_client.get_cluster(name=cluster_path)
        cluster_info.info({
            'project_id': PROJECT_ID,
            'cluster_name': CLUSTER_NAME,
            'location': CLUSTER_LOCATION,
            'version': cluster.current_master_version,
            'node_count': str(cluster.current_node_count)
        })
        logger.info(f"Cluster: {cluster.current_node_count} nodes")
    except Exception as e:
        logger.error(f"Failed to get cluster info: {e}")

def get_cloud_monitoring_metrics(node, tpu_type):
    """Cloud Monitoring에서 TPU 메트릭 가져오기"""
    try:
        project_name = f"projects/{PROJECT_ID}"
        now = datetime.utcnow()
        end_time = now
        start_time = now - timedelta(minutes=5)
        
        interval = monitoring_v3.TimeInterval({
            "end_time": {"seconds": int(end_time.timestamp())},
            "start_time": {"seconds": int(start_time.timestamp())},
        })
        
        # 각 메트릭 타입별로 조회
        for metric_suffix, (metric_name, gauge) in MONITORING_METRICS.items():
            try:
                # TPU 메트릭 필터
                metric_filter = (
                    f'metric.type="tpu.googleapis.com/instance/{metric_suffix}" '
                    f'AND resource.labels.node_id="{node}"'
                )
                
                results = monitoring_client.list_time_series(
                    request={
                        "name": project_name,
                        "filter": metric_filter,
                        "interval": interval,
                        "view": monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL,
                    }
                )
                
                for result in results:
                    if result.points:
                        value = result.points[0].value.double_value
                        gauge.labels(node=node, tpu_type=tpu_type).set(value)
                        logger.debug(f"Metric {metric_suffix} for {node}: {value}")
                        
            except Exception as e:
                logger.debug(f"Metric {metric_suffix} not available for {node}: {e}")
                
    except Exception as e:
        logger.warning(f"Failed to get Cloud Monitoring metrics for {node}: {e}")

def collect_tpu_metrics():
    try:
        try:
            config.load_incluster_config()
        except:
            config.load_kube_config()
        
        v1 = client.CoreV1Api()
        get_cluster_info()
        
        logger.info("Collecting TPU metrics...")
        # TPU 노드 찾기 (올바른 레이블 사용)
        nodes = v1.list_node(label_selector="cloud.google.com/gke-tpu-accelerator")
        
        if not nodes.items:
            logger.warning("No TPU nodes found in cluster")
            return
        
        tpu_types = {}
        total_chips = {}
        allocated_chips = {}
        
        for node in nodes.items:
            labels = node.metadata.labels
            tpu_type = labels.get('cloud.google.com/gke-tpu-accelerator', 'unknown')
            topology = labels.get('cloud.google.com/gke-tpu-topology', 'unknown')
            zone = labels.get('topology.kubernetes.io/zone', 'unknown')
            
            key = (tpu_type, topology, zone)
            tpu_types[key] = tpu_types.get(key, 0) + 1
            
            capacity = node.status.capacity
            allocatable = node.status.allocatable
            node = node.metadata.name
            
            # 리소스 메트릭
            for res_type in ['cpu', 'memory', 'ephemeral-storage']:
                if res_type in capacity:
                    cap_val = parse_resource(capacity[res_type], res_type)
                    alloc_val = parse_resource(allocatable[res_type], res_type)
                    res_name = res_type.replace('-', '_')
                    
                    tpu_node_capacity.labels(node, res_name, tpu_type, zone).set(cap_val)
                    tpu_node_allocatable.labels(node, res_name, tpu_type, zone).set(alloc_val)
                    tpu_node_usage.labels(node, res_name, tpu_type, zone).set(cap_val - alloc_val)
            
            # TPU chips
            if 'google.com/tpu' in capacity:
                chips = int(capacity['google.com/tpu'])
                chips_alloc = int(allocatable.get('google.com/tpu', 0))
                chips_used = chips - chips_alloc
                
                tpu_chip_count.labels(node, tpu_type, zone).set(chips)
                tpu_node_capacity.labels(node, 'tpu', tpu_type, zone).set(chips)
                tpu_node_allocatable.labels(node, 'tpu', tpu_type, zone).set(chips_alloc)
                tpu_node_usage.labels(node, 'tpu', tpu_type, zone).set(chips_used)
                
                # 클러스터 레벨 집계
                total_chips[tpu_type] = total_chips.get(tpu_type, 0) + chips
                allocated_chips[tpu_type] = allocated_chips.get(tpu_type, 0) + chips_used
            
            # Cloud Monitoring 메트릭 수집
            get_cloud_monitoring_metrics(node, tpu_type)
        
        # 노드 카운트
        for (tpu_type, topology, zone), count in tpu_types.items():
            tpu_node_count.labels(tpu_type, topology, zone).set(count)
        
        # 클러스터 레벨 TPU 집계
        for tpu_type, chips in total_chips.items():
            cluster_tpu_total.labels(tpu_type).set(chips)
            allocated = allocated_chips.get(tpu_type, 0)
            cluster_tpu_allocated.labels(tpu_type).set(allocated)
            cluster_tpu_available.labels(tpu_type).set(chips - allocated)
        
        logger.info(f"Found {len(nodes.items)} TPU nodes, {sum(total_chips.values())} total chips")
        
        # Pod 정보 수집
        running_pods = {}
        pending_pods = {}
        
        # Running pods
        pods = v1.list_pod_for_all_namespaces(field_selector='status.phase=Running')
        for pod in pods.items:
            process_pod(v1, pod, running_pods, 'Running')
        
        # Pending pods
        pending_pod_list = v1.list_pod_for_all_namespaces(field_selector='status.phase=Pending')
        for pod in pending_pod_list.items:
            process_pod(v1, pod, pending_pods, 'Pending')
        
        # Pod 카운트 메트릭
        for (namespace, tpu_type), count in running_pods.items():
            cluster_tpu_pods_running.labels(namespace, tpu_type).set(count)
        
        for (namespace, tpu_type), count in pending_pods.items():
            cluster_tpu_pods_pending.labels(namespace, tpu_type).set(count)
        
        logger.info(f"Running TPU pods: {sum(running_pods.values())}, Pending: {sum(pending_pods.values())}")
        
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)

def process_pod(v1, pod, pod_dict, phase):
    """Pod 정보 처리"""
    node = pod.spec.node
    
    # Pending pod는 node이 없을 수 있음
    if phase == 'Running' and not node:
        return
    
    # TPU 요청이 있는지 확인
    has_tpu = False
    for container in pod.spec.containers:
        if container.resources and container.resources.requests:
            if 'google.com/tpu' in container.resources.requests:
                has_tpu = True
                break
    
    if not has_tpu:
        return
    
    # Running pod는 노드에서 TPU 타입 가져오기
    tpu_type = 'unknown'
    if phase == 'Running':
        try:
            node = v1.read_node(node)
            if 'cloud.google.com/gke-tpu-accelerator' in node.metadata.labels:
                tpu_type = node.metadata.labels.get('cloud.google.com/gke-tpu-accelerator', 'unknown')
            else:
                return
        except:
            return
    else:
        # Pending pod는 요청한 TPU 타입 추정 (nodeSelector 등에서)
        if pod.spec.node_selector:
            tpu_type = pod.spec.node_selector.get('cloud.google.com/gke-tpu-accelerator', 'pending')
    
    namespace = pod.metadata.namespace
    pod = pod.metadata.name
    
    # 카운트
    key = (namespace, tpu_type)
    pod_dict[key] = pod_dict.get(key, 0) + 1
    
    # 리소스 요청량 (Running pod만)
    if phase == 'Running':
        for container in pod.spec.containers:
            if container.resources and container.resources.requests:
                for res_type, value in container.resources.requests.items():
                    res_val = parse_resource(value, res_type)
                    tpu_pod_request.labels(pod, namespace, node, res_type).set(res_val)

def parse_resource(value, res_type):
    if not value:
        return 0
    
    if res_type == 'cpu':
        if value.endswith('m'):
            return int(value[:-1]) / 1000.0
        return float(value)
    elif res_type in ['memory', 'ephemeral-storage']:
        units = {'Ki': 1024, 'Mi': 1024**2, 'Gi': 1024**3, 'Ti': 1024**4}
        for unit, mult in units.items():
            if value.endswith(unit):
                return int(value[:-len(unit)]) * mult
        return int(value)
    elif res_type == 'google.com/tpu':
        return int(value)
    return float(value)

if __name__ == '__main__':
    logger.info(f"Starting exporter: project={PROJECT_ID}, cluster={CLUSTER_NAME}")
    start_http_server(8000)
    logger.info("Server started on :8000")
    
    while True:
        try:
            collect_tpu_metrics()
        except Exception as e:
            logger.error(f"Error in loop: {e}")
        time.sleep(30)
